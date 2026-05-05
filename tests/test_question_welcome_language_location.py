from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import language, location, welcome


def _callback(data, user_id=123, chat_id=456, message_id=789):
    return SimpleNamespace(
        id="callback-id",
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=message_id,
        ),
    )


def _text_message(text, user_id=123, chat_id=456):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        text=text,
        content_type="text",
    )


def test_send_welcome_creates_nickname_and_sends_language_prompt(app_context):
    callbacks = welcome.WelcomeCallbacks(
        update_activity_timestamp=MagicMock(),
        get_user_hash=MagicMock(return_value="user-hash"),
        get_user_nickname=MagicMock(return_value=None),
        generate_unique_nickname=MagicMock(return_value="SafeNick1"),
        save_user_nickname=MagicMock(),
        send_welcome=MagicMock(),
    )

    welcome.send_welcome(
        app_context,
        callbacks=callbacks,
        message=_text_message("/start"),
    )

    assert app_context.sessions.get_data(123, "nickname") == "SafeNick1"
    callbacks.save_user_nickname.assert_called_once_with("user-hash", "SafeNick1")
    send_call = app_context.bot.send_message.call_args
    assert messages["en"]["welcome"] in send_call.args[1]
    keyboard = send_call.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "language_en"
    assert keyboard.keyboard[0][1].callback_data == "language_uk"


def test_language_selection_sets_language_and_sends_consent_prompt(app_context):
    callbacks = language.LanguageCallbacks(location_handler=MagicMock())

    language.handle_language_selection(
        app_context,
        _callback("language_uk"),
        callbacks,
    )

    assert app_context.sessions.get_data(123, "language") == "uk"
    assert app_context.sessions.get_profile(123, "language") == "uk"
    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["uk"]["language_callback_ack"].format(language="UK"),
    )
    app_context.bot.edit_message_reply_markup.assert_called_once_with(
        chat_id=456,
        message_id=789,
        reply_markup=None,
    )
    consent_call = app_context.bot.send_message.call_args
    assert consent_call.args[1] == messages["uk"]["project_intro"]
    assert consent_call.kwargs["parse_mode"] == "HTML"
    keyboard = consent_call.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "consent_0"


def test_location_text_response_stores_location_and_continues(app_context):
    app_context.sessions.set_data(123, "language", "en")
    ask_purpose = MagicMock()
    callbacks = location.LocationCallbacks(
        update_activity_timestamp=MagicMock(),
        send_welcome=MagicMock(),
        ask_purpose_visit=ask_purpose,
        location_handler=MagicMock(),
    )

    location.handle_location_step(
        app_context,
        _text_message("Student Park"),
        callbacks,
    )

    assert app_context.sessions.get_data(123, "location") == {
        "latitude": "",
        "longitude": "",
        "venue_title": "",
        "venue_address": "Student Park",
    }
    ask_purpose.assert_called_once_with(456, 123, "en")
    send_call = app_context.bot.send_message.call_args
    assert "Student Park" in send_call.args[1]
