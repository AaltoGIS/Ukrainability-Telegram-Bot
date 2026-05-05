from types import SimpleNamespace

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import consent
from ukrainability_telegram_bot.survey.questions.base import ConsentCallbacks


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


def test_handle_consent_agree_stores_consent_and_sends_continue(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "nickname", "Name <Tag>")

    consent.handle_consent(app_context, _call("consent_0", user_id=user_id))

    assert app_context.sessions.get_profile(user_id, "consent") is True
    app_context.bot.edit_message_reply_markup.assert_called_once_with(
        chat_id=456,
        message_id=789,
        reply_markup=None,
    )
    app_context.bot.answer_callback_query.assert_called_once()

    send_call = app_context.bot.send_message.call_args
    assert "<b>Name &lt;Tag&gt;</b>" in send_call.args[1]
    assert send_call.kwargs["parse_mode"] == "HTML"
    keyboard = send_call.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "post_consent_continue"


def test_handle_consent_deny_stores_consent_false_and_sends_restart(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "nickname", "SafeName")

    consent.handle_consent(app_context, _call("consent_1", user_id=user_id))

    assert app_context.sessions.get_profile(user_id, "consent") is False
    send_call = app_context.bot.send_message.call_args
    assert send_call.args[1] == messages["en"]["consent_denied"]
    keyboard = send_call.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "restart"


def test_handle_consent_invalid_callback_answers_invalid_selection(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "nickname", "SafeName")

    consent.handle_consent(app_context, _call("consent_99", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["invalid_selection"],
    )
    app_context.bot.edit_message_reply_markup.assert_not_called()


def test_handle_post_consent_continue_removes_keyboard_and_registers_next_step(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    location_handler = object()
    callbacks = ConsentCallbacks(location_handler=location_handler)

    consent.handle_post_consent_continue(
        app_context,
        _call("post_consent_continue", user_id=user_id),
        callbacks,
    )

    app_context.bot.edit_message_reply_markup.assert_called_once_with(
        chat_id=456,
        message_id=789,
        reply_markup=None,
    )
    app_context.bot.register_next_step_handler_by_chat_id.assert_called_once_with(
        456,
        location_handler,
    )
