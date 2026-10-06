import pytest
from pathlib import Path
from ingrations.catalog import Catalog
from ingrations.auth import AuthManager
from ingrations.discovery import ToolDiscoveryEngine
from ingrations.client import Ingrations


@pytest.fixture
def test_vault(tmp_path: Path) -> AuthManager:
    vault_file = tmp_path / "test_vault.json"
    return AuthManager(vault_path=vault_file, passphrase="test-passphrase-secure")


@pytest.fixture
def catalog() -> Catalog:
    cat = Catalog()
    cat.load()
    return cat


@pytest.fixture
def discovery(catalog: Catalog) -> ToolDiscoveryEngine:
    engine = ToolDiscoveryEngine(catalog)
    engine.build_index(force=True)
    return engine


@pytest.fixture
def client(test_vault: AuthManager) -> Ingrations:
    c = Ingrations()
    c.auth = test_vault
    return c
