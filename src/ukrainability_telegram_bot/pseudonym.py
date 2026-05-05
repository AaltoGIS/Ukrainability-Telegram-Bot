"""Pseudonymous identifiers for Telegram users."""

from __future__ import annotations

import hmac
from hashlib import sha256


def hash_user_id(user_id: int, salt: str) -> str:
    """Hash a Telegram user ID with a per-deployment secret salt."""

    if not salt:
        raise ValueError("A non-empty user hash salt is required")
    return hmac.new(salt.encode(), str(user_id).encode(), sha256).hexdigest()
