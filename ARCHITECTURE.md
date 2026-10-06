# Ingrations Architecture Specification

This document details the architectural decisions, design invariants, security model, and execution lifecycle of **Ingrations**.

---

## 1. Design Principles

1. **Zero Vendor Lock-in & Decentralization**: No proprietary cloud proxies. Actions execute directly from the host machine or container running the agent.
2. **Sub-Millisecond Discovery**: In-memory SQLite FTS5 enables sub-millisecond BM25 tool search, ensuring agents never have to load thousands of action schemas into their prompt context simultaneously.
3. **Pluggable & Model-Agnostic**: First-class serializers for Google Gemini (uppercase types), OpenAI (function calling), Anthropic Claude (inputSchema), and RFC JSON Schema.
4. **Local Cryptographic Security**: Credentials stored locally in an AES-128 Fernet encrypted vault with PBKDF2 key derivation. Zero credentials logged or transmitted to telemetry endpoints.
5. **Universal Protocol Standard**: Native Model Context Protocol (MCP) server compliance over standard JSON-RPC 2.0 stdio and SSE.

---

## 2. Core Subsystems

### Catalog & Schema Compilation (`ingrations.catalog` & `ingrations.compiler`)
The catalog is organized hierarchically by category:
- `catalog/devtools/`
- `catalog/productivity/`
- `catalog/cloud/`
- `catalog/crm_finance/`

The compiler (`OpenAPICompiler`) normalizes arbitrary OpenAPI 2.0 / 3.0 / 3.1 specifications into standard `AppSpec` and `ActionSpec` instances. It automatically detects parameter locations (`path`, `query`, `header`, `body`) and strips bloated recursive object definitions to protect LLM context windows.

### Semantic Tool Discovery (`ingrations.discovery`)
Instead of dumping 1,500 apps into a system prompt, Ingrations uses a two-tier discovery strategy:
1. The agent is equipped with the meta-tool `ingrations_search_tools`.
2. When the user requests an action (e.g. *"create a high-priority bug in Jira and notify the team on Slack"*), the agent issues searches for relevant tools.
3. The in-memory FTS5 virtual table matches against action IDs, app names, descriptions, and tags in `<2ms`.
4. Matching schemas are injected dynamically into the next conversational turn.

### Action Execution Engine (`ingrations.executor`)
`ActionExecutor` handles the HTTP lifecycle:
- Parameter routing: Automatically resolves path variable placeholders (`{owner}`, `{repo}`) and separates body from query parameters.
- Authentication injection: Applies the configured `AuthRequirement` (Bearer token, API Key header/query, Basic auth).
- Resilience: Retries transient errors (HTTP 429, 502, 503, 504) with exponential backoff.
- Dry-run capability: Simulates request payloads without making outbound network requests, ideal for automated testing and agent evaluation.

### Cryptographic Auth Vault (`ingrations.auth`)
- Backed by `~/.ingrations/vault.json`.
- Encryption: PBKDF2 HMAC SHA-256 with 100,000 iterations deriving a 256-bit key for Fernet AES-128-CBC encryption with HMAC authentication.
- Layered fallback: Memory -> Encrypted Vault -> Explicit Environment Variables (`GITHUB_TOKEN`, `LINEAR_API_KEY`) -> Conventional Environment Variables (`<APP>_API_KEY`, `<APP>_TOKEN`).

---

## 3. Execution Flow Diagram

```
User Prompt: "Open a pull request for feature branch"
                       │
                       ▼
               AI Agent (LLM)
                       │
                       ▼ calls ingrations_search_tools("open pull request")
             ToolDiscoveryEngine
                       │
                       ▼ returns ActionSpec(github.create_pull_request)
               AI Agent (LLM)
                       │
                       ▼ calls github_create_pull_request(...)
                 ActionExecutor
                 ├── Injects Auth from AuthManager (Vault/Env)
                 ├── Formats Path & JSON Body
                 └── Dispatches HTTP to https://api.github.com/repos/...
                       │
                       ▼
            GitHub API (Status 201 Created)
                       │
                       ▼
            ExecutionResult Returned to Agent
```
