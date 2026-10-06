import pytest
from ingrations.mcp.server import MCPServer
from ingrations.mcp.protocol import JSONRPCRequest


@pytest.mark.asyncio
async def test_mcp_initialize():
    server = MCPServer()
    req = JSONRPCRequest(id=1, method="initialize")
    resp = await server.handle_request(req)
    assert resp.id == 1
    assert resp.result["serverInfo"]["name"] == "ingrations-mcp"


@pytest.mark.asyncio
async def test_mcp_tools_list():
    server = MCPServer(mounted_apps=["github"])
    req = JSONRPCRequest(id=2, method="tools/list")
    resp = await server.handle_request(req)
    assert resp.id == 2
    tools = resp.result["tools"]
    tool_names = [t["name"] for t in tools]
    assert "ingrations_search_tools" in tool_names
    assert "ingrations_execute" in tool_names
    assert "github_create_pull_request" in tool_names


@pytest.mark.asyncio
async def test_mcp_tools_call_search():
    server = MCPServer()
    req = JSONRPCRequest(
        id=3,
        method="tools/call",
        params={
            "name": "ingrations_search_tools",
            "arguments": {"query": "pull request", "limit": 2}
        }
    )
    resp = await server.handle_request(req)
    assert resp.id == 3
    assert len(resp.result["content"]) > 0
    assert "github.create_pull_request" in resp.result["content"][0]["text"]


@pytest.mark.asyncio
async def test_mcp_tools_call_execute_dry_run():
    server = MCPServer()
    req = JSONRPCRequest(
        id=4,
        method="tools/call",
        params={
            "name": "ingrations_execute",
            "arguments": {
                "action_id": "github.create_pull_request",
                "params": {"owner": "rubum", "repo": "ingrations", "title": "MCP feat", "head": "a", "base": "b"},
                "dry_run": True
            }
        }
    )
    resp = await server.handle_request(req)
    assert resp.id == 4
    assert resp.result["isError"] is False
    assert '"dry_run": true' in resp.result["content"][0]["text"]
