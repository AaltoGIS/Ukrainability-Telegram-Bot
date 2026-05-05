from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from telebot.apihelper import ApiTelegramException

from ukrainability_telegram_bot import telegram_io


def _api_exception(error_code, description, parameters=None):
    payload = {"error_code": error_code, "description": description}
    if parameters is not None:
        payload["parameters"] = parameters
    return ApiTelegramException("/method", "/method", payload)


def _callback(user_id=123, chat_id=456):
    return SimpleNamespace(
        id="cb-1",
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=789),
    )


def test_telegram_io_safe_send_message_uses_context_bot(app_context):
    app_context.bot.send_message.return_value = SimpleNamespace(message_id=42)

    msg = telegram_io.safe_send_message(app_context, 123, "hello")

    assert msg.message_id == 42
    app_context.bot.send_message.assert_called_once_with(
        123,
        "hello",
        reply_markup=None,
        parse_mode=None,
    )


def test_telegram_io_message_ids_live_in_session_store(app_context):
    telegram_io.register_message_id(app_context, 123, "purpose_visit", 456)

    assert telegram_io.get_message_id(app_context, 123, "purpose_visit") == 456

    telegram_io.clear_message_ids(app_context, 123)

    assert telegram_io.get_message_id(app_context, 123, "purpose_visit") is None


def test_send_next_step_prompt_registers_before_send(app_context):
    calls = []

    def handler(message):
        return message

    app_context.bot.register_next_step_handler_by_chat_id.side_effect = (
        lambda chat_id, callback: calls.append(("register", chat_id, callback))
    )
    app_context.bot.send_message.side_effect = lambda chat_id, text, **kwargs: calls.append(
        ("send", chat_id, text)
    ) or SimpleNamespace(message_id=1)

    telegram_io.send_next_step_prompt(app_context, 123, "prompt", handler)

    assert calls[0] == ("register", 123, handler)
    assert calls[1] == ("send", 123, "prompt")


def test_telegram_retry_after_uses_result_json_parameters():
    err = SimpleNamespace(result_json={"parameters": {"retry_after": 7}})
    assert telegram_io.telegram_retry_after(err) == 7.0


def test_telegram_retry_after_falls_back_to_result_dict():
    err = SimpleNamespace(result_json=None, result={"parameters": {"retry_after": 4}})
    assert telegram_io.telegram_retry_after(err) == 4.0


def test_telegram_retry_after_returns_default_when_missing():
    err = SimpleNamespace(result_json={}, result=None)
    assert telegram_io.telegram_retry_after(err, default=5) == 5.0


def test_telegram_retry_after_caps_to_60_seconds():
    err = SimpleNamespace(result_json={"parameters": {"retry_after": 9999}})
    assert telegram_io.telegram_retry_after(err) == 60.0


def test_telegram_retry_after_handles_unparseable_value():
    err = SimpleNamespace(result_json={"parameters": {"retry_after": "nope"}})
    assert telegram_io.telegram_retry_after(err, default=2) == 2.0


def test_redacted_coordinate_rounds_to_one_decimal():
    assert telegram_io.redacted_coordinate(49.123456) == 49.1


def test_redacted_coordinate_returns_unknown_for_non_numeric():
    assert telegram_io.redacted_coordinate("nope") == "unknown"


def test_callback_suffix_returns_value_after_prefix():
    assert telegram_io.callback_suffix("foo_bar", "foo") == "bar"


def test_callback_suffix_raises_on_wrong_prefix():
    with pytest.raises(ValueError):
        telegram_io.callback_suffix("bar_baz", "foo")


def test_callback_index_validates_range():
    options = ["a", "b", "c"]
    assert telegram_io.callback_index("foo_1", "foo", options) == 1
    with pytest.raises(IndexError):
        telegram_io.callback_index("foo_5", "foo", options)
    with pytest.raises(ValueError):
        telegram_io.callback_index("bar_1", "foo", options)


def test_safe_send_message_retries_on_rate_limit_then_succeeds(app_context, monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.telegram_io.time.sleep", lambda _: None)
    sent = SimpleNamespace(message_id=42)
    app_context.bot.send_message.side_effect = [
        _api_exception(429, "Too Many Requests", {"retry_after": 1}),
        sent,
    ]

    result = telegram_io.safe_send_message(app_context, 123, "hi")

    assert result is sent
    assert app_context.bot.send_message.call_count == 2


def test_safe_send_message_retries_on_other_api_errors_then_raises(app_context, monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.telegram_io.time.sleep", lambda _: None)
    app_context.bot.send_message.side_effect = _api_exception(500, "Server error")

    with pytest.raises(ApiTelegramException):
        telegram_io.safe_send_message(app_context, 123, "hi", max_retries=2)


def test_safe_send_message_retries_once_on_generic_exception(app_context, monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.telegram_io.time.sleep", lambda _: None)
    sent = SimpleNamespace(message_id=42)
    app_context.bot.send_message.side_effect = [ConnectionError("boom"), sent]

    result = telegram_io.safe_send_message(app_context, 123, "hi")

    assert result is sent


def test_safe_send_message_raises_on_repeated_generic_exception(app_context, monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.telegram_io.time.sleep", lambda _: None)
    app_context.bot.send_message.side_effect = ConnectionError("boom")

    with pytest.raises(ConnectionError):
        telegram_io.safe_send_message(app_context, 123, "hi", max_retries=3)


def test_send_keyboard_message_registers_message_id(app_context):
    app_context.bot.send_message.return_value = SimpleNamespace(message_id=99)

    telegram_io.send_keyboard_message(app_context, 456, 123, "text", None, "purpose_visit")

    assert telegram_io.get_message_id(app_context, 123, "purpose_visit") == 99


def test_send_keyboard_message_falls_back_when_register_fails(app_context, monkeypatch):
    app_context.bot.send_message.return_value = SimpleNamespace(message_id=99)
    monkeypatch.setattr(
        "ukrainability_telegram_bot.telegram_io.register_message_id",
        MagicMock(side_effect=RuntimeError("nope")),
    )

    telegram_io.send_keyboard_message(app_context, 456, 123, "text", None, "purpose_visit")

    assert app_context.bot.send_message.call_count == 2


def test_edit_keyboard_returns_false_when_no_message_id(app_context):
    assert telegram_io.edit_keyboard(app_context, 123, 456, "purpose_visit", None) is False


def test_edit_keyboard_treats_not_modified_as_success(app_context):
    telegram_io.register_message_id(app_context, 123, "purpose_visit", 99)
    app_context.bot.edit_message_reply_markup.side_effect = _api_exception(
        400, "message is not modified"
    )

    assert telegram_io.edit_keyboard(app_context, 123, 456, "purpose_visit", None) is True


def test_edit_keyboard_returns_false_on_other_api_errors(app_context):
    telegram_io.register_message_id(app_context, 123, "purpose_visit", 99)
    app_context.bot.edit_message_reply_markup.side_effect = _api_exception(400, "bad")

    assert telegram_io.edit_keyboard(app_context, 123, 456, "purpose_visit", None) is False


def test_edit_keyboard_returns_false_on_generic_exception(app_context):
    telegram_io.register_message_id(app_context, 123, "purpose_visit", 99)
    app_context.bot.edit_message_reply_markup.side_effect = ConnectionError("boom")

    assert telegram_io.edit_keyboard(app_context, 123, 456, "purpose_visit", None) is False


def test_edit_keyboard_succeeds_when_telegram_accepts_update(app_context):
    telegram_io.register_message_id(app_context, 123, "purpose_visit", 99)

    assert telegram_io.edit_keyboard(app_context, 123, 456, "purpose_visit", None) is True


def test_escape_html_replaces_specials():
    assert telegram_io.escape_html("a & b <c>") == "a &amp; b &lt;c&gt;"


def test_escape_html_coerces_non_string():
    assert telegram_io.escape_html(42) == "42"


def test_clear_callback_state_removes_temp_keys_and_flags(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "temp_age", "placeholder-value")
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_data(user_id, "current_question", "age")
    app_context.sessions.set_data(user_id, "language", "en")

    telegram_io.clear_callback_state(app_context, user_id)

    assert app_context.sessions.get_data(user_id, "temp_age") is None
    assert app_context.sessions.get_data(user_id, "modifying") is None
    assert app_context.sessions.get_data(user_id, "current_question") is None
    assert app_context.sessions.get_data(user_id, "language") == "en"


def test_safe_answer_callback_ignores_expired_query_error(app_context):
    app_context.bot.answer_callback_query.side_effect = _api_exception(400, "query is too old")

    telegram_io.safe_answer_callback(app_context, _callback(), "msg")

    app_context.bot.answer_callback_query.assert_called_once()


def test_safe_answer_callback_other_error_falls_back_to_send_message(app_context):
    app_context.bot.answer_callback_query.side_effect = _api_exception(500, "boom")

    telegram_io.safe_answer_callback(app_context, _callback(), "msg")

    app_context.bot.send_message.assert_called_once()


def test_hide_keyboard_swallows_send_failure(app_context):
    app_context.bot.send_message.side_effect = ConnectionError("boom")

    telegram_io.hide_keyboard(app_context, 456)


def test_handle_callback_error_clears_state_and_sends_restart(app_context):
    app_context.sessions.set_data(123, "language", "en")
    app_context.sessions.set_data(123, "temp_age", "placeholder-value")
    clear = MagicMock()

    telegram_io.handle_callback_error(
        app_context,
        _callback(),
        RuntimeError("boom"),
        "test_func",
        clear_callback_state=clear,
    )

    clear.assert_called_once_with(123)
    sent_keyboards = [
        c.kwargs.get("reply_markup") for c in app_context.bot.send_message.call_args_list
    ]
    keyboard = next(k for k in sent_keyboards if k is not None)
    cds = [b.callback_data for row in keyboard.keyboard for b in row]
    assert "restart" in cds


def test_handle_callback_error_without_clear_state_still_sends_messages(app_context):
    app_context.sessions.set_data(123, "language", "en")

    telegram_io.handle_callback_error(
        app_context,
        _callback(),
        RuntimeError("boom"),
        "test_func",
    )

    assert app_context.bot.send_message.call_count >= 2


def test_handle_callback_error_swallows_send_failure(app_context):
    app_context.bot.answer_callback_query.side_effect = ConnectionError("ignored")
    app_context.bot.send_message.side_effect = ConnectionError("also ignored")

    telegram_io.handle_callback_error(app_context, _callback(), RuntimeError("boom"), "test_func")
