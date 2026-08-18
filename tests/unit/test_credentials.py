from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from proxy.security.credentials import (
    CredentialCipher,
    CredentialEncryptionUnavailable,
    InvalidCredentialCiphertext,
)


def cipher() -> CredentialCipher:
    return CredentialCipher(SecretStr(Fernet.generate_key().decode()))


def test_credentials_round_trip_without_plaintext_in_ciphertext() -> None:
    codec = cipher()
    credentials = {"api_key": "super-secret", "unicode": "Grüße"}

    encrypted = codec.encrypt(credentials)

    assert encrypted.startswith("v1.")
    assert "super-secret" not in encrypted
    assert codec.decrypt(encrypted) == credentials


def test_credentials_reject_tampering_and_unknown_versions() -> None:
    codec = cipher()
    encrypted = codec.encrypt({"api_key": "secret"})

    with pytest.raises(InvalidCredentialCiphertext):
        codec.decrypt(encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B"))
    with pytest.raises(InvalidCredentialCiphertext, match="version"):
        codec.decrypt("v2.invalid")


def test_credentials_are_unavailable_without_configuration() -> None:
    codec = CredentialCipher(None)

    assert codec.available is False
    with pytest.raises(CredentialEncryptionUnavailable):
        codec.encrypt({})


def test_invalid_key_keeps_mcp_only_gateway_startable() -> None:
    codec = CredentialCipher(SecretStr("not-a-fernet-key"))

    assert codec.available is False
    with pytest.raises(CredentialEncryptionUnavailable, match="invalid"):
        codec.encrypt({})
