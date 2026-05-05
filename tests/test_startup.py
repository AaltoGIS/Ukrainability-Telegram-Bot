import sqlite3
from dataclasses import replace

from ukrainability_telegram_bot import startup
from ukrainability_telegram_bot.pseudonym import hash_user_id
from ukrainability_telegram_bot.storage import save_user_nickname


def test_initialize_database_creates_tables(tmp_path, app_context):
    app_context.config = replace(app_context.config, storage_dir=tmp_path / "storage")

    startup.initialize_database(app_context)

    with sqlite3.connect(app_context.config.db_file) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"responses", "user_nicknames"}.issubset(tables)


def test_update_activity_timestamp_initializes_and_updates(app_context):
    user_id = 123

    startup.update_activity_timestamp(app_context, user_id)
    first_timestamp = app_context.sessions.data[user_id]["last_activity_time"]
    startup.update_activity_timestamp(app_context, user_id)

    assert app_context.sessions.data[user_id]["last_activity_time"] >= first_timestamp


def test_recover_user_sessions_restores_language_and_nickname(app_context):
    user_id = 123
    user_hash = hash_user_id(user_id, app_context.config.user_hash_salt)
    save_user_nickname(app_context.config.db_file, user_hash, "Bright Fox 0", "2026-05")
    app_context.sessions.data[user_id] = {}
    app_context.sessions.profiles[user_id] = {"language": "en"}

    startup.recover_user_sessions(app_context)

    assert app_context.sessions.data[user_id]["language"] == "en"
    assert app_context.sessions.data[user_id]["nickname"] == "Bright Fox 0"
    assert app_context.sessions.data[user_id]["session_recovered"] is True
