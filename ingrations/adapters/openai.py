from typing import Dict, Any
from ingrations.models import ActionSpec


def action_to_openai_declaration(action: ActionSpec) -> Dict[str, Any]:
    """Converts an ActionSpec into OpenAI ChatCompletions tool format."""
    safe_name = action.id.replace(".", "_")
    return {
        "type": "function",
        "function": {
            "name": safe_name,
            "description": f"[{action.app_id.upper()}] {action.description}",
            "parameters": action.to_json_schema()
        }
    }
