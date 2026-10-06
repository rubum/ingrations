from typing import Dict, Any, List
from ingrations.models import ActionSpec, ParameterLocation


def action_to_gemini_declaration(action: ActionSpec) -> Dict[str, Any]:
    """
    Converts an ActionSpec into Google Gemini function declaration format
    with uppercase JSON Schema types (STRING, INTEGER, OBJECT, ARRAY, BOOLEAN).
    """
    TYPE_MAP = {
        "string": "STRING",
        "integer": "INTEGER",
        "number": "NUMBER",
        "boolean": "BOOLEAN",
        "object": "OBJECT",
        "array": "ARRAY"
    }

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for p in action.parameters:
        gemini_type = TYPE_MAP.get(p.type.lower(), "STRING")
        prop: Dict[str, Any] = {
            "type": gemini_type,
            "description": p.description or f"Parameter '{p.name}'"
        }
        if p.enum:
            prop["enum"] = [str(e) for e in p.enum]
        properties[p.name] = prop
        if p.required:
            required.append(p.name)

    # Gemini function names must match ^[a-zA-Z_][a-zA-Z0-9_]*$
    safe_name = action.id.replace(".", "_")

    return {
        "name": safe_name,
        "description": f"[{action.app_id.upper()}] {action.description}",
        "parameters": {
            "type": "OBJECT",
            "properties": properties,
            "required": required
        }
    }
