from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.flow import (
    NOTICED_CHANGES_DETAIL_REQUIRING_INDICES,
    REGULARITY_SKIP_TO_WISHLIST_INDICES,
)
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
    app_context.sessions.set_profile(user_id, "age", "placeholder-age")

    demographics.ask_age(
        app_context,
        456,
        user_id,
        "en",
        _demographics_callbacks(ask_gender=ask_gender),
    )

    assert app_context.sessions.get_data(user_id, "age") == "placeholder-age"
    ask_gender.assert_called_once_with(456, user_id, "en")


def test_ask_age_without_profile_sends_question_with_keyboard(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    demographics.ask_age(app_context, 456, user_id, "en", _demographics_callbacks())

    assert app_context.sessions.get_data(user_id, "current_question") == "age"
    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "age_0"


def test_ask_age_modifying_skips_profile_lookup(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_profile(user_id, "age", "placeholder-age")
    ask_gender = MagicMock()

    demographics.ask_age(
        app_context, 456, user_id, "en", _demographics_callbacks(ask_gender=ask_gender)
    )

    assert app_context.sessions.get_data(user_id, "current_question") == "age"
    ask_gender.assert_not_called()


def test_ask_income_without_profile_sends_single_select(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    demographics.ask_income(app_context, 456, user_id, "en", _demographics_callbacks())

    assert app_context.sessions.get_data(user_id, "current_question") == "income"
    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "income_0"


def test_ask_income_with_profile_no_callbacks_just_seeds_session(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_profile(user_id, "income", "placeholder-income")

    demographics.ask_income(app_context, 456, user_id, "en", None)

    assert app_context.sessions.get_data(user_id, "income") == "placeholder-income"
    app_context.bot.send_message.assert_not_called()


def test_ask_income_with_profile_no_kremenchuk_routes_to_kremenchuk(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_profile(user_id, "income", "placeholder-income")
    ask_kremenchuk = MagicMock()

    demographics.ask_income(
        app_context,
        456,
        user_id,
        "en",
        _demographics_callbacks(ask_kremenchuk=ask_kremenchuk),
    )

    ask_kremenchuk.assert_called_once_with(456, user_id, "en")


def test_handle_gender_selection_marks_choice_and_adds_done_button(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    options = messages["en"]["options"]["gender"]

    demographics.handle_gender_selection(app_context, _call("gender_1", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "temp_gender") == options[1]
    keyboard = app_context.bot.edit_message_reply_markup.call_args.kwargs["reply_markup"]
    assert keyboard.keyboard[1][0].text.startswith("✅")
    assert keyboard.keyboard[-1][0].callback_data == "confirm_gender"


def test_handle_age_selection_invalid_index_answers_invalid_selection(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    demographics.handle_age_selection(app_context, _call("age_999", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["invalid_selection"],
    )


def test_handle_occupation_selection_falls_back_to_profile_language(app_context):
    user_id = 123
    app_context.sessions.set_profile(user_id, "language", "uk")

    demographics.handle_occupation_selection(app_context, _call("occupation_0", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "language") == "uk"
    options = messages["uk"]["options"]["occupation"]
    assert app_context.sessions.get_data(user_id, "temp_occupation") == options[0]


def test_handle_income_selection_no_language_anywhere_warns_session_expired(app_context):
    demographics.handle_income_selection(app_context, _call("income_0", user_id=123))

    sent_text = app_context.bot.send_message.call_args.args[1]
    assert sent_text == messages["en"]["session_expired"]


def test_confirm_age_advances_to_gender(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_age", "placeholder-age")
    ask_gender = MagicMock()

    demographics.confirm_age(
        app_context,
        _call("confirm_age", user_id=user_id),
        _demographics_callbacks(ask_gender=ask_gender),
    )

    assert app_context.sessions.get_data(user_id, "age") == "placeholder-age"
    assert app_context.sessions.get_profile(user_id, "age") == "placeholder-age"
    ask_gender.assert_called_once_with(456, user_id, "en")


def test_confirm_age_does_not_honor_modifying(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_age", "placeholder-age")
    app_context.sessions.set_data(user_id, "modifying", True)
    ask_gender = MagicMock()
    ask_final = MagicMock()

    demographics.confirm_age(
        app_context,
        _call("confirm_age", user_id=user_id),
        _demographics_callbacks(ask_gender=ask_gender, ask_final_confirmation=ask_final),
    )

    ask_gender.assert_called_once_with(456, user_id, "en")
    ask_final.assert_not_called()


def test_confirm_gender_when_modifying_returns_to_final_confirmation(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_gender", "placeholder-gender")
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_data(user_id, "modifying_field", "gender")
    ask_occupation = MagicMock()
    ask_final = MagicMock()

    demographics.confirm_gender(
        app_context,
        _call("confirm_gender", user_id=user_id),
        _demographics_callbacks(ask_occupation=ask_occupation, ask_final_confirmation=ask_final),
    )

    assert app_context.sessions.get_data(user_id, "modifying") is None
    assert app_context.sessions.get_data(user_id, "modifying_field") is None
    ask_final.assert_called_once_with(456, user_id, "en")
    ask_occupation.assert_not_called()


def test_confirm_occupation_when_modifying_description_routes_to_description(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_occupation", "placeholder-occupation")
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_data(user_id, "modifying_field", "description")
    ask_description = MagicMock()
    ask_final = MagicMock()

    demographics.confirm_occupation(
        app_context,
        _call("confirm_occupation", user_id=user_id),
        _demographics_callbacks(ask_description=ask_description, ask_final_confirmation=ask_final),
    )

    ask_description.assert_called_once_with(456, user_id, "en")
    ask_final.assert_not_called()


def test_confirm_gender_without_temp_value_warns_user(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    demographics.confirm_gender(
        app_context,
        _call("confirm_gender", user_id=user_id),
        _demographics_callbacks(),
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["select_option_first"],
    )


def test_confirm_income_without_stored_kremenchuk_routes_to_kremenchuk(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_income", "placeholder-income")
    ask_kremenchuk = MagicMock()
    ask_description = MagicMock()

    demographics.confirm_income(
        app_context,
        _call("confirm_income", user_id=user_id),
        _demographics_callbacks(ask_kremenchuk=ask_kremenchuk, ask_description=ask_description),
    )

    ask_kremenchuk.assert_called_once_with(456, user_id, "en")
    ask_description.assert_not_called()


def test_demographics_question_classes_dispatch_to_module_functions(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    for cls, field in [
        (demographics.AgeQuestion, "age"),
        (demographics.GenderQuestion, "gender"),
        (demographics.OccupationQuestion, "occupation"),
        (demographics.IncomeQuestion, "income"),
    ]:
        question = cls()
        question.ask(app_context, 456, user_id, "en")
        assert app_context.sessions.get_data(user_id, "current_question") == field
        question.handle(app_context, _call(f"{field}_0", user_id=user_id))
        assert app_context.sessions.get_data(user_id, f"temp_{field}") is not None
        app_context.sessions.remove_data(user_id, "current_question")
        app_context.sessions.remove_data(user_id, f"temp_{field}")


def test_demographics_callbacks_from_context_uses_provided_actions(app_context):
    actions = SimpleNamespace(
        ask_gender=MagicMock(),
        ask_occupation=MagicMock(),
        ask_income=MagicMock(),
        ask_kremenchuk=MagicMock(),
        ask_description=MagicMock(),
        ask_final_confirmation=MagicMock(),
    )

    cbs = demographics.callbacks_from_context(app_context, actions)

    assert cbs.ask_gender is actions.ask_gender


def test_confirm_income_with_stored_kremenchuk_continues_to_description(app_context):
    user_id = 123
    ask_description = MagicMock()
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_income", "placeholder-income")
    app_context.sessions.set_profile(user_id, "kremenchuk", "placeholder-kremenchuk")

    demographics.confirm_income(
        app_context,
        _call("confirm_income", user_id=user_id),
        _demographics_callbacks(ask_description=ask_description),
    )

    assert app_context.sessions.get_data(user_id, "income") == "placeholder-income"
    assert app_context.sessions.get_profile(user_id, "income") == "placeholder-income"
    assert app_context.sessions.get_data(user_id, "kremenchuk") == "placeholder-kremenchuk"
    ask_description.assert_called_once_with(456, user_id, "en")


def test_get_responses_text_merges_custom_values_and_escapes_html(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "purpose_visit", ["Relax"])
    app_context.sessions.set_data(user_id, "custom_purposes", ["Meet <friends>"])
    app_context.sessions.set_data(user_id, "description", "Nice & calm")

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert "Relax; Meet &lt;friends&gt;" in text
    assert "Nice &amp; calm" in text


def test_get_responses_text_renders_location_with_venue(app_context):
    user_id = 123
    app_context.sessions.set_data(
        user_id,
        "location",
        {"venue_title": "Park <main>", "venue_address": "Side & street"},
    )

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert "Park &lt;main&gt;" in text
    assert "Side &amp; street" in text


def test_get_responses_text_renders_location_with_lat_lon(app_context):
    user_id = 123
    app_context.sessions.set_data(
        user_id,
        "location",
        {"latitude": 49.07, "longitude": 33.42},
    )

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert "49.07" in text
    assert "33.42" in text


def test_get_responses_text_renders_voice_submitted(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "voice_submitted", "voice.ogg")
    app_context.sessions.set_data(user_id, "description", "")

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert messages["en"]["voice_message_submitted"] in text


def test_get_responses_text_renders_skipped_description(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "description", "   ")

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert messages["en"]["skipped_label"] in text


def test_get_responses_text_renders_visitor_accessibility_changes_wishlist(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "visitor_type", ["placeholder-visitor-1"])
    app_context.sessions.set_data(user_id, "custom_visitor_types", ["placeholder-visitor-2"])
    app_context.sessions.set_data(user_id, "accessibility", ["placeholder-access-1"])
    app_context.sessions.set_data(user_id, "custom_accessibility", ["placeholder-access-2"])
    app_context.sessions.set_data(user_id, "changes_detail", ["placeholder-change-1"])
    app_context.sessions.set_data(user_id, "custom_changes", ["placeholder-change-2"])
    app_context.sessions.set_data(user_id, "wishlist", ["placeholder-wish-1"])
    app_context.sessions.set_data(user_id, "custom_wishlist", ["placeholder-wish-2"])
    app_context.sessions.set_data(user_id, "kremenchuk", "placeholder-kremenchuk")
    app_context.sessions.set_data(user_id, "custom_kremenchuk", [])

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert "placeholder-visitor-1; placeholder-visitor-2" in text
    assert "placeholder-access-1; placeholder-access-2" in text
    assert "placeholder-change-1; placeholder-change-2" in text
    assert "placeholder-wish-1; placeholder-wish-2" in text
    assert "placeholder-kremenchuk" in text


def test_get_responses_text_renders_list_field_via_generic_branch(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "age", "placeholder-age")

    text = confirmation.get_responses_text(app_context, user_id, "en")

    assert "placeholder-age" in text


def test_ask_final_confirmation_sends_summary_and_prompt(app_context, monkeypatch):
    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.confirmation.time.sleep", lambda _: None
    )
    user_id = 123
    app_context.sessions.set_data(user_id, "age", "placeholder-age")

    confirmation.ask_final_confirmation(app_context, 456, user_id, "en")

    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    callbacks = [btn.callback_data for row in keyboard.keyboard for btn in row]
    assert callbacks == ["final_0", "final_1"]


def test_ask_final_confirmation_pulls_kremenchuk_from_profile(app_context, monkeypatch):
    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.confirmation.time.sleep", lambda _: None
    )
    user_id = 123
    app_context.sessions.set_profile(user_id, "kremenchuk", "placeholder-kremenchuk")

    confirmation.ask_final_confirmation(app_context, 456, user_id, "en")

    assert app_context.sessions.get_data(user_id, "kremenchuk") == "placeholder-kremenchuk"


def test_handle_final_confirmation_modify_branch_calls_ask_which(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    confirmation.handle_final_confirmation_choice(
        app_context,
        _call("final_0", user_id=user_id),
        _confirmation_callbacks(),
    )

    sent_texts = [c.args[1] for c in app_context.bot.send_message.call_args_list]
    assert any(messages["en"]["select_questions_to_modify"] in t for t in sent_texts)


def test_handle_final_confirmation_invalid_choice_answers_invalid(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    confirmation.handle_final_confirmation_choice(
        app_context,
        _call("final_2", user_id=user_id),
        _confirmation_callbacks(),
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["invalid_selection"],
    )


def test_handle_final_confirmation_no_language_prompts_use_start(app_context):
    confirmation.handle_final_confirmation_choice(
        app_context,
        _call("final_0", user_id=999),
        _confirmation_callbacks(),
    )

    sent_text = app_context.bot.send_message.call_args.args[1]
    assert "/start" in sent_text


def test_ask_which_responses_to_modify_builds_keyboard_and_logs_dependencies(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "regularity", "placeholder-regularity")
    app_context.sessions.set_data(user_id, "noticed_changes", "placeholder-noticed")
    app_context.sessions.set_data(user_id, "age", "placeholder-age")

    confirmation.ask_which_responses_to_modify(
        app_context, 456, user_id, "en", _confirmation_callbacks()
    )

    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    callback_datas = [btn.callback_data for row in keyboard.keyboard for btn in row]
    assert "modify_age" in callback_datas
    assert "modify_regularity" in callback_datas
    assert callback_datas[-1] == "modification_done"


def test_handle_modification_done_returns_to_final_confirmation(app_context, monkeypatch):
    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.confirmation.time.sleep", lambda _: None
    )
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    confirmation.handle_modification_selection(
        app_context,
        _call("modification_done", user_id=user_id),
        _confirmation_callbacks(),
    )

    sent_texts = [c.args[1] for c in app_context.bot.send_message.call_args_list]
    assert any(messages["en"]["responses_summary_header"] in t for t in sent_texts)


def test_handle_modification_selection_logs_dependencies(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "regularity", "placeholder-regularity")
    app_context.sessions.set_data(user_id, "noticed_changes", "placeholder-noticed")
    ask_regularity = MagicMock()

    confirmation.handle_modification_selection(
        app_context,
        _call("modify_regularity", user_id=user_id),
        _confirmation_callbacks(ask_regularity=ask_regularity),
    )

    assert app_context.sessions.get_data(user_id, "modifying_field") == "regularity"
    ask_regularity.assert_called_once_with(456, user_id, "en")


def _regularity_option(*, in_skip_set: bool) -> str:
    options = messages["en"]["options"]["regularity"]
    for idx, option in enumerate(options):
        if (idx in REGULARITY_SKIP_TO_WISHLIST_INDICES) == in_skip_set:
            return option
    raise AssertionError("no regularity option matches the requested branch")


def _noticed_changes_option(*, requires_detail: bool) -> str:
    options = messages["en"]["options"]["noticed_changes"]
    for idx, option in enumerate(options):
        if (idx in NOTICED_CHANGES_DETAIL_REQUIRING_INDICES) == requires_detail:
            return option
    raise AssertionError("no noticed_changes option matches the requested branch")


def test_clear_dependent_fields_regularity_skips_to_wishlist_clears_followups(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "noticed_changes", "placeholder-noticed")
    app_context.sessions.set_data(user_id, "changes_detail", ["placeholder-detail"])
    app_context.sessions.set_data(user_id, "custom_changes", ["placeholder-custom"])

    cleared = confirmation.clear_dependent_fields(
        app_context,
        user_id,
        "regularity",
        _regularity_option(in_skip_set=False),
        _regularity_option(in_skip_set=True),
        get_anonymous_id=lambda _uid: "anon",
    )

    assert "noticed_changes" in cleared
    assert "changes_detail" in cleared
    assert "custom_changes" in cleared
    assert app_context.sessions.get_data(user_id, "noticed_changes") is None


def test_clear_dependent_fields_noticed_changes_to_no_clears_detail(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "changes_detail", ["placeholder-detail"])
    app_context.sessions.set_data(user_id, "custom_changes", ["placeholder-custom"])

    cleared = confirmation.clear_dependent_fields(
        app_context,
        user_id,
        "noticed_changes",
        _noticed_changes_option(requires_detail=True),
        _noticed_changes_option(requires_detail=False),
        get_anonymous_id=lambda _uid: "anon",
    )

    assert "changes_detail" in cleared
    assert "custom_changes" in cleared


def test_clear_dependent_fields_unknown_field_returns_empty(app_context):
    cleared = confirmation.clear_dependent_fields(
        app_context, 123, "age", "old", "new", get_anonymous_id=lambda _: "anon"
    )

    assert cleared == []


def test_clear_dependent_fields_regularity_keeping_followups_clears_nothing(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "noticed_changes", "placeholder-noticed")
    options = messages["en"]["options"]["regularity"]
    follow_up_options = [
        opt for idx, opt in enumerate(options) if idx not in REGULARITY_SKIP_TO_WISHLIST_INDICES
    ]
    assert len(follow_up_options) >= 2, "test needs two distinct follow-up regularity options"

    cleared = confirmation.clear_dependent_fields(
        app_context,
        user_id,
        "regularity",
        follow_up_options[0],
        follow_up_options[1],
        get_anonymous_id=lambda _: "anon",
    )

    assert cleared == []
    assert app_context.sessions.get_data(user_id, "noticed_changes") is not None


def test_handle_modification_selection_invalid_field_warns_invalid(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    confirmation.handle_modification_selection(
        app_context,
        _call("modify_unknown", user_id=user_id),
        _confirmation_callbacks(),
    )

    sent_texts = [c.args[1] for c in app_context.bot.send_message.call_args_list]
    assert messages["en"]["invalid_selection"] in sent_texts


def test_confirmation_callbacks_from_context_uses_provided_actions(app_context):
    actions = SimpleNamespace(
        ask_enjoyment=MagicMock(),
        ask_purpose_visit=MagicMock(),
        ask_regularity=MagicMock(),
        ask_accessibility=MagicMock(),
        ask_noticed_changes=MagicMock(),
        ask_changes_detail=MagicMock(),
        ask_wishlist=MagicMock(),
        ask_kremenchuk=MagicMock(),
        ask_age=MagicMock(),
        ask_gender=MagicMock(),
        ask_occupation=MagicMock(),
        ask_income=MagicMock(),
        ask_description=MagicMock(),
        ask_visitor_type=MagicMock(),
        ask_duration=MagicMock(),
        ask_continue_or_stop=MagicMock(),
        save_data_and_restart=MagicMock(),
        get_anonymous_id=MagicMock(return_value="anon"),
    )

    cbs = confirmation.callbacks_from_context(app_context, actions)

    assert cbs.ask_enjoyment is actions.ask_enjoyment
    assert cbs.get_anonymous_id is actions.get_anonymous_id


def test_final_confirmation_question_class_methods_dispatch(app_context, monkeypatch):
    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.confirmation.time.sleep", lambda _: None
    )
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    final_q = confirmation.FinalConfirmationQuestion()
    mod_q = confirmation.ModificationQuestion()

    final_q.ask(app_context, 456, user_id, "en")
    final_q.handle(app_context, _call("final_2", user_id=user_id))
    mod_q.ask(app_context, 456, user_id, "en")
    mod_q.handle(app_context, _call("modify_unknown", user_id=user_id))


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
