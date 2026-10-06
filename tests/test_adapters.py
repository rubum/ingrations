from ingrations.catalog import Catalog
from ingrations.adapters.gemini import action_to_gemini_declaration
from ingrations.adapters.openai import action_to_openai_declaration
from ingrations.adapters.claude import action_to_claude_declaration


def test_gemini_adapter(catalog: Catalog):
    action = catalog.get_action("github.create_issue")
    decl = action_to_gemini_declaration(action)
    assert decl["name"] == "github_create_issue"
    assert decl["parameters"]["type"] == "OBJECT"
    props = decl["parameters"]["properties"]
    assert "title" in props
    assert props["title"]["type"] == "STRING"
    assert "title" in decl["parameters"]["required"]


def test_openai_adapter(catalog: Catalog):
    action = catalog.get_action("github.create_issue")
    decl = action_to_openai_declaration(action)
    assert decl["type"] == "function"
    assert decl["function"]["name"] == "github_create_issue"
    assert decl["function"]["parameters"]["type"] == "object"
    assert "title" in decl["function"]["parameters"]["properties"]


def test_claude_adapter(catalog: Catalog):
    action = catalog.get_action("github.create_issue")
    decl = action_to_claude_declaration(action)
    assert decl["name"] == "github_create_issue"
    assert decl["input_schema"]["type"] == "object"
    assert "title" in decl["input_schema"]["properties"]
