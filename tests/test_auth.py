import os
from pathlib import Path
from ingrations.auth import AuthManager


def test_auth_manager_set_and_get(test_vault: AuthManager):
    assert test_vault.get_credential("github") is None

    test_vault.set_credential("github", "ghp_secrettoken123")
    assert test_vault.get_credential("github") == "ghp_secrettoken123"
    assert test_vault.is_configured("github") is True


def test_auth_manager_persistence(tmp_path: Path):
    vault_file = tmp_path / "persisted_vault.json"
    auth1 = AuthManager(vault_path=vault_file, passphrase="my-key-phrase")
    auth1.set_credential("linear", "lin_api_key_456")

    assert vault_file.exists()
    # Confirm file is encrypted (not plain text)
    with open(vault_file, "rb") as f:
        raw_bytes = f.read()
    assert b"lin_api_key_456" not in raw_bytes

    # Second manager loading same file
    auth2 = AuthManager(vault_path=vault_file, passphrase="my-key-phrase")
    assert auth2.get_credential("linear") == "lin_api_key_456"


def test_auth_manager_env_fallback(test_vault: AuthManager, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env_token_from_system")
    val = test_vault.get_credential("github", env_vars=["GITHUB_TOKEN"])
    assert val == "env_token_from_system"

    # Vault token takes precedence
    test_vault.set_credential("github", "vault_token_override")
    assert test_vault.get_credential("github", env_vars=["GITHUB_TOKEN"]) == "vault_token_override"


def test_auth_manager_remove_credential(test_vault: AuthManager):
    test_vault.set_credential("slack", "xoxb-test")
    assert test_vault.is_configured("slack") is True
    assert test_vault.remove_credential("slack") is True
    assert test_vault.is_configured("slack") is False
