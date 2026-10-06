from ingrations.catalog import Catalog
from ingrations.models import AppSpec, ActionSpec, HTTPMethod


def test_catalog_loads_default_apps(catalog: Catalog):
    apps = catalog.list_apps()
    assert len(apps) >= 16
    assert catalog.total_actions >= 70

    github = catalog.get_app("github")
    assert github is not None
    assert github.name == "GitHub"
    assert github.category == "devtools"

    linear = catalog.get_app("linear")
    assert linear is not None
    assert linear.name == "Linear"


def test_catalog_category_filtering(catalog: Catalog):
    devtools = catalog.list_apps(category="devtools")
    assert any(a.id == "github" for a in devtools)
    assert any(a.id == "jira" for a in devtools)
    assert not any(a.id == "stripe" for a in devtools)

    finance = catalog.list_apps(category="crm_finance")
    assert any(a.id == "stripe" for a in finance)


def test_catalog_action_lookup(catalog: Catalog):
    action = catalog.get_action("github.create_pull_request")
    assert action is not None
    assert action.method == HTTPMethod.POST
    assert "/pulls" in action.path

    missing = catalog.get_action("nonexistent.action")
    assert missing is None


def test_register_custom_app(catalog: Catalog):
    custom_app = AppSpec(
        id="custom_tool",
        name="Custom Tool",
        description="A user-defined local tool",
        base_url="https://api.custom.dev",
        actions=[
            ActionSpec(
                id="custom_tool.ping",
                name="Ping",
                description="Checks connection",
                app_id="custom_tool",
                method=HTTPMethod.GET,
                path="/ping"
            )
        ]
    )
    catalog.register_app(custom_app)
    assert catalog.get_app("custom_tool") is not None
    assert catalog.get_action("custom_tool.ping") is not None
