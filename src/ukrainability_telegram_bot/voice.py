"""Voice-message file helpers."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

_SAFE_NICKNAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ]*")


def safe_nickname_directory(base_dir: str | Path, nickname: str) -> Path:
    """Return the user's voice directory after validating the nickname."""

    if not _SAFE_NICKNAME_RE.fullmatch(nickname or ""):
        raise ValueError("Unsafe nickname for voice file path")
    return Path(base_dir) / nickname


def new_voice_filename(nickname: str) -> str:
    if not _SAFE_NICKNAME_RE.fullmatch(nickname or ""):
        raise ValueError("Unsafe nickname for voice filename")
    return f"{nickname} {secrets.token_hex(8)}.enc"
