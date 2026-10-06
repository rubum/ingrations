"""
Ingrations: Open-source universal action infrastructure and tool integrations for AI agents.
"""

from ingrations.client import Ingrations
from ingrations.catalog import Catalog, default_catalog
from ingrations.discovery import ToolDiscoveryEngine, default_discovery
from ingrations.auth import AuthManager, default_auth_manager
from ingrations.executor import ActionExecutor
from ingrations.compiler import OpenAPICompiler
from ingrations.models import (
    AppSpec,
    ActionSpec,
    ParameterSpec,
    ExecutionResult,
    SearchResult,
    AuthRequirement,
    AuthType,
    HTTPMethod,
    ParameterLocation
)

__version__ = "0.1.0"
__all__ = [
    "Ingrations",
    "Catalog",
    "default_catalog",
    "ToolDiscoveryEngine",
    "default_discovery",
    "AuthManager",
    "default_auth_manager",
    "ActionExecutor",
    "OpenAPICompiler",
    "AppSpec",
    "ActionSpec",
    "ParameterSpec",
    "ExecutionResult",
    "SearchResult",
    "AuthRequirement",
    "AuthType",
    "HTTPMethod",
    "ParameterLocation"
]
