import os
import json
import base64
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger("ingrations.auth")

DEFAULT_VAULT_PATH = Path.home() / ".ingrations" / "vault.json"


class AuthManager:
    """
    Manages encrypted credential storage, environment variable fallbacks,
    and ephemeral local OAuth handshakes.
    """

    def __init__(self, vault_path: Optional[Path] = None, passphrase: Optional[str] = None):
        self.vault_path = vault_path or DEFAULT_VAULT_PATH
        self._passphrase = passphrase or os.environ.get("INGRATIONS_PASSPHRASE", "ingrations-default-salt-2026")
        self._fernet = self._derive_cipher(self._passphrase)
        self._memory_credentials: Dict[str, Dict[str, Any]] = {}
        self._load_vault()

    def _derive_cipher(self, passphrase: str) -> Fernet:
        salt = b"ingrations-vault-salt-static"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return Fernet(key)

    def _load_vault(self) -> None:
        if not self.vault_path.exists():
            return
        try:
            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                return
            decrypted = self._fernet.decrypt(encrypted_data).decode("utf-8")
            self._memory_credentials = json.loads(decrypted)
        except Exception as e:
            logger.warning(f"Could not decrypt vault at '{self.vault_path}': {e}")
            self._memory_credentials = {}

    def _save_vault(self) -> None:
        try:
            self.vault_path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(self._memory_credentials).encode("utf-8")
            encrypted = self._fernet.encrypt(payload)
            with open(self.vault_path, "wb") as f:
                f.write(encrypted)
        except Exception as e:
            logger.error(f"Failed to write encrypted credentials to '{self.vault_path}': {e}")

    def set_credential(
        self,
        app_id: str,
        token: str,
        metadata: Optional[Dict[str, Any]] = None,
        persist: bool = True
    ) -> None:
        """Stores a credential for a given app ID."""
        clean_app = app_id.lower().strip()
        data = {
            "token": token.strip(),
            "metadata": metadata or {}
        }
        self._memory_credentials[clean_app] = data
        if persist:
            self._save_vault()

    def get_credential(self, app_id: str, env_vars: Optional[List[str]] = None) -> Optional[str]:
        """
        Retrieves active credential for an app ID.
        Checks in-memory/vault first, then falls back to environment variables.
        """
        clean_app = app_id.lower().strip()
        entry = self._memory_credentials.get(clean_app)
        if entry and entry.get("token"):
            return entry["token"]

        # Check explicit env vars
        if env_vars:
            for ev in env_vars:
                val = os.environ.get(ev)
                if val and val.strip():
                    return val.strip()

        # Check conventional env var
        conv = f"{clean_app.upper()}_API_KEY"
        if os.environ.get(conv):
            return os.environ[conv].strip()

        conv_token = f"{clean_app.upper()}_TOKEN"
        if os.environ.get(conv_token):
            return os.environ[conv_token].strip()

        return None

    def remove_credential(self, app_id: str) -> bool:
        """Removes a stored credential from vault."""
        clean_app = app_id.lower().strip()
        if clean_app in self._memory_credentials:
            del self._memory_credentials[clean_app]
            self._save_vault()
            return True
        return False

    def is_configured(self, app_id: str, env_vars: Optional[List[str]] = None) -> bool:
        return self.get_credential(app_id, env_vars) is not None

    def list_configured_apps(self) -> List[str]:
        return list(self._memory_credentials.keys())

    def clear(self) -> None:
        self._memory_credentials.clear()
        if self.vault_path.exists():
            try:
                self.vault_path.unlink()
            except Exception:
                pass


# Global singleton auth manager
default_auth_manager = AuthManager()
