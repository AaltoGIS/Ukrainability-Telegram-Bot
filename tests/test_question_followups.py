from types import SimpleNamespace
from unittest.mock import MagicMock

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import (
    changes_detail,
    kremenchuk,
    noticed_changes,
    wishlist,
)
from ukrainability_telegram_bot.survey.questions.changes_detail import (
    ChangesDetailCallbacks,
)
from ukrainability_telegram_bot.survey.questions.kremenchuk import KremenchukCallbacks
from ukrainability_telegram_bot.survey.questions.noticed_changes import (
    NoticedChangesCallbacks,
)
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


def test_confirm_noticed_changes_positive_asks_for_details(app_context):
    user_id = 123
    selected = messages["en"]["options"]["noticed_changes"][0]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "temp_noticed_changes", selected)
    app_context.sessions.set_data(user_id, "temp_noticed_changes_idx", 0)
    app_context.sessions.set_data(user_id, "noticed_changes", "")
    ask_changes_detail = MagicMock()
    callbacks = NoticedChangesCallbacks(
        ask_changes_detail=ask_changes_detail,
        ask_wishlist=MagicMock(),
        ask_final_confirmation=MagicMock(),
        clear_dependent_fields=MagicMock(return_value=[]),
        get_anonymous_id=MagicMock(return_value="anon"),
    )

    noticed_changes.confirm_noticed_changes(
        app_context,
        _call("confirm_noticed_changes", user_id=user_id),
        callbacks,
    )

    assert app_context.sessions.get_data(user_id, "noticed_changes") == selected
    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["response_confirmed"],
    )
    ask_changes_detail.assert_called_once_with(456, user_id, "en")


def test_changes_detail_done_with_selection_continues_to_wishlist(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "changes_detail", ["Services"])
    app_context.sessions.set_data(user_id, "custom_changes", ["More seating"])
    app_context.sessions.set_data(user_id, "awaiting_multiple_select", "changes_detail")
    ask_wishlist = MagicMock()
    callbacks = ChangesDetailCallbacks(
        ask_wishlist=ask_wishlist,
        ask_final_confirmation=MagicMock(),
        get_anonymous_id=MagicMock(return_value="anon"),
    )

    changes_detail.handle_changes_detail_selection(
        app_context,
        _call("changes_detail_done", user_id=user_id),
        callbacks,
    )

    assert app_context.sessions.get_data(user_id, "awaiting_multiple_select") is None
    ask_wishlist.assert_called_once_with(456, user_id, "en")
    response_call = [
        call for call in app_context.bot.send_message.call_args_list
        if call.kwargs.get("parse_mode") == "HTML"
    ][0]
    assert "Services; More seating" in response_call.args[1]


def test_wishlist_done_with_selection_continues_to_age(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "wishlist", ["More greenery"])
    app_context.sessions.set_data(user_id, "custom_wishlist", ["Benches"])
    app_context.sessions.set_data(user_id, "awaiting_multiple_select", "wishlist")
    ask_age = MagicMock()
    callbacks = WishlistCallbacks(
        ask_age=ask_age,
        ask_final_confirmation=MagicMock(),
        get_anonymous_id=MagicMock(return_value="anon"),
    )

    wishlist.handle_wishlist_selection(
        app_context,
        _call("wishlist_done", user_id=user_id),
        callbacks,
    )

    assert app_context.sessions.get_data(user_id, "awaiting_multiple_select") is None
    ask_age.assert_called_once_with(456, user_id, "en")


def test_kremenchuk_done_stores_profile_and_continues_to_description(app_context):
    user_id = 123
    selected = messages["en"]["options"]["kremenchuk"][1]
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "kremenchuk", selected)
    app_context.sessions.set_data(user_id, "custom_kremenchuk", [])
    app_context.sessions.set_data(user_id, "awaiting_multiple_select", "kremenchuk")
    ask_description = MagicMock()
    callbacks = KremenchukCallbacks(
        ask_description=ask_description,
        ask_final_confirmation=MagicMock(),
    )

    kremenchuk.handle_kremenchuk_selection(
        app_context,
        _call("kremenchuk_done", user_id=user_id),
        callbacks,
    )

    assert app_context.sessions.get_profile(user_id, "kremenchuk") == selected
    assert app_context.sessions.get_data(user_id, "awaiting_multiple_select") is None
    ask_description.assert_called_once_with(456, user_id, "en")


def test_kremenchuk_invalid_callback_answers_invalid_selection(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")

    kremenchuk.handle_kremenchuk_selection(
        app_context,
        _call("kremenchuk_999", user_id=user_id),
    )

    app_context.bot.answer_callback_query.assert_called_once_with(
        "callback-id",
        messages["en"]["invalid_selection"],
    )
