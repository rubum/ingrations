from ingrations.discovery import ToolDiscoveryEngine


def test_discovery_indexing_and_search(discovery: ToolDiscoveryEngine):
    # Search for pull request
    results = discovery.search("create pull request", limit=5)
    assert len(results) > 0
    top_id = results[0].action_id
    assert "pull_request" in top_id or "merge_request" in top_id


def test_discovery_category_filter(discovery: ToolDiscoveryEngine):
    results = discovery.search("issue", category="devtools")
    for r in results:
        assert r.category == "devtools"


def test_discovery_meta_tool_declaration():
    decl = ToolDiscoveryEngine.get_search_tool_declaration()
    assert decl["name"] == "ingrations_search_tools"
    assert "query" in decl["parameters"]["required"]
    assert "category" in decl["parameters"]["properties"]
