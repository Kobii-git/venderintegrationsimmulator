import base64
import hashlib
import secrets
from typing import Any

from app.core.config import get_settings
from cryptography.fernet import Fernet, InvalidToken

SECRET_FIELD_NAMES = frozenset({"password", "token", "oauth_client_secret"})
ENCRYPTED_SUFFIX = "_encrypted"


class SecretEncryptor:
    """Encrypt and decrypt secret fields in auth configuration."""

    def __init__(self, secret_key: str) -> None:
        derived = hashlib.sha256(secret_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt secret value") from exc

    def encrypt_auth_config(self, auth_config: dict[str, Any]) -> dict[str, Any]:
        stored = dict(auth_config)
        for field in SECRET_FIELD_NAMES:
            encrypted_key = f"{field}{ENCRYPTED_SUFFIX}"
            if field not in stored:
                continue
            value = stored.pop(field)
            if value is None:
                stored.pop(encrypted_key, None)
            else:
                stored[encrypted_key] = self.encrypt(str(value))
        return stored

    def decrypt_auth_config(self, stored: dict[str, Any]) -> dict[str, Any]:
        result = dict(stored)
        for field in SECRET_FIELD_NAMES:
            encrypted_key = f"{field}{ENCRYPTED_SUFFIX}"
            if encrypted_key in result and result[encrypted_key] is not None:
                result[field] = self.decrypt(str(result[encrypted_key]))
                del result[encrypted_key]
        return result

    def sanitize_auth_config_for_api(self, stored: dict[str, Any]) -> dict[str, Any]:
        """Return auth config safe for API responses (no secret values)."""
        public: dict[str, Any] = {}
        for key, value in stored.items():
            if key.endswith(ENCRYPTED_SUFFIX):
                base_field = key[: -len(ENCRYPTED_SUFFIX)]
                public[f"has_{base_field}"] = value is not None
                continue
            if key in SECRET_FIELD_NAMES:
                public[f"has_{key}"] = value is not None
                continue
            public[key] = value
        return public

    def merge_auth_config_update(
        self,
        existing: dict[str, Any],
        update: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge an auth config update, preserving secrets not provided."""
        decrypted_existing = self.decrypt_auth_config(existing) if existing else {}
        merged = {**decrypted_existing, **update}
        for field in SECRET_FIELD_NAMES:
            if field in update and update[field] is None:
                merged[field] = None
        return self.encrypt_auth_config(merged)


def resolve_secret_key() -> str:
    """Load or generate the application secret key."""
    settings = get_settings()
    if settings.secret_key:
        return settings.secret_key

    key_file = settings.resolved_data_dir / ".secret_key"
    if key_file.is_file():
        return key_file.read_text(encoding="utf-8").strip()

    generated = secrets.token_urlsafe(32)
    settings.ensure_data_dir()
    key_file.write_text(generated, encoding="utf-8")
    key_file.chmod(0o600)
    return generated


def get_secret_encryptor() -> SecretEncryptor:
    return SecretEncryptor(resolve_secret_key())
