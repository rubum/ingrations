import time
import json
import logging
import asyncio
from typing import Dict, Any, Optional
import httpx
from ingrations.models import (
    AppSpec,
    ActionSpec,
    ExecutionResult,
    ParameterLocation,
    AuthType
)
from ingrations.auth import AuthManager, default_auth_manager

logger = logging.getLogger("ingrations.executor")


class ActionExecutor:
    """
    Executes ActionSpec requests against remote API endpoints with parameter routing,
    authentication injection, retry backoff, and error normalization.
    """

    def __init__(self, auth_manager: Optional[AuthManager] = None):
        self.auth_manager = auth_manager or default_auth_manager

    async def execute(
        self,
        app: AppSpec,
        action: ActionSpec,
        params: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        client: Optional[httpx.AsyncClient] = None
    ) -> ExecutionResult:
        """Executes an action specification against the live API or in dry-run mode."""
        start_time = time.perf_counter()
        params = params or {}

        # 1. Parameter separation & path interpolation
        path_params: Dict[str, Any] = {}
        query_params: Dict[str, Any] = {}
        header_params: Dict[str, str] = {}
        body_params: Dict[str, Any] = {}

        param_map = {p.name: p for p in action.parameters}

        for k, v in params.items():
            if k in param_map:
                loc = param_map[k].location
                if loc == ParameterLocation.PATH:
                    path_params[k] = v
                elif loc == ParameterLocation.QUERY:
                    query_params[k] = v
                elif loc == ParameterLocation.HEADER:
                    header_params[k] = str(v)
                elif loc == ParameterLocation.BODY:
                    body_params[k] = v
            else:
                # Default unknown parameters to body if POST/PUT/PATCH, else query
                if action.method.value in ["POST", "PUT", "PATCH"]:
                    body_params[k] = v
                else:
                    query_params[k] = v

        # Interpolate path
        formatted_path = action.path
        for pk, pv in path_params.items():
            formatted_path = formatted_path.replace(f"{{{pk}}}", str(pv))

        # Check for unformatted path variables
        if "{" in formatted_path and "}" in formatted_path:
            missing = [p.name for p in action.parameters if p.location == ParameterLocation.PATH and p.name not in path_params]
            duration = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                success=False,
                action_id=action.id,
                status_code=400,
                error=f"Missing required path parameter(s): {', '.join(missing)} in path '{action.path}'",
                duration_ms=duration
            )

        # Build full URL
        base = app.base_url.rstrip("/")
        # Also interpolate base_url placeholders like {service} or {project_ref} if provided
        for pk, pv in params.items():
            if f"{{{pk}}}" in base:
                base = base.replace(f"{{{pk}}}", str(pv))

        full_url = f"{base}/{formatted_path.lstrip('/')}"

        # 2. Authentication injection
        auth_req = app.auth
        token = self.auth_manager.get_credential(app.id, auth_req.env_vars)

        if auth_req.auth_type != AuthType.NONE and not token and not dry_run:
            duration = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                success=False,
                action_id=action.id,
                status_code=401,
                error=f"Authentication required for app '{app.name}' ({app.id}). Set credential via 'ingrations auth set {app.id} <token>' or environment variable.",
                duration_ms=duration
            )

        headers = {
            "User-Agent": "Ingrations-Agent/1.0",
            "Accept": "application/json"
        }

        if token:
            if auth_req.auth_type == AuthType.BEARER_TOKEN:
                prefix = auth_req.token_prefix or "Bearer "
                headers["Authorization"] = f"{prefix}{token}"
            elif auth_req.auth_type == AuthType.API_KEY:
                if auth_req.query_param:
                    query_params[auth_req.query_param] = token
                else:
                    h_name = auth_req.header_name or "X-API-Key"
                    headers[h_name] = token
            elif auth_req.auth_type == AuthType.CUSTOM_HEADER:
                h_name = auth_req.header_name or "X-API-Key"
                headers[h_name] = token
            elif auth_req.auth_type == AuthType.BASIC:
                headers["Authorization"] = f"Basic {token}"

        headers.update(header_params)

        # If dry run, return simulated payload
        if dry_run:
            duration = (time.perf_counter() - start_time) * 1000
            # Redact authorization header for safety
            safe_headers = dict(headers)
            if "Authorization" in safe_headers:
                safe_headers["Authorization"] = "[REDACTED]"
            return ExecutionResult(
                success=True,
                action_id=action.id,
                status_code=200,
                data={
                    "dry_run": True,
                    "method": action.method.value,
                    "url": full_url,
                    "headers": safe_headers,
                    "query_params": query_params,
                    "body": body_params
                },
                duration_ms=duration
            )

        # 3. HTTP Execution with retry backoff
        json_body = body_params if body_params and action.method.value in ["POST", "PUT", "PATCH"] else None

        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            close_client = True

        try:
            resp = None
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    resp = await client.request(
                        method=action.method.value,
                        url=full_url,
                        params=query_params if query_params else None,
                        headers=headers,
                        json=json_body
                    )
                    # Retry on 429 rate limit or 502/503/504 gateway errors
                    if resp.status_code in [429, 502, 503, 504] and attempt < max_retries:
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    break
                except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                    if attempt < max_retries:
                        await asyncio.sleep(1.0)
                        continue
                    raise net_err

            duration = (time.perf_counter() - start_time) * 1000

            # Parse response
            data = None
            if resp.content:
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text

            is_success = 200 <= resp.status_code < 300
            error_msg = None if is_success else f"HTTP {resp.status_code}: {resp.text[:500]}"

            return ExecutionResult(
                success=is_success,
                action_id=action.id,
                status_code=resp.status_code,
                data=data,
                error=error_msg,
                duration_ms=duration,
                headers=dict(resp.headers)
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                success=False,
                action_id=action.id,
                status_code=500,
                error=f"Execution failed: {str(e)}",
                duration_ms=duration
            )
        finally:
            if close_client:
                await client.aclose()
