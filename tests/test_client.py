import pytest
from ingrations.client import Ingrations


def test_client_list_and_get(client: Ingrations):
    apps = client.list_apps()
    assert len(apps) >= 16

    github = client.get_app("github")
    assert github is not None

    pr_action = client.get_action("github.create_pull_request")
    assert pr_action is not None


def test_client_search_tools(client: Ingrations):
    matches = client.search_tools("send message", limit=3)
    assert len(matches) > 0
    app_ids = [m.app_id for m in matches]
    assert any(a in ["slack", "discord", "google_workspace"] for a in app_ids)


def test_client_export_declarations(client: Ingrations):
    # Gemini format
    gemini_tools = client.get_tool_declarations(app_ids=["github"], format="gemini")
    assert len(gemini_tools) == 6
    assert all("parameters" in t and "type" in t["parameters"] for t in gemini_tools)
    assert gemini_tools[0]["parameters"]["type"] == "OBJECT"

    # OpenAI format
    openai_tools = client.get_tool_declarations(app_ids=["github"], format="openai")
    assert len(openai_tools) == 6
    assert all(t["type"] == "function" for t in openai_tools)

    # Claude format
    claude_tools = client.get_tool_declarations(app_ids=["github"], format="claude")
    assert len(claude_tools) == 6
    assert all("input_schema" in t for t in claude_tools)


@pytest.mark.asyncio
async def test_client_dry_run_execution(client: Ingrations):
    res = await client.execute("slack.post_message", params={"channel": "C123", "text": "Hello world"}, dry_run=True)
    assert res.success is True
    assert res.data["dry_run"] is True
    assert res.data["body"]["text"] == "Hello world"
