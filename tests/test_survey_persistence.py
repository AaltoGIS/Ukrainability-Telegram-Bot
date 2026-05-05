import datetime
import sqlite3
from unittest.mock import MagicMock

import pytest

from ukrainability_telegram_bot.security import decrypt_text
from ukrainability_telegram_bot.storage import (
    ENCRYPTED_COLUMNS,
    PLAINTEXT_COLUMNS,
    RESPONSE_COLUMNS,
    initialize_database,
)
from ukrainability_telegram_bot.survey.persistence import (
    DatabaseSaveError,
    EncryptionUnavailableError,
    build_response_row,
    encrypt_row,
    save_response,
)


def test_build_response_row_formats_lists_and_profile_fallback():
    now = datetime.datetime(2026, 5, 5, 12, 30, 45)
    snapshot = {
        "location": {"latitude": 49.1, "longitude": 33.4, "venue_title": "Park"},
        "purpose_visit": ["Walk", "Rest"],
        "changes_detail": ["Trees"],
        "wishlist": ["Benches", "Lights"],
        "visitor_type": ["Resident"],
        "accessibility": ["Ramp"],
    }
    profile = {"kremenchuk": ["Yes"]}

    row = build_response_row(
        snapshot,
        profile,
        language="en",
        nickname="BrightFox07",
        now=now,
    )

    assert row["nickname"] == "BrightFox07"
    assert row["month_year"] == "2026-05"
    assert row["timestamp"] == "2026-05-05 12:30:45"
    assert row["latitude"] == "49.1"
    assert row["purpose_visit"] == "Walk;Rest"
    assert row["wishlist"] == "Benches;Lights"
    assert row["kremenchuk"] == "Yes"
    assert row["consent"] == "True"


def test_encrypt_row_encrypts_everything_except_timestamp(app_context):
    row = {column: f"value-{column}" for column in RESPONSE_COLUMNS}

    encrypted = encrypt_row(app_context.fernet, row)

    for column in ENCRYPTED_COLUMNS:
        assert encrypted[column] != row[column]
        assert decrypt_text(app_context.fernet, encrypted[column]) == row[column]
    for column in PLAINTEXT_COLUMNS:
        assert encrypted[column] == row[column]


def test_save_response_skips_insert_when_consent_denied(app_context):
    initialize_database(app_context.config.db_file)
    app_context.sessions.set_profile(123, "consent", False)

    assert (
        save_response(
            app_context,
            123,
            "en",
            nickname_provider=lambda: "BrightFox07",
        )
        is True
    )

    with sqlite3.connect(app_context.config.db_file) as conn:
        count = conn.execute("SELECT count(*) FROM responses").fetchone()[0]
    assert count == 0


def test_save_response_inserts_encrypted_response(app_context):
    initialize_database(app_context.config.db_file)
    app_context.sessions.set_profile(123, "consent", True)
    app_context.sessions.set_data(123, "location", {"latitude": 49.1, "longitude": 33.4})
    app_context.sessions.set_data(123, "purpose_visit", ["Walk", "Rest"])
    app_context.sessions.set_data(123, "language", "en")

    assert (
        save_response(
            app_context,
            123,
            "en",
            nickname_provider=lambda: "BrightFox07",
        )
        is True
    )

    with sqlite3.connect(app_context.config.db_file) as conn:
        stored = conn.execute(
            "SELECT nickname, purpose_visit, language, timestamp FROM responses"
        ).fetchone()
    assert decrypt_text(app_context.fernet, stored[0]) == "BrightFox07"
    assert decrypt_text(app_context.fernet, stored[1]) == "Walk;Rest"
    assert decrypt_text(app_context.fernet, stored[2]) == "en"
    assert stored[3]


def test_save_response_raises_encryption_unavailable_when_fernet_missing(app_context):
    app_context.fernet = None
    app_context.sessions.set_profile(123, "consent", True)

    with pytest.raises(EncryptionUnavailableError):
        save_response(
            app_context,
            123,
            "en",
            nickname_provider=lambda: "BrightFox07",
        )


def test_save_response_retries_then_raises_database_save_error(monkeypatch, app_context):
    app_context.sessions.set_profile(123, "consent", True)
    insert_response = MagicMock(side_effect=sqlite3.Error("database locked"))
    sleep_calls = []
    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.persistence.insert_response",
        insert_response,
    )

    with pytest.raises(DatabaseSaveError):
        save_response(
            app_context,
            123,
            "en",
            nickname_provider=lambda: "BrightFox07",
            sleep=sleep_calls.append,
        )

    assert insert_response.call_count == 3
    assert sleep_calls == [1, 2]
