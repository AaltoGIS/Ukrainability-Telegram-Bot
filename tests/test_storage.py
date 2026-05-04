import sqlite3

from ukrainability_telegram_bot.storage import (
    RESPONSE_COLUMNS,
    get_all_used_nicknames,
    get_user_nickname,
    initialize_database,
    save_user_nickname,
    table_columns,
)


def test_initialize_database_creates_expected_schema(tmp_path):
    db_file = tmp_path / "responses_kremenchuk.db"

    initialize_database(db_file)

    response_columns = set(table_columns(db_file, "responses"))
    for column in RESPONSE_COLUMNS:
        assert column in response_columns
    assert {"user_hash", "nickname", "month_year"} <= set(
        table_columns(db_file, "user_nicknames")
    )


def test_nickname_persistence_is_month_scoped(tmp_path):
    db_file = tmp_path / "responses_kremenchuk.db"
    initialize_database(db_file)

    save_user_nickname(db_file, "hash-1", "BrightFox07", "2026-05")
    save_user_nickname(db_file, "hash-1", "WiseWolf08", "2026-06")

    assert get_user_nickname(db_file, "hash-1", "2026-05") == "BrightFox07"
    assert get_user_nickname(db_file, "hash-1", "2026-06") == "WiseWolf08"
    assert get_all_used_nicknames(db_file) == {"BrightFox07", "WiseWolf08"}


def test_initialize_database_is_idempotent(tmp_path):
    db_file = tmp_path / "responses_kremenchuk.db"

    initialize_database(db_file)
    initialize_database(db_file)

    with sqlite3.connect(db_file) as conn:
        assert conn.execute("SELECT count(*) FROM user_nicknames").fetchone()[0] == 0
