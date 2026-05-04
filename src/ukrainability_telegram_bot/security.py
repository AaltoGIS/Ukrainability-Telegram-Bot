"""Encryption helpers."""

from __future__ import annotations

from cryptography.fernet import Fernet


def build_fernet(encryption_key: str) -> Fernet:
    """Validate and create a Fernet instance from a text key."""

    try:
        return Fernet(encryption_key.encode())
    except ValueError as exc:
        raise ValueError(f"Invalid encryption key: {exc}") from exc


def encrypt_text(fernet: Fernet, value: str) -> str:
    return fernet.encrypt(value.encode()).decode()
