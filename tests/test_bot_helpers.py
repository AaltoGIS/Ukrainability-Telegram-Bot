import sqlite3
from types import SimpleNamespace

import pytest

from ukrainability_telegram_bot import _legacy as bot


def test_telegram_retry_after_coerces_string_and_caps():
    error = SimpleNamespace(result_json={"parameters": {"retry_after": "120"}})

    assert bot.telegram_retry_after(error) == 60.0


def test_telegram_retry_after_falls_back_for_bad_values():
    error = SimpleNamespace(result_json={"parameters": {"retry_after": "later"}})

    assert bot.telegram_retry_after(error, default=7) == 7.0


def test_callback_index_validates_prefix_and_bounds():
    options = ["yes", "no"]

    assert bot.callback_index("consent_1", "consent", options) == 1
    with pytest.raises(ValueError):
        bot.callback_index("purpose_1", "consent", options)
    with pytest.raises(IndexError):
        bot.callback_index("consent_2", "consent", options)


def test_save_data_and_restart_skips_insert_when_consent_denied(monkeypatch, tmp_path, app_context):
    user_id = 123
    monkeypatch.setattr(bot.runtime_module, "_active_context", app_context)
    monkeypatch.setattr(bot, "clear_message_ids", lambda user_id: None)
    monkeypatch.setattr(bot, "send_welcome", lambda **kwargs: None)

    with app_context.sessions.lock:
        app_context.sessions.data[user_id] = {"language": "en"}
        app_context.sessions.profiles[user_id] = {"consent": False}

    try:
        assert bot.save_data_and_restart(456, user_id, "en") is True
        with sqlite3.connect(app_context.config.db_file) as conn:
            count = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
        assert count == 0
    finally:
        with app_context.sessions.lock:
            app_context.sessions.data.pop(user_id, None)
            app_context.sessions.profiles.pop(user_id, None)


def test_handle_callback_error_clears_legacy_transient_state(monkeypatch, app_context):
    user_id = 123
    chat_id = 456
    monkeypatch.setattr(bot.runtime_module, "_active_context", app_context)
    app_context.sessions.data[user_id] = {
        "language": "en",
        "awaiting_multiple_select": "visitor_type",
        "temp_enjoyment": "5",
        "current_question": "enjoyment",
        "modifying": True,
        "modifying_field": "purpose_visit",
        "purpose_visit": ["Walking"],
    }
    call = SimpleNamespace(
        id="callback-id",
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id)),
    )

    bot.handle_callback_error(call, RuntimeError("boom"), "handle_purpose_selection")

    session = app_context.sessions.data[user_id]
    assert "awaiting_multiple_select" not in session
    assert "temp_enjoyment" not in session
    assert "current_question" not in session
    assert "modifying" not in session
    assert "modifying_field" not in session
    assert session["purpose_visit"] == ["Walking"]
    app_context.bot.answer_callback_query.assert_called_once()
