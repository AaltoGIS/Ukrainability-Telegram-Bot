from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey import text_router


def _message(user_id=123, chat_id=456, text="hello"):
    return SimpleNamespace(
        text=text,
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
    )


def test_text_router_records_custom_multiple_select_input(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "awaiting_multiple_select", "purpose_visit")

    text_router.handle_text_messages(app_context, _message(user_id=user_id, text="Birding"))

    assert app_context.sessions.get_data(user_id, "custom_purposes") == ["Birding"]
    app_context.bot.send_message.assert_called_with(
        456,
        messages["en"]["multiple_select_input_noted"],
    )


def test_text_router_reprompts_single_select_question(app_context):
    user_id = 123
    actions = MagicMock()
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "current_question", "duration")

    text_router.handle_text_messages(
        app_context,
        _message(user_id=user_id, text="about an hour"),
        actions,
    )

    app_context.bot.send_message.assert_called_with(
        456,
        messages["en"]["single_select_prompt"],
    )
    actions.ask_duration.assert_called_once_with(456, user_id, "en")
