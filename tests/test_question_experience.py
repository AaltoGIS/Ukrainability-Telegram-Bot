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
from ukrainability_telegram_bot.survey.questions.enjoyment import EnjoymentCallbacks
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
    app_context.sessions.set_data(123, "purpose_visit", ["placeholder-purpose-1"])
    app_context.sessions.set_data(123, "custom_purposes", ["placeholder-purpose-2"])

    enjoyment.ask_enjoyment(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "current_question") == "enjoyment"
    send_call = app_context.bot.send_message.call_args
    assert "placeholder-purpose-1, placeholder-purpose-2" in send_call.args[1]
    keyboard = send_call.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "enjoyment_0"


def _enjoyment_callbacks():
    return EnjoymentCallbacks(
        ask_visitor_type=MagicMock(),
        ask_final_confirmation=MagicMock(),
    )


def test_handle_enjoyment_selection_marks_choice_and_adds_done_button(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    options = messages["en"]["enjoyment_options"]

    enjoyment.handle_enjoyment_selection(app_context, _call("enjoyment_2", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "temp_enjoyment") == options[2]
    edit_kwargs = app_context.bot.edit_message_reply_markup.call_args.kwargs
    keyboard = edit_kwargs["reply_markup"].keyboard
    assert keyboard[2][0].text.startswith("✅")
    assert keyboard[-1][0].callback_data == "confirm_enjoyment"
    app_context.bot.answer_callback_query.assert_called_once()


def test_handle_enjoyment_selection_invalid_index_answers_invalid_rating(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    enjoyment.handle_enjoyment_selection(app_context, _call("enjoyment_999", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["invalid_rating"],
    )


def test_handle_enjoyment_selection_uses_profile_language_when_session_empty(app_context):
    user_id = 123
    app_context.sessions.set_profile(user_id, "language", "uk")

    enjoyment.handle_enjoyment_selection(app_context, _call("enjoyment_0", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "language") == "uk"
    options = messages["uk"]["enjoyment_options"]
    assert app_context.sessions.get_data(user_id, "temp_enjoyment") == options[0]


def test_handle_enjoyment_selection_no_language_anywhere_prompts_start(app_context):
    enjoyment.handle_enjoyment_selection(app_context, _call("enjoyment_0", user_id=123))

    sent_text = app_context.bot.send_message.call_args.args[1]
    assert "/start" in sent_text


def test_handle_enjoyment_selection_ignores_message_not_modified(app_context):
    import telebot

    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.bot.edit_message_reply_markup.side_effect = telebot.apihelper.ApiTelegramException(
        "/edit",
        "/edit",
        {"error_code": 400, "description": "message is not modified"},
    )

    enjoyment.handle_enjoyment_selection(app_context, _call("enjoyment_1", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once()


def test_confirm_enjoyment_advances_to_visitor_type(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_enjoyment", "placeholder-enjoyment")
    callbacks = _enjoyment_callbacks()

    enjoyment.confirm_enjoyment(app_context, _call("confirm_enjoyment", user_id=user_id), callbacks)

    assert app_context.sessions.get_data(user_id, "enjoyment") == "placeholder-enjoyment"
    assert app_context.sessions.get_data(user_id, "temp_enjoyment") is None
    assert app_context.sessions.get_data(user_id, "current_question") is None
    callbacks.ask_visitor_type.assert_called_once_with(456, user_id, "en")
    callbacks.ask_final_confirmation.assert_not_called()


def test_confirm_enjoyment_returns_to_final_confirmation_when_modifying(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_enjoyment", "placeholder-enjoyment")
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_data(user_id, "modifying_field", "enjoyment")
    callbacks = _enjoyment_callbacks()

    enjoyment.confirm_enjoyment(app_context, _call("confirm_enjoyment", user_id=user_id), callbacks)

    assert app_context.sessions.get_data(user_id, "modifying") is None
    assert app_context.sessions.get_data(user_id, "modifying_field") is None
    callbacks.ask_final_confirmation.assert_called_once_with(456, user_id, "en")
    callbacks.ask_visitor_type.assert_not_called()


def test_confirm_enjoyment_without_temp_value_warns_user(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    callbacks = _enjoyment_callbacks()

    enjoyment.confirm_enjoyment(app_context, _call("confirm_enjoyment", user_id=user_id), callbacks)

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["select_option_first"],
    )
    callbacks.ask_visitor_type.assert_not_called()


def test_enjoyment_question_class_methods_dispatch_to_module_functions(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    question = enjoyment.EnjoymentQuestion()

    question.ask(app_context, 456, user_id, "en")
    assert app_context.sessions.get_data(user_id, "current_question") == "enjoyment"

    question.handle(app_context, _call("enjoyment_0", user_id=user_id))
    assert app_context.sessions.get_data(user_id, "temp_enjoyment") is not None


def test_enjoyment_callbacks_from_context_uses_provided_actions(app_context):
    actions = SimpleNamespace(
        ask_visitor_type=MagicMock(),
        ask_final_confirmation=MagicMock(),
    )

    cbs = enjoyment.callbacks_from_context(app_context, actions)

    assert cbs.ask_visitor_type is actions.ask_visitor_type
    assert cbs.ask_final_confirmation is actions.ask_final_confirmation


def test_handle_visitor_done_with_selection_clears_state_and_continues(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "visitor_type", ["placeholder-visitor-1"])
    app_context.sessions.set_data(user_id, "custom_visitor_types", ["placeholder-visitor-2"])
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
        call
        for call in app_context.bot.send_message.call_args_list
        if call.kwargs.get("parse_mode") == "HTML"
    ][0]
    assert "placeholder-visitor-1; placeholder-visitor-2" in response_call.args[1]


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
