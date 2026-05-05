import sqlite3
from types import SimpleNamespace

import pytest

from ukrainability_telegram_bot import _legacy as bot
from ukrainability_telegram_bot import telegram_io
from ukrainability_telegram_bot.survey.actions import SurveyActions
from ukrainability_telegram_bot.survey.questions import restart as restart_question


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


def test_legacy_bridge_does_not_expose_session_store_wrappers(app_context):
    bridge = bot.create_legacy_bridge(app_context)

    for name in (
        "get_user_data",
        "set_user_data",
        "remove_user_data",
        "get_user_profile",
        "set_user_profile",
    ):
        assert not hasattr(bridge, name)


def test_legacy_bridge_does_not_expose_callback_builders(app_context):
    bridge = bot.create_legacy_bridge(app_context)

    assert not [
        name
        for name in dir(bridge)
        if name.startswith("_") and name.endswith("_callbacks")
    ]


def test_legacy_bridge_surface_is_limited(app_context):
    bridge = bot.create_legacy_bridge(app_context)

    public_names = {
        name
        for name in dir(bridge)
        if not name.startswith("_")
    }
    assert public_names == {
        "clear_callback_state",
        "ctx",
        "ensure_session_valid",
        "register_handlers",
    }


def test_save_data_and_restart_skips_insert_when_consent_denied(monkeypatch, tmp_path, app_context):
    user_id = 123
    actions = SurveyActions(app_context)

    with app_context.sessions.lock:
        app_context.sessions.data[user_id] = {"language": "en"}
        app_context.sessions.profiles[user_id] = {"consent": False}

    try:
        assert restart_question.save_data_and_restart(
            app_context,
            456,
            user_id,
            "en",
            False,
            restart_question.callbacks_from_context(app_context, actions),
        ) is True
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
    bridge = bot.create_legacy_bridge(app_context)
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

    telegram_io.handle_callback_error(
        app_context,
        call,
        RuntimeError("boom"),
        "handle_purpose_selection",
        clear_callback_state=bridge.clear_callback_state,
    )

    session = app_context.sessions.data[user_id]
    assert "awaiting_multiple_select" not in session
    assert "temp_enjoyment" not in session
    assert "current_question" not in session
    assert "modifying" not in session
    assert "modifying_field" not in session
    assert session["purpose_visit"] == ["Walking"]
    app_context.bot.answer_callback_query.assert_called_once()
