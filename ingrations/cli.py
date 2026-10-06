import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, List
import click
from ingrations.client import Ingrations
from ingrations.compiler import OpenAPICompiler
from ingrations.mcp.server import MCPServer


@click.group()
@click.version_option(version="0.1.0", prog_name="ingrations")
def main():
    """Ingrations: Open-source universal action infrastructure for AI agents."""
    pass


@main.command("list-apps")
@click.option("--category", "-c", help="Filter by category (devtools, productivity, cloud, crm_finance)")
def list_apps(category: Optional[str]):
    """Lists available software apps in the Ingrations catalog."""
    client = Ingrations()
    apps = client.list_apps(category)
    click.echo(f"\nAvailable Apps ({len(apps)} total):\n")
    for a in apps:
        configured = client.auth.is_configured(a.id, a.auth.env_vars)
        status_badge = click.style(" [Configured] ", fg="green", bold=True) if configured else click.style(" [Not configured] ", fg="yellow")
        click.echo(f" • {click.style(a.name, bold=True)} ({a.id}) - {status_badge} [{a.category}]")
        click.echo(f"   {a.description}")
        click.echo(f"   Actions: {len(a.actions)} available\n")


@main.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=5, help="Number of results to return")
@click.option("--category", "-c", help="Filter by category")
def search(query: str, limit: int, category: Optional[str]):
    """Performs semantic BM25 tool discovery for natural language keywords."""
    client = Ingrations()
    results = client.search_tools(query, limit=limit, category=category)
    click.echo(f"\nSearch results for '{query}' ({len(results)} matches):\n")
    for r in results:
        click.echo(f" • {click.style(r.action_id, fg='cyan', bold=True)} ({r.app_name}) - Score: {r.score:.2f}")
        click.echo(f"   {r.description}\n")


@main.command("show")
@click.argument("action_id")
def show(action_id: str):
    """Inspects detailed schema, method, parameters, and auth for an action."""
    client = Ingrations()
    action = client.get_action(action_id)
    if not action:
        click.echo(f"Error: Action '{action_id}' not found.", err=True)
        sys.exit(1)

    app = client.get_app(action.app_id)
    click.echo(f"\nAction: {click.style(action.id, bold=True, fg='cyan')}")
    click.echo(f"App: {app.name if app else action.app_id} ({action.method.value} {action.path})")
    click.echo(f"Description: {action.description}\n")

    click.echo("Parameters:")
    for p in action.parameters:
        req = click.style("[Required]", fg="red") if p.required else "[Optional]"
        click.echo(f" • {p.name} ({p.type}, {p.location.value}) {req}: {p.description}")
    click.echo("")


@main.command("auth-list")
def auth_list():
    """Lists apps with active stored credentials in local encrypted vault."""
    client = Ingrations()
    apps = client.auth.list_configured_apps()
    click.echo(f"\nConfigured Apps in Local Vault ({len(apps)} total):\n")
    if not apps:
        click.echo("  (No stored credentials. Use 'ingrations auth-set <app_id> <token>' to store keys)")
    for aid in apps:
        click.echo(f" • {click.style(aid, bold=True, fg='green')}")
    click.echo("")


@main.command("auth-set")
@click.argument("app_id")
@click.argument("token")
def auth_set(app_id: str, token: str):
    """Stores an API key, PAT, or Bearer token securely in local encrypted vault."""
    client = Ingrations()
    client.auth.set_credential(app_id, token)
    click.echo(click.style(f"✓ Credential for '{app_id}' encrypted and saved in vault.", fg="green", bold=True))


@main.command("auth-clear")
@click.argument("app_id")
def auth_clear(app_id: str):
    """Removes a stored credential from local vault."""
    client = Ingrations()
    removed = client.auth.remove_credential(app_id)
    if removed:
        click.echo(f"✓ Removed credentials for '{app_id}'.")
    else:
        click.echo(f"No stored credentials found for '{app_id}'.")


@main.command("exec")
@click.argument("action_id")
@click.option("--params", "-p", help="JSON string of parameter values", default="{}")
@click.option("--dry-run", is_flag=True, help="Simulate request without executing live API call")
def execute_action(action_id: str, params: str, dry_run: bool):
    """Executes an action directly from the command line."""
    try:
        parsed_params = json.loads(params)
    except Exception as e:
        click.echo(f"Invalid JSON in --params: {e}", err=True)
        sys.exit(1)

    client = Ingrations()
    result = asyncio.run(client.execute(action_id, params=parsed_params, dry_run=dry_run))

    if result.success:
        click.echo(click.style(f"\n✓ Status {result.status_code} ({result.duration_ms:.1f}ms):", fg="green", bold=True))
        click.echo(json.dumps(result.data, indent=2))
    else:
        click.echo(click.style(f"\n✗ Failed with status {result.status_code} ({result.duration_ms:.1f}ms):", fg="red", bold=True))
        click.echo(result.error)
        sys.exit(1)


@main.command("compile")
@click.argument("openapi_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", "-o", type=click.Path(path_type=Path), help="Target catalog directory")
def compile_openapi(openapi_file: Path, output_dir: Optional[Path]):
    """Compiles an OpenAPI specification into normalized Ingrations catalog spec."""
    out = output_dir or (Path(__file__).parent.parent / "catalog")
    app_spec = OpenAPICompiler.compile_file(openapi_file)
    exported = OpenAPICompiler.export_to_catalog(app_spec, out)
    click.echo(click.style(f"✓ Compiled {len(app_spec.actions)} actions for '{app_spec.name}' into {exported}", fg="green"))


@main.command("mcp-serve")
@click.option("--apps", "-a", help="Comma-separated app IDs to mount as explicit tools (e.g. 'github,linear')")
def mcp_serve(apps: Optional[str]):
    """Runs Ingrations Model Context Protocol (MCP) server over stdio."""
    mounted = [a.strip() for a in apps.split(",")] if apps else []
    server = MCPServer(mounted_apps=mounted)
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
