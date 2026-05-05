"""Startup and session-recovery helpers."""

from __future__ import annotations

from .app import AppContext
from .pseudonym import hash_user_id
from .storage import get_latest_user_nickname
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

    ctx.sessions.update_activity(user_id)


def recover_user_sessions(ctx: AppContext) -> None:
    """Attempt to recover in-memory user sessions after a bot restart."""

    try:
        ctx.flow_logger.info("Attempting to recover user sessions...")
        users_to_recover = ctx.sessions.all_user_ids()
        recovered_count = 0

        for user_id in users_to_recover:
            try:
                if ctx.sessions.get_data(user_id, "language") is None:
                    language = ctx.sessions.get_profile(user_id, "language")
                    if not language:
                        continue
                    ctx.sessions.set_data(user_id, "language", language)

                if ctx.sessions.get_data(user_id, "nickname") is None:
                    user_hash = hash_user_id(user_id, ctx.config.user_hash_salt)
                    nickname = get_latest_user_nickname(ctx.config.db_file, user_hash)
                    if nickname:
                        ctx.sessions.set_data(user_id, "nickname", nickname)

                ctx.sessions.set_data(user_id, "session_recovered", True)
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
