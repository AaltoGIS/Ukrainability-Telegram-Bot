from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import purpose
from ukrainability_telegram_bot.survey.questions.base import PurposeCallbacks
from ukrainability_telegram_bot.telegram_io import get_message_id


def _call(data, user_id=123, chat_id=456, message_id=789):
    return SimpleNamespace(
        id="callback-id",
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=message_id,
        ),
    )


def test_ask_purpose_visit_initializes_state_and_tracks_keyboard(app_context):
    app_context.bot.send_message.return_value = SimpleNamespace(message_id=321)

    purpose.ask_purpose_visit(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "purpose_visit") == []
    assert app_context.sessions.get_data(123, "custom_purposes") == []
    assert app_context.sessions.get_data(123, "awaiting_multiple_select") == "purpose_visit"
    assert get_message_id(app_context, 123, "purpose_visit") == 321

    send_call = app_context.bot.send_message.call_args
    assert messages["en"]["purpose_visit"] in send_call.args[1]
    keyboard = send_call.kwargs["reply_markup"]
    assert keyboard.keyboard[-1][0].callback_data == "purpose_done"


def test_handle_purpose_toggle_adds_and_removes_selected_option(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    option = messages["en"]["options"]["purpose_visit"][0]

    purpose.handle_purpose_selection(app_context, _call("purpose_0", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "purpose_visit") == [option]
    app_context.bot.edit_message_reply_markup.assert_called()

    purpose.handle_purpose_selection(app_context, _call("purpose_0", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "purpose_visit") == []


def test_handle_purpose_done_without_selection_answers_prompt(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "purpose_visit", [])
    app_context.sessions.set_data(user_id, "custom_purposes", [])

    purpose.handle_purpose_selection(app_context, _call("purpose_done", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["please_select_at_least_one"],
    )


def test_handle_purpose_done_with_selection_clears_state_and_continues(
    app_context,
    monkeypatch,
):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "purpose_visit", ["Walking"])
    app_context.sessions.set_data(user_id, "custom_purposes", ["Birding"])
    app_context.sessions.set_data(user_id, "awaiting_multiple_select", "purpose_visit")
    app_context.bot.send_message.return_value = SimpleNamespace(message_id=1)
    monkeypatch.setattr(purpose.time, "sleep", lambda seconds: None)
    ask_enjoyment = MagicMock()
    callbacks = PurposeCallbacks(
        ask_enjoyment=ask_enjoyment,
        ask_final_confirmation=MagicMock(),
    )

    purpose.handle_purpose_selection(
        app_context,
        _call("purpose_done", user_id=user_id),
        callbacks,
    )

    assert app_context.sessions.get_data(user_id, "awaiting_multiple_select") is None
    ask_enjoyment.assert_called_once_with(456, user_id, "en")
    response_calls = [
        call
        for call in app_context.bot.send_message.call_args_list
        if call.kwargs.get("parse_mode") == "HTML"
    ]
    assert "Walking; Birding" in response_calls[0].args[1]
