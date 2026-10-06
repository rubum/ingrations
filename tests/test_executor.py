import pytest
import httpx
from ingrations.catalog import Catalog
from ingrations.executor import ActionExecutor
from ingrations.auth import AuthManager


@pytest.mark.asyncio
async def test_executor_dry_run(catalog: Catalog, test_vault: AuthManager):
    executor = ActionExecutor(test_vault)
    test_vault.set_credential("github", "ghp_dryrun_token")

    app = catalog.get_app("github")
    action = catalog.get_action("github.create_issue")

    result = await executor.execute(
        app=app,
        action=action,
        params={
            "owner": "rubum",
            "repo": "ingrations",
            "title": "Support webhooks",
            "body": "Add webhook receiver"
        },
        dry_run=True
    )

    assert result.success is True
    assert result.status_code == 200
    assert result.data["dry_run"] is True
    assert result.data["method"] == "POST"
    assert "https://api.github.com/repos/rubum/ingrations/issues" in result.data["url"]
    assert result.data["body"]["title"] == "Support webhooks"
    assert result.data["headers"]["Authorization"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_executor_missing_path_param(catalog: Catalog, test_vault: AuthManager):
    executor = ActionExecutor(test_vault)
    app = catalog.get_app("github")
    action = catalog.get_action("github.create_issue")

    # Missing repo parameter
    result = await executor.execute(
        app=app,
        action=action,
        params={"owner": "rubum"},
        dry_run=True
    )

    assert result.success is False
    assert result.status_code == 400
    assert "Missing required path parameter" in result.error


@pytest.mark.asyncio
async def test_executor_mock_http_execution(catalog: Catalog, test_vault: AuthManager):
    executor = ActionExecutor(test_vault)
    test_vault.set_credential("github", "ghp_mock_token")

    app = catalog.get_app("github")
    action = catalog.get_action("github.get_repo")

    # Create MockTransport
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer ghp_mock_token"
        assert "repos/rubum/ingrations" in str(request.url)
        return httpx.Response(
            status_code=200,
            json={"id": 999, "name": "ingrations", "full_name": "rubum/ingrations"}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await executor.execute(
            app=app,
            action=action,
            params={"owner": "rubum", "repo": "ingrations"},
            client=client
        )

    assert result.success is True
    assert result.status_code == 200
    assert result.data["name"] == "ingrations"
