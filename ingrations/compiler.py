import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
from ingrations.models import (
    AppSpec,
    ActionSpec,
    ParameterSpec,
    ParameterLocation,
    HTTPMethod,
    AuthRequirement,
    AuthType
)

logger = logging.getLogger("ingrations.compiler")


class OpenAPICompiler:
    """
    Compiles raw OpenAPI 2.0 / 3.0 / 3.1 specs into normalized AppSpec and ActionSpec models.
    """

    @classmethod
    def compile_file(cls, file_path: Path, app_id: Optional[str] = None) -> AppSpec:
        """Loads a JSON or YAML OpenAPI file and compiles it into an AppSpec."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            data = yaml.safe_load(content)

        return cls.compile_spec(data, app_id=app_id or file_path.stem.lower())

    @classmethod
    def compile_spec(cls, spec: Dict[str, Any], app_id: str) -> AppSpec:
        """Compiles OpenAPI dictionary into an AppSpec."""
        info = spec.get("info", {})
        title = info.get("title", app_id.capitalize())
        description = info.get("description", f"Integration toolkit for {title}").strip()
        version = info.get("version", "1.0.0")

        # Resolve Base URL
        base_url = "https://api.example.com"
        servers = spec.get("servers", [])
        if servers and isinstance(servers, list):
            base_url = servers[0].get("url", base_url)
        elif "host" in spec:
            schemes = spec.get("schemes", ["https"])
            scheme = schemes[0] if schemes else "https"
            base_path = spec.get("basePath", "")
            base_url = f"{scheme}://{spec['host']}{base_path}".rstrip("/")

        auth_req = cls._extract_auth(spec)
        actions: List[ActionSpec] = []

        paths = spec.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method_str in ["get", "post", "put", "patch", "delete"]:
                op = path_item.get(method_str)
                if not op or not isinstance(op, dict):
                    continue

                action = cls._compile_operation(
                    app_id=app_id,
                    path=path,
                    method_str=method_str,
                    operation=op,
                    common_params=path_item.get("parameters", [])
                )
                actions.append(action)

        return AppSpec(
            id=app_id.lower(),
            name=title,
            description=description[:250],
            category=cls._detect_category(app_id, title, description),
            base_url=base_url,
            auth=auth_req,
            actions=actions,
            version=version
        )

    @classmethod
    def _compile_operation(
        cls,
        app_id: str,
        path: str,
        method_str: str,
        operation: Dict[str, Any],
        common_params: List[Dict[str, Any]]
    ) -> ActionSpec:
        op_id = operation.get("operationId")
        if not op_id:
            clean_path = re.sub(r"[{}\-_/]+", "_", path).strip("_")
            op_id = f"{method_str}_{clean_path}"

        # Normalize action ID: app_id.clean_name
        clean_action_name = re.sub(r"[^A-Za-z0-9_]+", "_", op_id).strip("_").lower()
        full_action_id = f"{app_id}.{clean_action_name}"

        summary = operation.get("summary") or operation.get("description") or f"{method_str.upper()} {path}"
        description = (operation.get("description") or summary).strip()

        parameters: List[ParameterSpec] = []
        all_raw_params = list(common_params) + list(operation.get("parameters", []))

        for p in all_raw_params:
            if not isinstance(p, dict):
                continue
            name = p.get("name")
            if not name:
                continue

            in_loc = p.get("in", "query").lower()
            loc_enum = ParameterLocation.QUERY
            if in_loc == "path":
                loc_enum = ParameterLocation.PATH
            elif in_loc == "header":
                loc_enum = ParameterLocation.HEADER
            elif in_loc == "body":
                loc_enum = ParameterLocation.BODY

            schema = p.get("schema", {})
            p_type = schema.get("type", p.get("type", "string"))

            parameters.append(ParameterSpec(
                name=name,
                type=p_type,
                description=p.get("description", ""),
                required=p.get("required", False),
                location=loc_enum,
                default=schema.get("default", p.get("default")),
                enum=schema.get("enum", p.get("enum"))
            ))

        # Handle requestBody (OpenAPI 3.x)
        req_body = operation.get("requestBody")
        if req_body and isinstance(req_body, dict):
            content = req_body.get("content", {})
            json_media = content.get("application/json") or content.get("*/*")
            if json_media and "schema" in json_media:
                body_schema = json_media["schema"]
                cls._extract_body_parameters(body_schema, parameters)

        tags = operation.get("tags", [])
        method_enum = HTTPMethod[method_str.upper()]

        return ActionSpec(
            id=full_action_id,
            name=summary[:80],
            description=description[:350],
            app_id=app_id,
            method=method_enum,
            path=path,
            parameters=parameters,
            tags=tags
        )

    @classmethod
    def _extract_body_parameters(cls, schema: Dict[str, Any], parameters: List[ParameterSpec]) -> None:
        if schema.get("type") == "object" and "properties" in schema:
            req_fields = schema.get("required", [])
            for prop_name, prop_spec in schema["properties"].items():
                if not isinstance(prop_spec, dict):
                    continue
                p_type = prop_spec.get("type", "string")
                parameters.append(ParameterSpec(
                    name=prop_name,
                    type=p_type,
                    description=prop_spec.get("description", ""),
                    required=prop_name in req_fields,
                    location=ParameterLocation.BODY,
                    default=prop_spec.get("default"),
                    enum=prop_spec.get("enum")
                ))
        else:
            parameters.append(ParameterSpec(
                name="payload",
                type=schema.get("type", "object"),
                description=schema.get("description", "JSON request body payload"),
                required=True,
                location=ParameterLocation.BODY,
                schema_def=schema
            ))

    @classmethod
    def _extract_auth(cls, spec: Dict[str, Any]) -> AuthRequirement:
        security_schemes = spec.get("components", {}).get("securitySchemes", {}) or spec.get("securityDefinitions", {})
        for name, scheme in security_schemes.items():
            if not isinstance(scheme, dict):
                continue
            s_type = scheme.get("type", "").lower()
            if s_type == "http":
                sub_scheme = scheme.get("scheme", "").lower()
                if sub_scheme == "bearer":
                    return AuthRequirement(
                        auth_type=AuthType.BEARER_TOKEN,
                        header_name="Authorization",
                        token_prefix="Bearer "
                    )
                elif sub_scheme == "basic":
                    return AuthRequirement(
                        auth_type=AuthType.BASIC,
                        header_name="Authorization"
                    )
            elif s_type == "apikey":
                in_loc = scheme.get("in", "header").lower()
                param_name = scheme.get("name", "X-API-Key")
                if in_loc == "header":
                    return AuthRequirement(
                        auth_type=AuthType.API_KEY,
                        header_name=param_name,
                        token_prefix=""
                    )
                else:
                    return AuthRequirement(
                        auth_type=AuthType.API_KEY,
                        query_param=param_name
                    )
            elif s_type in ["oauth2", "openIdConnect"]:
                return AuthRequirement(
                    auth_type=AuthType.OAUTH2,
                    header_name="Authorization",
                    token_prefix="Bearer "
                )

        return AuthRequirement(auth_type=AuthType.BEARER_TOKEN)

    @classmethod
    def _detect_category(cls, app_id: str, title: str, description: str) -> str:
        text = f"{app_id} {title} {description}".lower()
        if any(w in text for w in ["git", "issue", "bug", "code", "repo", "pipeline", "ci/cd", "sentry"]):
            return "devtools"
        if any(w in text for w in ["aws", "cloud", "database", "storage", "postgres", "s3", "compute", "dns"]):
            return "cloud"
        if any(w in text for w in ["slack", "notion", "email", "chat", "message", "calendar", "document"]):
            return "productivity"
        if any(w in text for w in ["payment", "invoice", "crm", "lead", "contact", "deal", "stripe", "sales"]):
            return "crm_finance"
        return "devtools"

    @classmethod
    def export_to_catalog(cls, app_spec: AppSpec, output_dir: Path) -> Path:
        """Serializes AppSpec to JSON and writes to category directory."""
        target_dir = output_dir / app_spec.category
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / f"{app_spec.id}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(app_spec.model_dump_json(indent=2))

        return file_path
