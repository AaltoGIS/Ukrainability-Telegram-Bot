import sqlite3

from ukrainability_telegram_bot.storage import (
    ENCRYPTED_COLUMNS,
    PLAINTEXT_COLUMNS,
    RESPONSE_COLUMNS,
    get_all_used_nicknames,
    get_latest_user_nickname,
    get_user_nickname,
    initialize_database,
    insert_response,
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
    assert get_latest_user_nickname(db_file, "hash-1") == "WiseWolf08"
    assert get_all_used_nicknames(db_file) == {"BrightFox07", "WiseWolf08"}


def test_initialize_database_is_idempotent(tmp_path):
    db_file = tmp_path / "responses_kremenchuk.db"

    initialize_database(db_file)
    initialize_database(db_file)

    with sqlite3.connect(db_file) as conn:
        assert conn.execute("SELECT count(*) FROM user_nicknames").fetchone()[0] == 0


def test_table_columns_rejects_unknown_table(tmp_path):
    db_file = tmp_path / "responses_kremenchuk.db"
    initialize_database(db_file)

    try:
        table_columns(db_file, "responses; DROP TABLE responses")
    except ValueError as exc:
        assert "Unsupported table name" in str(exc)
    else:
        raise AssertionError("Expected unsafe table name to be rejected")


def test_response_column_partition_matches_current_save_behavior():
    assert PLAINTEXT_COLUMNS == ("timestamp",)
    assert set(ENCRYPTED_COLUMNS) == set(RESPONSE_COLUMNS) - set(PLAINTEXT_COLUMNS)
    assert "consent" in ENCRYPTED_COLUMNS
    assert "language" in ENCRYPTED_COLUMNS
    assert "nickname" in ENCRYPTED_COLUMNS


def test_insert_response_persists_row_in_schema_order(tmp_path):
    db_file = tmp_path / "responses_kremenchuk.db"
    initialize_database(db_file)
    row = {column: f"value-{column}" for column in RESPONSE_COLUMNS}

    row_id = insert_response(db_file, row)

    with sqlite3.connect(db_file) as conn:
        stored = conn.execute(
            "SELECT nickname, timestamp, consent FROM responses WHERE id = ?",
            (row_id,),
        ).fetchone()
    assert stored == ("value-nickname", "value-timestamp", "value-consent")
