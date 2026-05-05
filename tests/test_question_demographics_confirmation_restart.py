from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import (
    confirmation,
    demographics,
    restart,
)
from ukrainability_telegram_bot.survey.questions.confirmation import ConfirmationCallbacks
from ukrainability_telegram_bot.survey.questions.demographics import DemographicsCallbacks
from ukrainability_telegram_bot.survey.questions.restart import RestartCallbacks


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


def _demographics_callbacks(**overrides):
    values = {
        "ask_gender": MagicMock(),
        "ask_occupation": MagicMock(),
        "ask_income": MagicMock(),
        "ask_kremenchuk": MagicMock(),
        "ask_description": MagicMock(),
        "ask_final_confirmation": MagicMock(),
    }
    values.update(overrides)
    return DemographicsCallbacks(**values)


def _confirmation_callbacks(**overrides):
    values = {
        "ask_enjoyment": MagicMock(),
        "ask_purpose_visit": MagicMock(),
        "ask_regularity": MagicMock(),
        "ask_accessibility": MagicMock(),
        "ask_noticed_changes": MagicMock(),
        "ask_changes_detail": MagicMock(),
        "ask_wishlist": MagicMock(),
        "ask_kremenchuk": MagicMock(),
        "ask_age": MagicMock(),
        "ask_gender": MagicMock(),
        "ask_occupation": MagicMock(),
        "ask_income": MagicMock(),
        "ask_description": MagicMock(),
        "ask_visitor_type": MagicMock(),
        "ask_duration": MagicMock(),
        "ask_continue_or_stop": MagicMock(),
        "save_data_and_restart": MagicMock(),
        "get_anonymous_id": MagicMock(return_value="anon"),
    }
    values.update(overrides)
    return ConfirmationCallbacks(**values)


def _restart_callbacks(**overrides):
    values = {
        "location_handler": MagicMock(),
        "send_welcome": MagicMock(),
        "get_user_hash": MagicMock(return_value="hash"),
        "get_user_nickname": MagicMock(return_value="Nick Name 1"),
        "generate_unique_nickname": MagicMock(return_value="Nick Name 2"),
        "save_user_nickname": MagicMock(),
        "clear_message_ids": MagicMock(),
    }
    values.update(overrides)
    return RestartCallbacks(**values)


def test_ask_age_reuses_profile_and_continues_to_gender(app_context):
    user_id = 123
    ask_gender = MagicMock()
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_profile(user_id, "age", "25-34")

    demographics.ask_age(
        app_context,
        456,
        user_id,
        "en",
        _demographics_callbacks(ask_gender=ask_gender),
    )

    assert app_context.sessions.get_data(user_id, "age") == "25-34"
    ask_gender.assert_called_once_with(456, user_id, "en")


def test_confirm_income_with_stored_kremenchuk_continues_to_description(app_context):
    user_id = 123
    ask_description = MagicMock()
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_income", "Prefer not to disclose")
    app_context.sessions.set_profile(user_id, "kremenchuk", "1-3 years")

    demographics.confirm_income(
        app_context,
        _call("confirm_income", user_id=user_id),
        _demographics_callbacks(ask_description=ask_description),
    )

    assert app_context.sessions.get_data(user_id, "income") == "Prefer not to disclose"
    assert app_context.sessions.get_profile(user_id, "income") == "Prefer not to disclose"
    assert app_context.sessions.get_data(user_id, "kremenchuk") == "1-3 years"
    ask_description.assert_called_once_with(456, user_id, "en")


def test_get_responses_text_merges_custom_values_and_escapes_html(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "purpose_visit", ["Relax"])
    app_context.sessions.set_data(user_id, "custom_purposes", ["Meet <friends>"])
    app_context.sessions.set_data(user_id, "description", "Nice & calm")

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert "Relax; Meet &lt;friends&gt;" in text
    assert "Nice &amp; calm" in text


def test_final_confirmation_confirm_saves_and_asks_continue(app_context):
    user_id = 123
    save_data_and_restart = MagicMock()
    ask_continue_or_stop = MagicMock()
    app_context.sessions.set_data(user_id, "language", "en")

    confirmation.handle_final_confirmation_choice(
        app_context,
        _call("final_1", user_id=user_id),
        _confirmation_callbacks(
            save_data_and_restart=save_data_and_restart,
            ask_continue_or_stop=ask_continue_or_stop,
        ),
    )

    save_data_and_restart.assert_called_once_with(456, user_id, "en", False)
    ask_continue_or_stop.assert_called_once_with(456, user_id, "en")
    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["confirm_submission"],
    )


def test_modification_selection_routes_to_selected_question(app_context):
    user_id = 123
    ask_income = MagicMock()
    app_context.sessions.set_data(user_id, "language", "en")

    confirmation.handle_modification_selection(
        app_context,
        _call("modify_income", user_id=user_id),
        _confirmation_callbacks(ask_income=ask_income),
    )

    assert app_context.sessions.get_data(user_id, "modifying") is True
    assert app_context.sessions.get_data(user_id, "modifying_field") == "income"
    ask_income.assert_called_once_with(456, user_id, "en")


def test_continue_selection_registers_next_location_prompt(app_context):
    user_id = 123
    location_handler = MagicMock()
    app_context.sessions.set_data(user_id, "language", "en")

    restart.handle_continue_or_stop_selection(
        app_context,
        _call("continue_0", user_id=user_id),
        _restart_callbacks(location_handler=location_handler),
    )

    app_context.bot.register_next_step_handler_by_chat_id.assert_called_once()
    args = app_context.bot.register_next_step_handler_by_chat_id.call_args.args
    assert args[0] == 456
    assert args[1] is location_handler
