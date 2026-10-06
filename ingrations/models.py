from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AuthType(str, Enum):
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    CUSTOM_HEADER = "custom_header"


class ParameterLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    BODY = "body"


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class AuthRequirement(BaseModel):
    auth_type: AuthType = AuthType.NONE
    header_name: Optional[str] = None
    token_prefix: Optional[str] = "Bearer "
    query_param: Optional[str] = None
    env_vars: List[str] = Field(default_factory=list)
    oauth2_authorize_url: Optional[str] = None
    oauth2_token_url: Optional[str] = None
    oauth2_scopes: List[str] = Field(default_factory=list)


class ParameterSpec(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    location: ParameterLocation = ParameterLocation.BODY
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None
    schema_def: Optional[Dict[str, Any]] = None


class ActionSpec(BaseModel):
    id: str
    name: str
    description: str
    app_id: str
    method: HTTPMethod = HTTPMethod.POST
    path: str
    parameters: List[ParameterSpec] = Field(default_factory=list)
    response_schema: Optional[Dict[str, Any]] = None
    rate_limit_per_minute: Optional[int] = None
    tags: List[str] = Field(default_factory=list)

    def to_json_schema(self) -> Dict[str, Any]:
        """Converts action parameters into a standard RFC JSON Schema."""
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for p in self.parameters:
            prop: Dict[str, Any] = {
                "type": p.type,
                "description": p.description or f"Parameter '{p.name}'"
            }
            if p.enum:
                prop["enum"] = p.enum
            if p.default is not None:
                prop["default"] = p.default
            if p.schema_def:
                prop.update(p.schema_def)

            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required
        }


class AppSpec(BaseModel):
    id: str
    name: str
    description: str
    category: str = "devtools"
    base_url: str
    auth: AuthRequirement = Field(default_factory=AuthRequirement)
    actions: List[ActionSpec] = Field(default_factory=list)
    icon: Optional[str] = None
    docs_url: Optional[str] = None
    version: str = "1.0.0"


class ExecutionResult(BaseModel):
    success: bool
    action_id: str
    status_code: int = 200
    data: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    headers: Dict[str, str] = Field(default_factory=dict)


class SearchResult(BaseModel):
    action_id: str
    app_id: str
    action_name: str
    app_name: str
    description: str
    category: str
    score: float = 0.0
    tags: List[str] = Field(default_factory=list)
