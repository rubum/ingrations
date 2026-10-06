import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from ingrations.models import (
    AppSpec,
    ActionSpec,
    ExecutionResult,
    SearchResult
)
from ingrations.catalog import Catalog, default_catalog
from ingrations.discovery import ToolDiscoveryEngine, default_discovery
from ingrations.auth import AuthManager, default_auth_manager
from ingrations.executor import ActionExecutor
from ingrations.adapters.gemini import action_to_gemini_declaration
from ingrations.adapters.openai import action_to_openai_declaration
from ingrations.adapters.claude import action_to_claude_declaration

logger = logging.getLogger("ingrations")


class Ingrations:
    """
    Main SDK client for Ingrations: Open-source universal action infrastructure for AI agents.
    """

    def __init__(
        self,
        catalog_dir: Optional[Path] = None,
        vault_path: Optional[Path] = None,
        passphrase: Optional[str] = None
    ):
        self.catalog = Catalog(catalog_dir) if catalog_dir else default_catalog
        self.auth = AuthManager(vault_path, passphrase) if vault_path else default_auth_manager
        self.discovery = ToolDiscoveryEngine(self.catalog)
        self.executor = ActionExecutor(self.auth)

    def list_apps(self, category: Optional[str] = None) -> List[AppSpec]:
        """Lists available apps in the catalog."""
        return self.catalog.list_apps(category)

    def get_app(self, app_id: str) -> Optional[AppSpec]:
        """Retrieves AppSpec by ID."""
        return self.catalog.get_app(app_id)

    def get_action(self, action_id: str) -> Optional[ActionSpec]:
        """Retrieves ActionSpec by ID."""
        return self.catalog.get_action(action_id)

    def search_tools(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[SearchResult]:
        """Performs sub-millisecond semantic BM25 search across all indexed tools."""
        return self.discovery.search(query, limit=limit, category=category)

    def get_tool_declarations(
        self,
        app_ids: Optional[List[str]] = None,
        action_ids: Optional[List[str]] = None,
        format: str = "json_schema"
    ) -> List[Dict[str, Any]]:
        """
        Exports tool definitions in the requested model provider format:
        'json_schema', 'gemini', 'openai', or 'claude'.
        """
        target_actions: List[ActionSpec] = []

        if action_ids:
            for aid in action_ids:
                a = self.catalog.get_action(aid)
                if a:
                    target_actions.append(a)
        elif app_ids:
            for aid in app_ids:
                app = self.catalog.get_app(aid)
                if app:
                    target_actions.extend(app.actions)
        else:
            target_actions = self.catalog.list_actions()

        fmt = format.lower()
        if fmt == "gemini":
            return [action_to_gemini_declaration(a) for a in target_actions]
        elif fmt in ["openai", "codex"]:
            return [action_to_openai_declaration(a) for a in target_actions]
        elif fmt in ["claude", "anthropic"]:
            return [action_to_claude_declaration(a) for a in target_actions]
        else:
            return [
                {
                    "name": a.id,
                    "description": a.description,
                    "parameters": a.to_json_schema()
                }
                for a in target_actions
            ]

    async def execute(
        self,
        action_id: str,
        params: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        client: Optional[httpx.AsyncClient] = None
    ) -> ExecutionResult:
        """Executes an action asynchronously against the destination API."""
        action = self.catalog.get_action(action_id)
        if not action:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                status_code=404,
                error=f"Action '{action_id}' not found in catalog."
            )

        app = self.catalog.get_app(action.app_id)
        if not app:
            return ExecutionResult(
                success=False,
                action_id=action_id,
                status_code=404,
                error=f"Parent app '{action.app_id}' not found in catalog."
            )

        return await self.executor.execute(app, action, params=params, dry_run=dry_run, client=client)
