from typing import Dict, Any
from ingrations.models import ActionSpec


def action_to_claude_declaration(action: ActionSpec) -> Dict[str, Any]:
    """Converts an ActionSpec into Anthropic Claude tool format."""
    safe_name = action.id.replace(".", "_")
    return {
        "name": safe_name,
        "description": f"[{action.app_id.upper()}] {action.description}",
        "input_schema": action.to_json_schema()
    }
