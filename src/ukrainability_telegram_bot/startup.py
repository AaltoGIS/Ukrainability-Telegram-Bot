"""Startup and session-recovery helpers."""

from __future__ import annotations

import sqlite3
import time

from .app import AppContext
from .pseudonym import hash_user_id
from .storage import initialize_database as initialize_storage_database


def initialize_database(ctx: AppContext) -> None:
    """Initialize the configured SQLite database."""

    try:
        initialize_storage_database(ctx.config.db_file)
        ctx.flow_logger.info("Database initialized successfully")
    except Exception as exc:
        ctx.flow_logger.exception(f"Error initializing responses database: {exc}")
        raise


def update_activity_timestamp(ctx: AppContext, user_id: int) -> None:
    """Update the last activity timestamp for a user session."""

    with ctx.sessions.lock:
        if user_id in ctx.sessions.data:
            ctx.sessions.data[user_id]["last_activity_time"] = time.time()
        else:
            ctx.sessions.data[user_id] = {"last_activity_time": time.time()}


def recover_user_sessions(ctx: AppContext) -> None:
    """Attempt to recover in-memory user sessions after a bot restart."""

    try:
        ctx.flow_logger.info("Attempting to recover user sessions...")
        with ctx.sessions.lock:
            users_to_recover = list(ctx.sessions.data.keys())
        recovered_count = 0

        for user_id in users_to_recover:
            try:
                with ctx.sessions.lock:
                    session = ctx.sessions.data.get(user_id, {})
                if "language" not in session:
                    language = _get_profile_value(ctx, user_id, "language")
                    if language:
                        _set_session_value(ctx, user_id, "language", language)
                    else:
                        continue

                current_session = _get_session(ctx, user_id)
                if "nickname" not in current_session:
                    user_hash = hash_user_id(user_id, ctx.config.user_hash_salt)
                    nickname = _get_latest_user_nickname(ctx, user_hash)
                    if nickname:
                        _set_session_value(ctx, user_id, "nickname", nickname)

                _set_session_value(ctx, user_id, "session_recovered", True)
                recovered_count += 1
                ctx.flow_logger.info(f"Recovered session for user {user_id}")
            except Exception as inner_exc:
                ctx.flow_logger.error(
                    f"Error recovering session for user {user_id}: {inner_exc}"
                )

        ctx.flow_logger.info(
            f"Session recovery complete. Recovered {recovered_count} sessions."
        )
    except Exception as exc:
        ctx.flow_logger.error(f"Error in session recovery process: {exc}")


def _get_session(ctx: AppContext, user_id: int) -> dict:
    with ctx.sessions.lock:
        return ctx.sessions.data.setdefault(user_id, {})


def _set_session_value(ctx: AppContext, user_id: int, key: str, value: object) -> None:
    with ctx.sessions.lock:
        ctx.sessions.data.setdefault(user_id, {})[key] = value


def _get_profile_value(ctx: AppContext, user_id: int, key: str) -> object | None:
    with ctx.sessions.lock:
        return ctx.sessions.profiles.setdefault(user_id, {}).get(key)


def _get_latest_user_nickname(ctx: AppContext, user_hash: str) -> str | None:
    with sqlite3.connect(ctx.config.db_file, check_same_thread=False) as conn:
        cursor = conn.execute(
            """
            SELECT nickname FROM user_nicknames
            WHERE user_hash = ?
            ORDER BY month_year DESC LIMIT 1
            """,
            (user_hash,),
        )
        row = cursor.fetchone()
    return row[0] if row else None
