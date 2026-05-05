"""Survey response persistence helpers."""

from __future__ import annotations

import datetime
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cryptography.fernet import MultiFernet

from ..app import AppContext
from ..storage import ENCRYPTED_COLUMNS, insert_response


class EncryptionUnavailableError(RuntimeError):
    """Raised when a response cannot be encrypted before storage."""


class DatabaseSaveError(RuntimeError):
    """Raised when all response insert attempts fail."""


def _join_response_value(value: Any, *, empty_if_missing: bool = False) -> str:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if empty_if_missing and not value:
        return ""
    return str(value)


def build_response_row(
    snapshot: dict[str, Any],
    profile_snapshot: dict[str, Any],
    *,
    language: str,
    nickname: str,
    now: datetime.datetime | None = None,
) -> dict[str, str]:
    """Build the plaintext response row from session/profile snapshots."""

    current_time = now or datetime.datetime.now()
    location_data = snapshot.get("location", {}) or {}
    kremenchuk_value = snapshot.get("kremenchuk", "") or profile_snapshot.get("kremenchuk", "")

    return {
        "nickname": nickname,
        "month_year": current_time.strftime("%Y-%m"),
        "latitude": str(location_data.get("latitude", "")),
        "longitude": str(location_data.get("longitude", "")),
        "venue_title": location_data.get("venue_title", ""),
        "venue_address": location_data.get("venue_address", ""),
        "enjoyment": snapshot.get("enjoyment", ""),
        "purpose_visit": _join_response_value(snapshot.get("purpose_visit", [])),
        "regularity": snapshot.get("regularity", ""),
        "noticed_changes": snapshot.get("noticed_changes", ""),
        "changes_detail": _join_response_value(snapshot.get("changes_detail", [])),
        "wishlist": _join_response_value(snapshot.get("wishlist", []), empty_if_missing=True),
        "kremenchuk": _join_response_value(kremenchuk_value),
        "description": snapshot.get("description", ""),
        "voice_submitted": snapshot.get("voice_submitted", ""),
        "age": snapshot.get("age", ""),
        "gender": snapshot.get("gender", ""),
        "occupation": snapshot.get("occupation", ""),
        "income": snapshot.get("income", ""),
        "language": language,
        "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        "visitor_type": _join_response_value(snapshot.get("visitor_type", [])),
        "duration_visit": snapshot.get("duration_visit", ""),
        "accessibility": _join_response_value(
            snapshot.get("accessibility", []), empty_if_missing=True
        ),
        "consent": "True",
    }


def encrypt_row(
    fernet: MultiFernet,
    row: dict[str, str],
    *,
    logger: Any | None = None,
) -> dict[str, str]:
    """Encrypt all configured response columns while preserving plaintext columns."""

    encrypted = dict(row)
    encryption_errors: list[str] = []
    for field in ENCRYPTED_COLUMNS:
        try:
            if encrypted[field]:
                encrypted[field] = fernet.encrypt(encrypted[field].encode()).decode()
            else:
                encrypted[field] = ""
        except Exception as exc:
            if logger is not None:
                logger.error(f"Error encrypting {field}: {exc}")
            encryption_errors.append(field)
            encrypted[field] = ""

    if encryption_errors and logger is not None:
        logger.error(f"Failed to encrypt fields: {encryption_errors}")
    return encrypted


def save_response(
    ctx: AppContext,
    user_id: int,
    language: str,
    *,
    nickname_provider: Callable[[], str],
    max_db_attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Persist a user's response snapshot.

    Returns True when persistence can proceed or is intentionally skipped for
    denied consent. Raises explicit exceptions for user-facing error handling
    in the bot layer.
    """

    with ctx.sessions.lock:
        snapshot = ctx.sessions.snapshot(user_id)
        profile_snapshot = ctx.sessions.profile_snapshot(user_id)
        user_consent = profile_snapshot.get("consent", False)

    if not user_consent:
        ctx.flow_logger.info("Consent denied; skipping response row insert")
        return True

    if ctx.fernet is None:
        raise EncryptionUnavailableError("Encryption not initialized")

    row = build_response_row(
        snapshot,
        profile_snapshot,
        language=language,
        nickname=nickname_provider(),
    )
    encrypted_row = encrypt_row(ctx.fernet, row, logger=ctx.flow_logger)

    db_file = Path(ctx.config.db_file)
    db_connection_attempts = 0
    while db_connection_attempts < max_db_attempts:
        db_connection_attempts += 1
        try:
            last_id = insert_response(db_file, encrypted_row)
            ctx.flow_logger.info(f"Inserted row ID: {last_id}")
            return True
        except sqlite3.Error as db_error:
            ctx.flow_logger.error(f"Database error attempt {db_connection_attempts}: {db_error}")
            if db_connection_attempts < max_db_attempts:
                retry_delay = 2 ** (db_connection_attempts - 1)
                ctx.flow_logger.info(f"Retrying database operation in {retry_delay} seconds")
                sleep(retry_delay)
            else:
                ctx.flow_logger.error("All database attempts failed, cannot save data")
                raise DatabaseSaveError("All database attempts failed") from db_error

    raise DatabaseSaveError("All database attempts failed")
