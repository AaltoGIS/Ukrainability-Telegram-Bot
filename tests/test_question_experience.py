from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import (
    accessibility,
    duration,
    enjoyment,
    regularity,
    visitor_type,
)
from ukrainability_telegram_bot.survey.questions.regularity import RegularityCallbacks
from ukrainability_telegram_bot.survey.questions.visitor_type import VisitorTypeCallbacks


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


def test_ask_enjoyment_uses_selected_purposes_and_tracks_question(app_context):
    app_context.sessions.set_data(123, "purpose_visit", ["Walking"])
    app_context.sessions.set_data(123, "custom_purposes", ["Birding"])

    enjoyment.ask_enjoyment(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "current_question") == "enjoyment"
    send_call = app_context.bot.send_message.call_args
    assert "Walking, Birding" in send_call.args[1]
    keyboard = send_call.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "enjoyment_0"


def test_handle_visitor_done_with_selection_clears_state_and_continues(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "visitor_type", ["Families"])
    app_context.sessions.set_data(user_id, "custom_visitor_types", ["Students"])
    app_context.sessions.set_data(user_id, "awaiting_multiple_select", "visitor_type")
    ask_duration = MagicMock()
    callbacks = VisitorTypeCallbacks(
        ask_duration=ask_duration,
        ask_final_confirmation=MagicMock(),
    )

    visitor_type.handle_visitor_type_selection(
        app_context,
        _call("visitor_done", user_id=user_id),
        callbacks,
    )

    assert app_context.sessions.get_data(user_id, "awaiting_multiple_select") is None
    ask_duration.assert_called_once_with(456, user_id, "en")
    response_call = [
        call for call in app_context.bot.send_message.call_args_list
        if call.kwargs.get("parse_mode") == "HTML"
    ][0]
    assert "Families; Students" in response_call.args[1]


def test_duration_invalid_callback_answers_invalid_selection(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    duration.handle_duration_selection(app_context, _call("duration_999", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["invalid_selection"],
    )


def test_accessibility_invalid_callback_answers_invalid_selection(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    accessibility.handle_accessibility_selection(
        app_context,
        _call("accessibility_999", user_id=user_id),
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["invalid_selection"],
    )


def test_confirm_regularity_one_time_visit_skips_to_wishlist(app_context):
    user_id = 123
    selected = messages["en"]["options"]["regularity"][4]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_regularity", selected)
    app_context.sessions.set_data(user_id, "regularity", "")
    ask_wishlist = MagicMock()
    callbacks = RegularityCallbacks(
        ask_noticed_changes=MagicMock(),
        ask_wishlist=ask_wishlist,
        ask_final_confirmation=MagicMock(),
        clear_dependent_fields=MagicMock(return_value=[]),
        get_anonymous_id=MagicMock(return_value="anon"),
    )

    regularity.confirm_regularity(
        app_context,
        _call("confirm_regularity", user_id=user_id),
        callbacks,
    )

    assert app_context.sessions.get_data(user_id, "regularity") == selected
    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["response_confirmed"],
    )
    ask_wishlist.assert_called_once_with(456, user_id, "en")
