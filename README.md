<p align="center">
  <h1 align="center">Ingrations</h1>
  <p align="center"><strong>Open-source universal action infrastructure and tool integrations for AI agents.</strong></p>
</p>

<p align="center">
  <a href="https://github.com/rubum/ingrations/actions"><img src="https://img.shields.io/badge/CI-passing-brightgreen.svg" alt="CI Status"></a>
  <a href="https://pypi.org/project/ingrations/"><img src="https://img.shields.io/badge/pypi-v0.1.0-blue.svg" alt="PyPI version"></a>
  <a href="https://github.com/rubum/ingrations/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
</p>

---

## What is Ingrations?

**Ingrations** is a fully open-source, vendor-agnostic tool integration infrastructure that connects AI agents to hundreds of software applications and APIs—without tying you to closed, proprietary execution proxies or paid monthly SaaS tiers.

While existing platforms gate their action specifications and execution servers behind closed backends, Ingrations provides:

- 🌐 **Open Action Catalog**: Clean, normalized, and token-optimized action specifications for GitHub, Linear, Jira, Slack, Notion, Discord, Google Workspace, AWS, Supabase, Cloudflare, Datadog, Stripe, Salesforce, HubSpot, and GitLab.
- ⚡ **Sub-Millisecond Semantic Tool Discovery**: In-memory SQLite FTS5 full-text search allowing agents to discover and mount matching tools across thousands of actions without prompt token bloat.
- 🔒 **Encrypted Local Vault & BYOK Auth**: AES-128 Fernet encrypted credential vault (`~/.ingrations/vault.json`) with zero third-party telemetry. Your API tokens stay strictly on your machine.
- 🔌 **Universal Model Context Protocol (MCP)**: Native stdio and SSE server (`ingrations mcp-serve`) ready to attach to Anthropic Claude Desktop, Cursor, Antigravity, and custom agent loops.
- 🛠️ **OpenAPI 3.0 / 3.1 Compiler**: Automatic ingestion engine that turns any raw Swagger or OpenAPI JSON/YAML document into a validated, token-pruned Ingrations app toolkit.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             AI Agent Runtime                             │
│       (Claude, OpenAI, Gemini, LangChain, CrewAI, Custom Loop)           │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ Queries tools / Dispatches calls
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                            Ingrations Engine                             │
├────────────────────────────────────┬─────────────────────────────────────┤
│ ToolDiscoveryEngine (FTS5 / BM25)  │ ActionExecutor (httpx async runner) │
│  - Instant sub-ms tool matching    │  - Path & body interpolation        │
│  - Prevents prompt token overload  │  - Retry with exponential backoff   │
├────────────────────────────────────┼─────────────────────────────────────┤
│ Catalog (AppSpec & ActionSpec)     │ AuthManager (Encrypted Vault)       │
│  - Developer Tools (Git, Issues)   │  - Fernet AES-128 local storage     │
│  - Cloud & Infra (AWS, Supabase)   │  - Zero cloud proxy dependency      │
│  - Productivity (Slack, Notion)    │  - Environment variable fallback    │
└────────────────────────────────────┴─────────────────────────────────────┘
```

---

## Installation

```bash
pip install ingrations
```

Or install from source:

```bash
git clone https://github.com/rubum/ingrations.git
cd ingrations
pip install -e .
```

---

## Quickstart

### 1. Python SDK

```python
import asyncio
from ingrations import Ingrations

async def main():
    client = Ingrations()

    # 1. Discover tools dynamically
    matches = client.search_tools("create pull request")
    for m in matches:
        print(f"[{m.score:.2f}] {m.action_id}: {m.description}")

    # 2. Export schemas for your LLM (Gemini, OpenAI, Claude, or standard JSON Schema)
    gemini_schemas = client.get_tool_declarations(app_ids=["github"], format="gemini")
    openai_schemas = client.get_tool_declarations(app_ids=["github"], format="openai")
    claude_schemas = client.get_tool_declarations(app_ids=["github"], format="claude")

    # 3. Execute an action
    result = await client.execute(
        action_id="github.create_pull_request",
        params={
            "owner": "rubum",
            "repo": "ingrations",
            "title": "Add Webhook Support",
            "head": "feature-branch",
            "base": "main"
        },
        dry_run=True  # Simulate without sending live request
    )
    print(result.data)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Command Line Interface (CLI)

The `ingrations` CLI provides full management of your local action infrastructure:

### List Available Apps & Status
```bash
ingrations list-apps
ingrations list-apps --category devtools
```

### Search Tools with Semantic BM25 Ranking
```bash
ingrations search "send slack message"
ingrations search "stripe refund customer charge"
```

### Inspect Action Schema & Parameters
```bash
ingrations show github.create_pull_request
```

### Manage Credentials Securely
```bash
# Encrypt and store token in ~/.ingrations/vault.json
ingrations auth-set github ghp_yourSecretTokenHere
ingrations auth-set linear lin_api_yourKeyHere

# List configured apps
ingrations auth-list

# Remove credential
ingrations auth-clear github
```

### Execute Action from Terminal
```bash
# Dry run simulation
ingrations exec github.create_pull_request --dry-run --params '{"owner":"rubum","repo":"ingrations","title":"New Feature","head":"feat","base":"main"}'

# Live execution
ingrations exec slack.post_message --params '{"channel":"C12345","text":"Deployment finished successfully!"}'
```

---

## Model Context Protocol (MCP) Server

Ingrations natively implements the Model Context Protocol. You can connect it to Cursor, Claude Desktop, Antigravity, or any MCP client:

### Run MCP Server
```bash
# Serves universal discovery and execution tools over stdio
ingrations mcp-serve

# Or pre-mount explicit app toolkits
ingrations mcp-serve --apps github,linear,slack
```

### Claude Desktop Configuration (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "ingrations": {
      "command": "ingrations",
      "args": ["mcp-serve", "--apps", "github,linear,slack"]
    }
  }
}
```

---

## Compiling Custom OpenAPI Specs

Ingrations includes an automated OpenAPI 3.0 / 3.1 compiler. Turn any public API documentation into a ready-to-use Ingrations toolkit:

```bash
ingrations compile path/to/openapi.yaml --output-dir catalog/
```

Programmatic compilation:

```python
from pathlib import Path
from ingrations.compiler import OpenAPICompiler

app_spec = OpenAPICompiler.compile_file(Path("my_service_openapi.json"))
print(f"Generated {len(app_spec.actions)} actions for {app_spec.name}")
```

---

## Supported Integrations

| Category | Apps & Toolkits | Status |
| :--- | :--- | :--- |
| **Developer Tools** | GitHub, Linear, Jira Software, GitLab, Sentry, AppSignal | ✅ Ready |
| **Productivity** | Slack, Notion, Discord, Google Workspace (Gmail, Calendar, Drive) | ✅ Ready |
| **Cloud & Infrastructure** | Amazon Web Services (AWS), Supabase, Cloudflare, Datadog | ✅ Ready |
| **CRM & Finance** | Stripe, Salesforce, HubSpot | ✅ Ready |

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
