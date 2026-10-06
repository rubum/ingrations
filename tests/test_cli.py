from click.testing import CliRunner
from ingrations.cli import main


def test_cli_list_apps():
    runner = CliRunner()
    result = runner.invoke(main, ["list-apps"])
    assert result.exit_code == 0
    assert "GitHub" in result.output
    assert "Linear" in result.output
    assert "Stripe" in result.output


def test_cli_search():
    runner = CliRunner()
    result = runner.invoke(main, ["search", "pull request"])
    assert result.exit_code == 0
    assert "github.create_pull_request" in result.output


def test_cli_show():
    runner = CliRunner()
    result = runner.invoke(main, ["show", "github.create_pull_request"])
    assert result.exit_code == 0
    assert "Action: github.create_pull_request" in result.output
    assert "Parameters:" in result.output


def test_cli_auth_set_and_clear():
    runner = CliRunner()
    res1 = runner.invoke(main, ["auth-set", "test_app", "test_secret_123"])
    assert res1.exit_code == 0
    assert "saved in vault" in res1.output

    res2 = runner.invoke(main, ["auth-list"])
    assert res2.exit_code == 0
    assert "test_app" in res2.output

    res3 = runner.invoke(main, ["auth-clear", "test_app"])
    assert res3.exit_code == 0
    assert "Removed credentials" in res3.output


def test_cli_exec_dry_run():
    runner = CliRunner()
    result = runner.invoke(main, [
        "exec",
        "github.create_pull_request",
        "--dry-run",
        "--params",
        '{"owner":"rubum","repo":"ingrations","title":"feat","head":"branch","base":"main"}'
    ])
    assert result.exit_code == 0
    assert "Status 200" in result.output
    assert '"dry_run": true' in result.output
