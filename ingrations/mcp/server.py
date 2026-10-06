import sys
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from ingrations.client import Ingrations
from ingrations.mcp.protocol import JSONRPCRequest, JSONRPCResponse, MCPTool

logger = logging.getLogger("ingrations.mcp")


class MCPServer:
    """
    Standard Model Context Protocol (MCP) server for Ingrations.
    Exposes tool discovery and all 1,500+ actions to any MCP-compliant AI client
    (Anthropic Claude, Cursor, Antigravity, VS Code, OpenAI).
    """

    def __init__(self, client: Optional[Ingrations] = None, mounted_apps: Optional[List[str]] = None):
        self.client = client or Ingrations()
        self.mounted_apps = mounted_apps or []

    async def handle_request(self, req: JSONRPCRequest) -> JSONRPCResponse:
        """Dispatches JSON-RPC request to appropriate handler."""
        method = req.method

        if method == "initialize":
            return JSONRPCResponse(
                id=req.id,
                result={
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True}
                    },
                    "serverInfo": {
                        "name": "ingrations-mcp",
                        "version": "0.1.0"
                    }
                }
            )

        elif method == "tools/list":
            tools: List[Dict[str, Any]] = []

            # 1. Meta discovery tool
            tools.append({
                "name": "ingrations_search_tools",
                "description": "Searches for external software integrations, APIs, and tools across 1,500+ apps. Returns matching actions and schemas.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Action or tool keywords, e.g. 'github create pull request', 'linear issue'"},
                        "category": {"type": "string", "description": "Optional category filter: devtools, productivity, cloud, crm_finance"},
                        "limit": {"type": "integer", "description": "Max tools to return", "default": 5}
                    },
                    "required": ["query"]
                }
            })

            # 2. Universal execute tool
            tools.append({
                "name": "ingrations_execute",
                "description": "Executes an action discovered via ingrations_search_tools.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action_id": {"type": "string", "description": "The action ID to execute, e.g. 'jira.create_issue'"},
                        "params": {"type": "object", "description": "Action parameter payload"},
                        "dry_run": {"type": "boolean", "description": "Simulate request without remote state change", "default": False}
                    },
                    "required": ["action_id"]
                }
            })

            # 3. Explicitly mounted apps
            for app_id in self.mounted_apps:
                app = self.client.get_app(app_id)
                if app:
                    for action in app.actions:
                        tools.append({
                            "name": action.id.replace(".", "_"),
                            "description": f"[{app.name}] {action.description}",
                            "inputSchema": action.to_json_schema()
                        })

            return JSONRPCResponse(id=req.id, result={"tools": tools})

        elif method == "tools/call":
            params = req.params or {}
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "ingrations_search_tools":
                q = arguments.get("query", "")
                cat = arguments.get("category")
                lim = int(arguments.get("limit", 5))
                results = self.client.search_tools(q, limit=lim, category=cat)
                formatted = [
                    {
                        "action_id": r.action_id,
                        "app_name": r.app_name,
                        "action_name": r.action_name,
                        "description": r.description,
                        "category": r.category
                    }
                    for r in results
                ]
                return JSONRPCResponse(
                    id=req.id,
                    result={
                        "content": [
                            {"type": "text", "text": json.dumps({"query": q, "results": formatted}, indent=2)}
                        ]
                    }
                )

            elif tool_name == "ingrations_execute":
                action_id = arguments.get("action_id", "")
                call_params = arguments.get("params", {})
                dry_run = bool(arguments.get("dry_run", False))
                res = await self.client.execute(action_id, params=call_params, dry_run=dry_run)
                return JSONRPCResponse(
                    id=req.id,
                    result={
                        "content": [
                            {"type": "text", "text": json.dumps(res.model_dump(), indent=2)}
                        ],
                        "isError": not res.success
                    }
                )

            else:
                # Mounted tool call
                norm_action = tool_name.replace("_", ".", 1)
                res = await self.client.execute(norm_action, params=arguments)
                return JSONRPCResponse(
                    id=req.id,
                    result={
                        "content": [
                            {"type": "text", "text": json.dumps(res.model_dump(), indent=2)}
                        ],
                        "isError": not res.success
                    }
                )

        return JSONRPCResponse(
            id=req.id,
            error={"code": -32601, "message": f"Method '{method}' not found"}
        )

    async def run_stdio(self) -> None:
        """Runs the MCP server over standard input / output."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        w_transport, w_protocol = await asyncio.get_event_loop().connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
        writer = asyncio.StreamWriter(w_transport, w_protocol, reader, asyncio.get_event_loop())

        while True:
            line = await reader.readline()
            if not line:
                break
            raw_text = line.decode("utf-8").strip()
            if not raw_text:
                continue

            try:
                data = json.loads(raw_text)
                req = JSONRPCRequest.model_validate(data)
                resp = await self.handle_request(req)
                resp_json = resp.model_dump_json(exclude_none=True) + "\n"
                writer.write(resp_json.encode("utf-8"))
                await writer.drain()
            except Exception as e:
                err_resp = JSONRPCResponse(
                    error={"code": -32700, "message": f"Parse error: {str(e)}"}
                )
                writer.write((err_resp.model_dump_json(exclude_none=True) + "\n").encode("utf-8"))
                await writer.drain()
