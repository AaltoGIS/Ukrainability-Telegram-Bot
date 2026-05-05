"""Encryption helpers."""

from __future__ import annotations

from cryptography.fernet import Fernet, MultiFernet


def build_fernet(encryption_key: str, retiring_keys: list[str] | None = None) -> MultiFernet:
    """Validate keys and create a MultiFernet instance.

    The first key is active for new encryption. Additional keys are accepted for
    decryption, which allows gradual key rotation without orphaning old rows.
    """

    try:
        keys = [Fernet(encryption_key.encode())]
        keys.extend(Fernet(key.encode()) for key in retiring_keys or [])
        return MultiFernet(keys)
    except ValueError as exc:
        raise ValueError(f"Invalid encryption key: {exc}") from exc


def encrypt_text(fernet: MultiFernet, value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt_text(fernet: MultiFernet, value: str) -> str:
    return fernet.decrypt(value.encode()).decode()
