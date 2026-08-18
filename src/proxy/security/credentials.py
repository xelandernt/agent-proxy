from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr


class CredentialEncryptionUnavailable(RuntimeError):
    """Raised when model credential encryption is not configured."""


class InvalidCredentialCiphertext(ValueError):
    """Raised when stored credential ciphertext cannot be authenticated."""


class CredentialCipher:
    """Versioned authenticated encryption for provider credential maps."""

    _VERSION = "v1"

    def __init__(self, key: SecretStr | None) -> None:
        self._fernet: Fernet | None = None
        self._invalid_key = False
        if key is not None:
            try:
                self._fernet = Fernet(key.get_secret_value().encode())
            except (TypeError, ValueError):
                self._invalid_key = True

    @property
    def available(self) -> bool:
        return self._fernet is not None

    def encrypt(self, credentials: dict[str, str]) -> str:
        fernet = self._require_fernet()
        payload = json.dumps(
            credentials,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"{self._VERSION}.{fernet.encrypt(payload).decode()}"

    def decrypt(self, ciphertext: str) -> dict[str, str]:
        fernet = self._require_fernet()
        version, separator, token = ciphertext.partition(".")
        if version != self._VERSION or not separator or not token:
            raise InvalidCredentialCiphertext(
                "Unsupported provider credential ciphertext version."
            )
        try:
            decoded = json.loads(fernet.decrypt(token.encode()))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidCredentialCiphertext(
                "Provider credential ciphertext could not be authenticated."
            ) from error
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in decoded.items()
        ):
            raise InvalidCredentialCiphertext(
                "Provider credential ciphertext has an invalid payload."
            )
        return decoded

    def _require_fernet(self) -> Fernet:
        if self._fernet is None:
            if self._invalid_key:
                raise CredentialEncryptionUnavailable(
                    "The model credential encryption key is invalid."
                )
            raise CredentialEncryptionUnavailable(
                "Model credential encryption is not configured."
            )
        return self._fernet
