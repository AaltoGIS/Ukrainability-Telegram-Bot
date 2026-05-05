"""Extra coverage for the survey question modules."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import (
    accessibility,
    changes_detail,
    description as description_q,
    duration,
    frequency,
    kremenchuk,
    location as location_q,
    noticed_changes,
    regularity,
    restart,
    visitor_type,
    wishlist,
)
from ukrainability_telegram_bot.survey.questions.accessibility import (
    AccessibilityCallbacks,
)
from ukrainability_telegram_bot.survey.questions.base import DescriptionCallbacks
from ukrainability_telegram_bot.survey.questions.changes_detail import (
    ChangesDetailCallbacks,
)
from ukrainability_telegram_bot.survey.questions.duration import DurationCallbacks
from ukrainability_telegram_bot.survey.questions.frequency import FrequencyCallbacks
from ukrainability_telegram_bot.survey.questions.kremenchuk import KremenchukCallbacks
from ukrainability_telegram_bot.survey.questions.noticed_changes import (
    NoticedChangesCallbacks,
)
from ukrainability_telegram_bot.survey.questions.regularity import RegularityCallbacks
from ukrainability_telegram_bot.survey.questions.restart import RestartCallbacks
from ukrainability_telegram_bot.survey.questions.visitor_type import VisitorTypeCallbacks
from ukrainability_telegram_bot.survey.questions.wishlist import WishlistCallbacks


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


def _text_message(text, user_id=123, chat_id=456):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        text=text,
        content_type="text",
    )


def _voice_message(file_id="vid", user_id=123, chat_id=456):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        content_type="voice",
        voice=SimpleNamespace(file_id=file_id),
    )


def _venue_message(user_id=123, chat_id=456):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        content_type="venue",
        venue=SimpleNamespace(
            location=SimpleNamespace(latitude=49.0, longitude=33.4),
            title="Park",
            address="Main",
        ),
    )


# -------- visitor_type --------


def _visitor_callbacks(**overrides):
    values = {
        "ask_duration": MagicMock(),
        "ask_final_confirmation": MagicMock(),
    }
    values.update(overrides)
    return VisitorTypeCallbacks(**values)


def test_ask_visitor_type_seeds_keyboard_and_state(app_context):
    visitor_type.ask_visitor_type(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "awaiting_multiple_select") == "visitor_type"
    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    callbacks = [b.callback_data for row in keyboard.keyboard for b in row]
    assert "visitor_done" in callbacks
    assert any(cd.startswith("visitor_") for cd in callbacks if cd != "visitor_done")


def test_handle_visitor_type_toggle_select_then_unselect(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    options = messages["en"]["visitor_type_options"][:-1]

    visitor_type.handle_visitor_type_selection(app_context, _call("visitor_0", user_id=user_id))
    assert options[0] in app_context.sessions.get_data(user_id, "visitor_type", [])

    visitor_type.handle_visitor_type_selection(app_context, _call("visitor_0", user_id=user_id))
    assert options[0] not in app_context.sessions.get_data(user_id, "visitor_type", [])


def test_visitor_type_done_without_selection_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "visitor_type", [])
    app_context.sessions.set_data(user_id, "custom_visitor_types", [])

    visitor_type.handle_visitor_type_selection(
        app_context,
        _call("visitor_done", user_id=user_id),
        _visitor_callbacks(),
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["please_select_at_least_one"],
    )


def test_visitor_type_done_modifying_returns_to_final_confirmation(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "visitor_type", ["placeholder-visitor-1"])
    app_context.sessions.set_data(user_id, "custom_visitor_types", [])
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _visitor_callbacks()

    visitor_type.handle_visitor_type_selection(
        app_context, _call("visitor_done", user_id=user_id), cbs
    )

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")
    cbs.ask_duration.assert_not_called()


def test_visitor_type_invalid_index_answers_invalid(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    visitor_type.handle_visitor_type_selection(app_context, _call("visitor_999", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["invalid_selection"]
    )


def test_visitor_type_class_dispatch(app_context):
    q = visitor_type.VisitorTypeQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("visitor_999", user_id=123))


def test_visitor_type_callbacks_from_context(app_context):
    actions = SimpleNamespace(ask_duration=MagicMock(), ask_final_confirmation=MagicMock())
    cbs = visitor_type.callbacks_from_context(app_context, actions)
    assert cbs.ask_duration is actions.ask_duration


# -------- accessibility --------


def _accessibility_callbacks(**overrides):
    values = {"ask_regularity": MagicMock(), "ask_final_confirmation": MagicMock()}
    values.update(overrides)
    return AccessibilityCallbacks(**values)


def test_ask_accessibility_seeds_keyboard_and_state(app_context):
    accessibility.ask_accessibility(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "awaiting_multiple_select") == "accessibility"
    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    callbacks = [b.callback_data for row in keyboard.keyboard for b in row]
    assert "accessibility_done" in callbacks


def test_accessibility_toggle_select(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    accessibility.handle_accessibility_selection(
        app_context, _call("accessibility_0", user_id=user_id)
    )
    selected = app_context.sessions.get_data(user_id, "accessibility", [])
    assert len(selected) == 1


def test_accessibility_done_without_selection_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "accessibility", [])
    app_context.sessions.set_data(user_id, "custom_accessibility", [])

    accessibility.handle_accessibility_selection(
        app_context,
        _call("accessibility_done", user_id=user_id),
        _accessibility_callbacks(),
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["please_select_at_least_one"]
    )


def test_accessibility_done_advances_to_regularity(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "accessibility", ["placeholder-access-1"])
    app_context.sessions.set_data(user_id, "custom_accessibility", [])
    cbs = _accessibility_callbacks()

    accessibility.handle_accessibility_selection(
        app_context, _call("accessibility_done", user_id=user_id), cbs
    )

    cbs.ask_regularity.assert_called_once_with(456, user_id, "en")


def test_accessibility_done_modifying_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "accessibility", ["placeholder-access-1"])
    app_context.sessions.set_data(user_id, "custom_accessibility", [])
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _accessibility_callbacks()

    accessibility.handle_accessibility_selection(
        app_context, _call("accessibility_done", user_id=user_id), cbs
    )

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_accessibility_class_dispatch(app_context):
    q = accessibility.AccessibilityQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("accessibility_999", user_id=123))


def test_accessibility_callbacks_from_context(app_context):
    actions = SimpleNamespace(ask_regularity=MagicMock(), ask_final_confirmation=MagicMock())
    cbs = accessibility.callbacks_from_context(app_context, actions)
    assert cbs.ask_regularity is actions.ask_regularity


# -------- duration --------


def _duration_callbacks(**overrides):
    values = {"ask_accessibility": MagicMock(), "ask_final_confirmation": MagicMock()}
    values.update(overrides)
    return DurationCallbacks(**values)


def test_ask_duration_sets_state_and_keyboard(app_context):
    duration.ask_duration(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "current_question") == "duration"
    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "duration_0"


def test_handle_duration_selection_marks_choice(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    options = messages["en"]["duration_options"]

    duration.handle_duration_selection(app_context, _call("duration_1", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "temp_duration_visit") == options[1]


def test_confirm_duration_advances_to_accessibility(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_duration_visit", "placeholder-duration")
    cbs = _duration_callbacks()

    duration.confirm_duration(app_context, _call("confirm_duration", user_id=user_id), cbs)

    assert app_context.sessions.get_data(user_id, "duration_visit") == "placeholder-duration"
    cbs.ask_accessibility.assert_called_once_with(456, user_id, "en")


def test_confirm_duration_modifying_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_duration_visit", "placeholder-duration")
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _duration_callbacks()

    duration.confirm_duration(app_context, _call("confirm_duration", user_id=user_id), cbs)

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_confirm_duration_without_temp_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    duration.confirm_duration(
        app_context, _call("confirm_duration", user_id=user_id), _duration_callbacks()
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["select_option_first"]
    )


def test_duration_class_dispatch(app_context):
    q = duration.DurationQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("duration_0", user_id=123))


def test_duration_callbacks_from_context(app_context):
    actions = SimpleNamespace(ask_accessibility=MagicMock(), ask_final_confirmation=MagicMock())
    cbs = duration.callbacks_from_context(app_context, actions)
    assert cbs.ask_accessibility is actions.ask_accessibility


# -------- regularity --------


def _regularity_callbacks(**overrides):
    values = {
        "ask_noticed_changes": MagicMock(),
        "ask_wishlist": MagicMock(),
        "ask_final_confirmation": MagicMock(),
        "clear_dependent_fields": MagicMock(return_value=[]),
        "get_anonymous_id": MagicMock(return_value="anon"),
    }
    values.update(overrides)
    return RegularityCallbacks(**values)


def test_ask_regularity_sends_keyboard(app_context):
    regularity.ask_regularity(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "current_question") == "regularity"
    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "regularity_0"


def test_handle_regularity_selection_marks_choice(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    options = messages["en"]["options"]["regularity"]

    regularity.handle_regularity_selection(app_context, _call("regularity_2", user_id=user_id))

    assert app_context.sessions.get_data(user_id, "temp_regularity") == options[2]
    assert app_context.sessions.get_data(user_id, "temp_regularity_idx") == 2


def test_handle_regularity_invalid_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    regularity.handle_regularity_selection(app_context, _call("regularity_999", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["invalid_selection"]
    )


def test_confirm_regularity_changing_value_calls_clear_dependent_fields(app_context):
    user_id = 123
    options = messages["en"]["options"]["regularity"]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_regularity", options[0])
    app_context.sessions.set_data(user_id, "temp_regularity_idx", 0)
    app_context.sessions.set_data(user_id, "regularity", options[1])
    cleared = MagicMock(return_value=["noticed_changes"])
    cbs = _regularity_callbacks(clear_dependent_fields=cleared)

    regularity.confirm_regularity(app_context, _call("confirm_regularity", user_id=user_id), cbs)

    cleared.assert_called_once()
    cbs.ask_noticed_changes.assert_called_once_with(456, user_id, "en")


def test_confirm_regularity_without_temp_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    regularity.confirm_regularity(
        app_context, _call("confirm_regularity", user_id=user_id), _regularity_callbacks()
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["select_option_first"]
    )


def test_confirm_regularity_modifying_with_followup_keeps_modifying(app_context):
    user_id = 123
    options = messages["en"]["options"]["regularity"]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_regularity", options[0])
    app_context.sessions.set_data(user_id, "temp_regularity_idx", 0)
    app_context.sessions.set_data(user_id, "regularity", "")
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _regularity_callbacks()

    regularity.confirm_regularity(app_context, _call("confirm_regularity", user_id=user_id), cbs)

    cbs.ask_noticed_changes.assert_called_once_with(456, user_id, "en")
    cbs.ask_final_confirmation.assert_not_called()


def test_confirm_regularity_modifying_skips_to_final(app_context):
    user_id = 123
    options = messages["en"]["options"]["regularity"]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_regularity", options[4])
    app_context.sessions.set_data(user_id, "temp_regularity_idx", 4)
    app_context.sessions.set_data(user_id, "regularity", "")
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_data(user_id, "modifying_field", "regularity")
    cbs = _regularity_callbacks()

    regularity.confirm_regularity(app_context, _call("confirm_regularity", user_id=user_id), cbs)

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_regularity_class_dispatch(app_context):
    q = regularity.RegularityQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("regularity_0", user_id=123))


def test_regularity_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        ask_noticed_changes=MagicMock(),
        ask_wishlist=MagicMock(),
        ask_final_confirmation=MagicMock(),
        clear_dependent_fields=MagicMock(),
        get_anonymous_id=MagicMock(),
    )
    cbs = regularity.callbacks_from_context(app_context, actions)
    assert cbs.ask_wishlist is actions.ask_wishlist


# -------- noticed_changes --------


def _noticed_changes_callbacks(**overrides):
    values = {
        "ask_changes_detail": MagicMock(),
        "ask_wishlist": MagicMock(),
        "ask_final_confirmation": MagicMock(),
        "clear_dependent_fields": MagicMock(return_value=[]),
        "get_anonymous_id": MagicMock(return_value="anon"),
    }
    values.update(overrides)
    return NoticedChangesCallbacks(**values)


def test_ask_noticed_changes_sends_keyboard(app_context):
    noticed_changes.ask_noticed_changes(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "current_question") == "noticed_changes"
    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "noticed_changes_0"


def test_handle_noticed_changes_selection_marks_choice(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    noticed_changes.handle_noticed_changes_selection(
        app_context, _call("noticed_changes_1", user_id=user_id)
    )

    options = messages["en"]["options"]["noticed_changes"]
    assert app_context.sessions.get_data(user_id, "temp_noticed_changes") == options[1]


def test_handle_noticed_changes_invalid_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    noticed_changes.handle_noticed_changes_selection(
        app_context, _call("noticed_changes_999", user_id=user_id)
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["invalid_selection"]
    )


def test_confirm_noticed_changes_modifying_no_change_returns_to_final(app_context):
    user_id = 123
    options = messages["en"]["options"]["noticed_changes"]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_noticed_changes", options[2])
    app_context.sessions.set_data(user_id, "temp_noticed_changes_idx", 2)
    app_context.sessions.set_data(user_id, "noticed_changes", "")
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_data(user_id, "modifying_field", "noticed_changes")
    cbs = _noticed_changes_callbacks()

    noticed_changes.confirm_noticed_changes(
        app_context, _call("confirm_noticed_changes", user_id=user_id), cbs
    )

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_confirm_noticed_changes_without_temp_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    noticed_changes.confirm_noticed_changes(
        app_context,
        _call("confirm_noticed_changes", user_id=user_id),
        _noticed_changes_callbacks(),
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["select_option_first"]
    )


def test_confirm_noticed_changes_value_change_invokes_clear_dependent_fields(app_context):
    user_id = 123
    options = messages["en"]["options"]["noticed_changes"]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_noticed_changes", options[0])
    app_context.sessions.set_data(user_id, "temp_noticed_changes_idx", 0)
    app_context.sessions.set_data(user_id, "noticed_changes", options[2])
    cleared = MagicMock(return_value=["changes_detail"])

    noticed_changes.confirm_noticed_changes(
        app_context,
        _call("confirm_noticed_changes", user_id=user_id),
        _noticed_changes_callbacks(clear_dependent_fields=cleared),
    )

    cleared.assert_called_once()


def test_noticed_changes_class_dispatch(app_context):
    q = noticed_changes.NoticedChangesQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("noticed_changes_0", user_id=123))


def test_noticed_changes_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        ask_changes_detail=MagicMock(),
        ask_wishlist=MagicMock(),
        ask_final_confirmation=MagicMock(),
        clear_dependent_fields=MagicMock(),
        get_anonymous_id=MagicMock(),
    )
    cbs = noticed_changes.callbacks_from_context(app_context, actions)
    assert cbs.ask_changes_detail is actions.ask_changes_detail


# -------- changes_detail --------


def _changes_detail_callbacks(**overrides):
    values = {
        "ask_wishlist": MagicMock(),
        "ask_final_confirmation": MagicMock(),
        "get_anonymous_id": MagicMock(return_value="anon"),
    }
    values.update(overrides)
    return ChangesDetailCallbacks(**values)


def test_ask_changes_detail_sends_keyboard(app_context):
    changes_detail.ask_changes_detail(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "awaiting_multiple_select") == "changes_detail"


def test_changes_detail_toggle_select(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    cbs = _changes_detail_callbacks()

    changes_detail.handle_changes_detail_selection(
        app_context, _call("changes_detail_0", user_id=user_id), cbs
    )
    selected_after = app_context.sessions.get_data(user_id, "changes_detail", [])
    assert len(selected_after) == 1


def test_changes_detail_done_without_selection_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "changes_detail", [])
    app_context.sessions.set_data(user_id, "custom_changes", [])

    changes_detail.handle_changes_detail_selection(
        app_context, _call("changes_detail_done", user_id=user_id), _changes_detail_callbacks()
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["please_select_at_least_one"]
    )


def test_changes_detail_done_modifying_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "changes_detail", ["placeholder-change-1"])
    app_context.sessions.set_data(user_id, "custom_changes", [])
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _changes_detail_callbacks()

    changes_detail.handle_changes_detail_selection(
        app_context, _call("changes_detail_done", user_id=user_id), cbs
    )

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_changes_detail_invalid_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    changes_detail.handle_changes_detail_selection(
        app_context, _call("changes_detail_999", user_id=user_id)
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["invalid_selection"]
    )


def test_changes_detail_class_dispatch(app_context):
    q = changes_detail.ChangesDetailQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("changes_detail_0", user_id=123))


def test_changes_detail_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        ask_wishlist=MagicMock(),
        ask_final_confirmation=MagicMock(),
        get_anonymous_id=MagicMock(),
    )
    cbs = changes_detail.callbacks_from_context(app_context, actions)
    assert cbs.ask_wishlist is actions.ask_wishlist


# -------- wishlist --------


def _wishlist_callbacks(**overrides):
    values = {
        "ask_age": MagicMock(),
        "ask_final_confirmation": MagicMock(),
        "get_anonymous_id": MagicMock(return_value="anon"),
    }
    values.update(overrides)
    return WishlistCallbacks(**values)


def test_ask_wishlist_sends_keyboard(app_context):
    wishlist.ask_wishlist(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "awaiting_multiple_select") == "wishlist"


def test_wishlist_toggle_select_then_unselect(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    options = messages["en"]["options"]["wishlist"][:-1]

    wishlist.handle_wishlist_selection(app_context, _call("wishlist_0", user_id=user_id))
    assert options[0] in app_context.sessions.get_data(user_id, "wishlist", [])

    wishlist.handle_wishlist_selection(app_context, _call("wishlist_0", user_id=user_id))
    assert options[0] not in app_context.sessions.get_data(user_id, "wishlist", [])


def test_wishlist_done_without_selection_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "wishlist", [])
    app_context.sessions.set_data(user_id, "custom_wishlist", [])

    wishlist.handle_wishlist_selection(
        app_context, _call("wishlist_done", user_id=user_id), _wishlist_callbacks()
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["please_select_at_least_one"]
    )


def test_wishlist_done_modifying_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "wishlist", ["placeholder-wish-1"])
    app_context.sessions.set_data(user_id, "custom_wishlist", [])
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _wishlist_callbacks()

    wishlist.handle_wishlist_selection(app_context, _call("wishlist_done", user_id=user_id), cbs)

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_wishlist_invalid_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    wishlist.handle_wishlist_selection(app_context, _call("wishlist_999", user_id=user_id))

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["invalid_selection"]
    )


def test_wishlist_class_dispatch(app_context):
    q = wishlist.WishlistQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("wishlist_0", user_id=123))


def test_wishlist_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        ask_age=MagicMock(),
        ask_final_confirmation=MagicMock(),
        get_anonymous_id=MagicMock(),
    )
    cbs = wishlist.callbacks_from_context(app_context, actions)
    assert cbs.ask_age is actions.ask_age


# -------- frequency --------


def _frequency_callbacks(**overrides):
    values = {
        "ask_noticed_changes": MagicMock(),
        "ask_wishlist": MagicMock(),
        "ask_final_confirmation": MagicMock(),
        "clear_dependent_fields": MagicMock(return_value=[]),
        "get_anonymous_id": MagicMock(return_value="anon"),
    }
    values.update(overrides)
    return FrequencyCallbacks(**values)


def test_ask_frequency_change_sends_keyboard(app_context):
    frequency.ask_frequency_change(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "current_question") == "frequency_change"


def test_frequency_change_invalid_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    frequency.handle_frequency_change_selection(
        app_context, _call("frequency_change_999", user_id=user_id)
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["invalid_selection"]
    )


def test_frequency_change_normal_path_advances_to_noticed_changes(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    cbs = _frequency_callbacks()

    frequency.handle_frequency_change_selection(
        app_context, _call("frequency_change_0", user_id=user_id), cbs
    )

    cbs.ask_noticed_changes.assert_called_once_with(456, user_id, "en")


def test_frequency_change_modifying_did_not_visit_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _frequency_callbacks()

    frequency.handle_frequency_change_selection(
        app_context, _call("frequency_change_3", user_id=user_id), cbs
    )

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_frequency_change_modifying_normal_to_noticed_changes(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _frequency_callbacks()

    frequency.handle_frequency_change_selection(
        app_context, _call("frequency_change_0", user_id=user_id), cbs
    )

    cbs.ask_noticed_changes.assert_called_once_with(456, user_id, "en")


def test_frequency_change_class_dispatch(app_context):
    q = frequency.FrequencyQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("frequency_change_999", user_id=123))


def test_frequency_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        ask_noticed_changes=MagicMock(),
        ask_wishlist=MagicMock(),
        ask_final_confirmation=MagicMock(),
        clear_dependent_fields=MagicMock(),
        get_anonymous_id=MagicMock(),
    )
    cbs = frequency.callbacks_from_context(app_context, actions)
    assert cbs.ask_wishlist is actions.ask_wishlist


# -------- kremenchuk --------


def _kremenchuk_callbacks(**overrides):
    values = {"ask_description": MagicMock(), "ask_final_confirmation": MagicMock()}
    values.update(overrides)
    return KremenchukCallbacks(**values)


def test_ask_kremenchuk_sends_keyboard(app_context):
    kremenchuk.ask_kremenchuk(app_context, 456, 123, "en")

    assert app_context.sessions.get_data(123, "awaiting_multiple_select") == "kremenchuk"


def test_kremenchuk_pick_option_stores_selection(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    kremenchuk.handle_kremenchuk_selection(app_context, _call("kremenchuk_0", user_id=user_id))

    selected = app_context.sessions.get_data(user_id, "kremenchuk", "")
    assert selected != ""


def test_kremenchuk_done_without_selection_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "kremenchuk", "")
    app_context.sessions.set_data(user_id, "custom_kremenchuk", [])

    kremenchuk.handle_kremenchuk_selection(
        app_context, _call("kremenchuk_done", user_id=user_id), _kremenchuk_callbacks()
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["please_select_at_least_one"]
    )


def test_kremenchuk_done_modifying_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "kremenchuk", "placeholder-kremenchuk")
    app_context.sessions.set_data(user_id, "custom_kremenchuk", [])
    app_context.sessions.set_data(user_id, "modifying", True)
    cbs = _kremenchuk_callbacks()

    kremenchuk.handle_kremenchuk_selection(
        app_context, _call("kremenchuk_done", user_id=user_id), cbs
    )

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_kremenchuk_class_dispatch(app_context):
    q = kremenchuk.KremenchukQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("kremenchuk_999", user_id=123))


def test_kremenchuk_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        ask_description=MagicMock(),
        ask_final_confirmation=MagicMock(),
    )
    cbs = kremenchuk.callbacks_from_context(app_context, actions)
    assert cbs.ask_description is actions.ask_description


# -------- restart --------


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


def test_ask_continue_or_stop_sends_keyboard(app_context, monkeypatch):
    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.restart.time.sleep", lambda _: None
    )
    user_id = 123
    app_context.sessions.set_data(user_id, "nickname", "SafeNick")

    restart.ask_continue_or_stop(app_context, 456, user_id, "en")

    keyboards = [c.kwargs.get("reply_markup") for c in app_context.bot.send_message.call_args_list]
    keyboard = next(k for k in keyboards if k is not None)
    cds = [b.callback_data for row in keyboard.keyboard for b in row]
    assert cds == ["continue_0", "continue_1"]


def test_handle_continue_stop_chosen_sends_restart_button(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    cbs = _restart_callbacks()

    restart.handle_continue_or_stop_selection(
        app_context, _call("continue_1", user_id=user_id), cbs
    )

    sent_keyboards = [
        c.kwargs.get("reply_markup") for c in app_context.bot.send_message.call_args_list
    ]
    keyboard = next(k for k in sent_keyboards if k is not None)
    cds = [b.callback_data for row in keyboard.keyboard for b in row]
    assert "restart" in cds


def test_handle_continue_invalid_warns(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    restart.handle_continue_or_stop_selection(
        app_context, _call("continue_99", user_id=user_id), _restart_callbacks()
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id", messages["en"]["invalid_selection"]
    )


def test_handle_continue_no_language_prompts_use_start(app_context):
    restart.handle_continue_or_stop_selection(
        app_context, _call("continue_0", user_id=999), _restart_callbacks()
    )

    sent_text = app_context.bot.send_message.call_args.args[1]
    assert "/start" in sent_text


def test_save_data_and_restart_no_consent_clears_message_ids_and_returns_true(app_context):
    user_id = 123
    cbs = _restart_callbacks()

    result = restart.save_data_and_restart(app_context, 456, user_id, "en", False, cbs)

    assert result is True
    cbs.clear_message_ids.assert_called_once_with(user_id)


def test_save_data_and_restart_no_consent_with_restart_calls_send_welcome(app_context):
    user_id = 123
    cbs = _restart_callbacks()

    restart.save_data_and_restart(app_context, 456, user_id, "en", True, cbs)

    cbs.send_welcome.assert_called_once_with(chat_id=456, user_id=user_id, start_param="restart")


def test_save_data_and_restart_with_consent_persists_response_and_clears_session(app_context):
    user_id = 123
    app_context.sessions.set_profile(user_id, "consent", True)
    app_context.sessions.set_data(user_id, "location", {"latitude": 49.0, "longitude": 33.0})
    cbs = _restart_callbacks()

    result = restart.save_data_and_restart(app_context, 456, user_id, "en", False, cbs)

    assert result is True
    assert app_context.sessions.get_data(user_id, "location") is None


def test_save_data_and_restart_with_consent_handles_encryption_error(app_context, monkeypatch):
    user_id = 123
    app_context.sessions.set_profile(user_id, "consent", True)
    cbs = _restart_callbacks()
    from ukrainability_telegram_bot.survey.persistence import EncryptionUnavailableError

    def boom(*args, **kwargs):
        raise EncryptionUnavailableError("nope")

    monkeypatch.setattr("ukrainability_telegram_bot.survey.questions.restart.save_response", boom)

    result = restart.save_data_and_restart(app_context, 456, user_id, "en", False, cbs)

    assert result is False
    sent_texts = [c.args[1] for c in app_context.bot.send_message.call_args_list]
    assert messages["en"]["security_error"] in sent_texts


def test_save_data_and_restart_with_consent_handles_database_error(app_context, monkeypatch):
    user_id = 123
    app_context.sessions.set_profile(user_id, "consent", True)
    cbs = _restart_callbacks()
    from ukrainability_telegram_bot.survey.persistence import DatabaseSaveError

    def boom(*args, **kwargs):
        raise DatabaseSaveError("nope")

    monkeypatch.setattr("ukrainability_telegram_bot.survey.questions.restart.save_response", boom)

    result = restart.save_data_and_restart(app_context, 456, user_id, "en", False, cbs)

    assert result is False
    sent_texts = [c.args[1] for c in app_context.bot.send_message.call_args_list]
    assert messages["en"]["database_error"] in sent_texts


def test_save_data_and_restart_persistence_uses_existing_nickname(app_context, monkeypatch):
    user_id = 123
    app_context.sessions.set_profile(user_id, "consent", True)
    cbs = _restart_callbacks()
    captured = {}

    def fake_save(ctx, uid, language, *, nickname_provider):
        captured["nickname"] = nickname_provider()

    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.restart.save_response", fake_save
    )

    restart.save_data_and_restart(app_context, 456, user_id, "en", False, cbs)

    assert captured["nickname"] == "Nick Name 1"
    cbs.save_user_nickname.assert_not_called()


def test_save_data_and_restart_persistence_generates_new_nickname(app_context, monkeypatch):
    user_id = 123
    app_context.sessions.set_profile(user_id, "consent", True)
    cbs = _restart_callbacks(get_user_nickname=MagicMock(return_value=None))
    captured = {}

    def fake_save(ctx, uid, language, *, nickname_provider):
        captured["nickname"] = nickname_provider()

    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.restart.save_response", fake_save
    )

    restart.save_data_and_restart(app_context, 456, user_id, "en", False, cbs)

    assert captured["nickname"] == "Nick Name 2"
    cbs.save_user_nickname.assert_called_once_with("hash", "Nick Name 2")


def test_continue_class_dispatch(app_context, monkeypatch):
    monkeypatch.setattr(
        "ukrainability_telegram_bot.survey.questions.restart.time.sleep", lambda _: None
    )
    app_context.sessions.set_data(123, "nickname", "X")
    q = restart.ContinueQuestion()
    q.ask(app_context, 456, 123, "en")
    q.handle(app_context, _call("continue_99", user_id=123))


def test_restart_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        handle_location_step=MagicMock(),
        send_welcome=MagicMock(),
        get_user_hash=MagicMock(),
        get_user_nickname=MagicMock(),
        generate_unique_nickname=MagicMock(),
        save_user_nickname=MagicMock(),
        clear_message_ids=MagicMock(),
    )
    cbs = restart.callbacks_from_context(app_context, actions)
    assert cbs.location_handler is actions.handle_location_step


# -------- description --------


def _description_callbacks(**overrides):
    values = {
        "ask_final_confirmation": MagicMock(),
        "description_handler": MagicMock(),
    }
    values.update(overrides)
    return DescriptionCallbacks(**values)


def test_ask_description_sends_skip_keyboard(app_context):
    description_q.ask_description(app_context, 456, 123, "en", _description_callbacks())

    keyboard = app_context.bot.send_message.call_args.kwargs["reply_markup"]
    assert keyboard.keyboard[0][0].callback_data == "description_skip"


def test_ask_description_pulls_kremenchuk_from_profile(app_context):
    user_id = 123
    app_context.sessions.set_profile(user_id, "kremenchuk", "placeholder-kremenchuk")

    description_q.ask_description(app_context, 456, user_id, "en", _description_callbacks())

    assert app_context.sessions.get_data(user_id, "kremenchuk") == "placeholder-kremenchuk"


def test_ask_description_already_done_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "description_done", True)
    cbs = _description_callbacks()

    description_q.ask_description(app_context, 456, user_id, "en", cbs)

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_ask_description_modifying_other_field_returns_to_final(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "modifying", True)
    app_context.sessions.set_data(user_id, "modifying_field", "age")
    cbs = _description_callbacks()

    description_q.ask_description(app_context, 456, user_id, "en", cbs)

    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_handle_description_skip_marks_done_and_advances(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    cbs = _description_callbacks()

    description_q.handle_description_skip(
        app_context, _call("description_skip", user_id=user_id), cbs
    )

    assert app_context.sessions.get_data(user_id, "description_done") is True
    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_handle_description_text_stores_description_and_advances(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    cbs = _description_callbacks()

    description_q.handle_description(
        app_context, _text_message("Beautiful place", user_id=user_id), cbs
    )

    assert app_context.sessions.get_data(user_id, "description") == "Beautiful place"
    assert app_context.sessions.get_data(user_id, "description_done") is True
    cbs.ask_final_confirmation.assert_called_once_with(456, user_id, "en")


def test_handle_description_unsupported_content_reprompts(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    cbs = _description_callbacks()
    photo_msg = SimpleNamespace(
        chat=SimpleNamespace(id=456),
        from_user=SimpleNamespace(id=user_id),
        content_type="photo",
    )

    description_q.handle_description(app_context, photo_msg, cbs)

    sent_text = app_context.bot.send_message.call_args.args[1]
    assert sent_text == messages["en"]["please_send_text_or_voice"]
    app_context.bot.register_next_step_handler_by_chat_id.assert_called_once()


def test_handle_description_no_language_prompts_use_start(app_context):
    cbs = _description_callbacks()

    description_q.handle_description(app_context, _text_message("hi", user_id=999), cbs)

    sent_text = app_context.bot.send_message.call_args.args[1]
    assert "/start" in sent_text


def test_description_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        ask_final_confirmation=MagicMock(),
        handle_description=MagicMock(),
    )
    cbs = description_q.callbacks_from_context(app_context, actions)
    assert cbs.ask_final_confirmation is actions.ask_final_confirmation


# -------- location: extra branches --------


def test_location_venue_response_stores_full_metadata(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    ask_purpose = MagicMock()
    cbs = location_q.LocationCallbacks(
        update_activity_timestamp=MagicMock(),
        send_welcome=MagicMock(),
        ask_purpose_visit=ask_purpose,
        location_handler=MagicMock(),
    )

    location_q.handle_location_step(app_context, _venue_message(user_id=user_id), cbs)

    stored = app_context.sessions.get_data(user_id, "location")
    assert stored["venue_title"] == "Park"
    assert stored["venue_address"] == "Main"
    ask_purpose.assert_called_once_with(456, user_id, "en")


def test_location_text_starting_with_start_calls_send_welcome(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    send_welcome = MagicMock()
    cbs = location_q.LocationCallbacks(
        update_activity_timestamp=MagicMock(),
        send_welcome=send_welcome,
        ask_purpose_visit=MagicMock(),
        location_handler=MagicMock(),
    )
    msg = _text_message("/start", user_id=user_id)

    location_q.handle_location_step(app_context, msg, cbs)

    send_welcome.assert_called_once_with(msg)


def test_location_text_other_command_reprompts(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    ask_purpose = MagicMock()
    cbs = location_q.LocationCallbacks(
        update_activity_timestamp=MagicMock(),
        send_welcome=MagicMock(),
        ask_purpose_visit=ask_purpose,
        location_handler=MagicMock(),
    )

    location_q.handle_location_step(app_context, _text_message("/help", user_id=user_id), cbs)

    ask_purpose.assert_not_called()


def test_location_unsupported_content_type_reprompts(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    cbs = location_q.LocationCallbacks(
        update_activity_timestamp=MagicMock(),
        send_welcome=MagicMock(),
        ask_purpose_visit=MagicMock(),
        location_handler=MagicMock(),
    )
    photo_msg = SimpleNamespace(
        chat=SimpleNamespace(id=456),
        from_user=SimpleNamespace(id=user_id),
        content_type="photo",
    )

    location_q.handle_location_step(app_context, photo_msg, cbs)

    cbs.ask_purpose_visit.assert_not_called()


def test_location_no_language_anywhere_prompts_use_start(app_context):
    cbs = location_q.LocationCallbacks(
        update_activity_timestamp=MagicMock(),
        send_welcome=MagicMock(),
        ask_purpose_visit=MagicMock(),
        location_handler=MagicMock(),
    )

    location_q.handle_location_step(app_context, _text_message("foo", user_id=999), cbs)

    sent_text = app_context.bot.send_message.call_args.args[1]
    assert "/start" in sent_text


def test_location_callbacks_from_context(app_context):
    actions = SimpleNamespace(
        update_activity_timestamp=MagicMock(),
        send_welcome=MagicMock(),
        ask_purpose_visit=MagicMock(),
        handle_location_step=MagicMock(),
    )
    cbs = location_q.callbacks_from_context(app_context, actions)
    assert cbs.location_handler is actions.handle_location_step
