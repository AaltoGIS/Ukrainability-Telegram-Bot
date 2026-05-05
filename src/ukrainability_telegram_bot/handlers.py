"""Telegram handler registration."""

from __future__ import annotations

from typing import Any

from .app import AppContext
from .survey import text_router
from .survey.actions import SurveyActions
from .survey.questions import (
    accessibility as accessibility_question,
    changes_detail as changes_detail_question,
    confirmation as confirmation_question,
    consent as consent_question,
    demographics as demographics_question,
    description as description_question,
    duration as duration_question,
    enjoyment as enjoyment_question,
    frequency as frequency_question,
    kremenchuk as kremenchuk_question,
    language as language_question,
    noticed_changes as noticed_changes_question,
    purpose as purpose_question,
    regularity as regularity_question,
    restart as restart_question,
    visitor_type as visitor_type_question,
    welcome as welcome_question,
    wishlist as wishlist_question,
)
from .telegram_io import clear_callback_state


def register_handlers(ctx: AppContext) -> None:
    """Register Telegram entry points against the configured bot."""

    actions = SurveyActions(
        ctx,
        clear_callback_state=lambda user_id: clear_callback_state(ctx, user_id),
    )
    bot_instance = ctx.bot

    def handle_restart(call: Any) -> None:
        welcome_question.handle_restart(
            ctx,
            call,
            welcome_question.callbacks_from_context(ctx, actions),
        )

    def send_welcome(
        message: Any = None,
        chat_id: int | None = None,
        user_id: int | None = None,
        start_param: str | None = None,
    ) -> None:
        welcome_question.send_welcome(
            ctx,
            callbacks=welcome_question.callbacks_from_context(ctx, actions),
            message=message,
            chat_id=chat_id,
            user_id=user_id,
            start_param=start_param,
        )

    def handle_language_selection(call: Any) -> None:
        language_question.handle_language_selection(
            ctx,
            call,
            language_question.callbacks_from_context(ctx, actions),
        )

    def handle_consent(call: Any) -> None:
        consent_question.handle_consent(ctx, call)

    def handle_post_consent_continue(call: Any) -> None:
        consent_question.handle_post_consent_continue(
            ctx,
            call,
            consent_question.callbacks_from_context(ctx, actions),
        )

    def handle_purpose_selection(call: Any) -> None:
        purpose_question.handle_purpose_selection(
            ctx,
            call,
            purpose_question.callbacks_from_context(ctx, actions),
        )

    def handle_enjoyment_selection(call: Any) -> None:
        enjoyment_question.handle_enjoyment_selection(
            ctx,
            call,
            enjoyment_question.callbacks_from_context(ctx, actions),
        )

    def confirm_enjoyment(call: Any) -> None:
        enjoyment_question.confirm_enjoyment(
            ctx,
            call,
            enjoyment_question.callbacks_from_context(ctx, actions),
        )

    def handle_visitor_type_selection(call: Any) -> None:
        visitor_type_question.handle_visitor_type_selection(
            ctx,
            call,
            visitor_type_question.callbacks_from_context(ctx, actions),
        )

    def handle_duration_selection(call: Any) -> None:
        duration_question.handle_duration_selection(ctx, call)

    def confirm_duration(call: Any) -> None:
        duration_question.confirm_duration(
            ctx,
            call,
            duration_question.callbacks_from_context(ctx, actions),
        )

    def handle_accessibility_selection(call: Any) -> None:
        accessibility_question.handle_accessibility_selection(
            ctx,
            call,
            accessibility_question.callbacks_from_context(ctx, actions),
        )

    def handle_regularity_selection(call: Any) -> None:
        regularity_question.handle_regularity_selection(ctx, call)

    def confirm_regularity(call: Any) -> None:
        regularity_question.confirm_regularity(
            ctx,
            call,
            regularity_question.callbacks_from_context(ctx, actions),
        )

    def handle_frequency_change_selection(call: Any) -> None:
        frequency_question.handle_frequency_change_selection(
            ctx,
            call,
            frequency_question.callbacks_from_context(ctx, actions),
        )

    def handle_noticed_changes_selection(call: Any) -> None:
        noticed_changes_question.handle_noticed_changes_selection(ctx, call)

    def confirm_noticed_changes(call: Any) -> None:
        noticed_changes_question.confirm_noticed_changes(
            ctx,
            call,
            noticed_changes_question.callbacks_from_context(ctx, actions),
        )

    def handle_changes_detail_selection(call: Any) -> None:
        changes_detail_question.handle_changes_detail_selection(
            ctx,
            call,
            changes_detail_question.callbacks_from_context(ctx, actions),
        )

    def handle_wishlist_selection(call: Any) -> None:
        wishlist_question.handle_wishlist_selection(
            ctx,
            call,
            wishlist_question.callbacks_from_context(ctx, actions),
        )

    def handle_age_selection(call: Any) -> None:
        demographics_question.handle_age_selection(ctx, call)

    def confirm_age(call: Any) -> None:
        demographics_question.confirm_age(
            ctx,
            call,
            demographics_question.callbacks_from_context(ctx, actions),
        )

    def handle_gender_selection(call: Any) -> None:
        demographics_question.handle_gender_selection(ctx, call)

    def confirm_gender(call: Any) -> None:
        demographics_question.confirm_gender(
            ctx,
            call,
            demographics_question.callbacks_from_context(ctx, actions),
        )

    def handle_occupation_selection(call: Any) -> None:
        demographics_question.handle_occupation_selection(ctx, call)

    def confirm_occupation(call: Any) -> None:
        demographics_question.confirm_occupation(
            ctx,
            call,
            demographics_question.callbacks_from_context(ctx, actions),
        )

    def handle_income_selection(call: Any) -> None:
        demographics_question.handle_income_selection(ctx, call)

    def confirm_income(call: Any) -> None:
        demographics_question.confirm_income(
            ctx,
            call,
            demographics_question.callbacks_from_context(ctx, actions),
        )

    def handle_kremenchuk_selection(call: Any) -> None:
        kremenchuk_question.handle_kremenchuk_selection(
            ctx,
            call,
            kremenchuk_question.callbacks_from_context(ctx, actions),
        )

    def handle_description_skip(call: Any) -> None:
        description_question.handle_description_skip(
            ctx,
            call,
            description_question.callbacks_from_context(ctx, actions),
        )

    def handle_final_confirmation_choice(call: Any) -> None:
        confirmation_question.handle_final_confirmation_choice(
            ctx,
            call,
            confirmation_question.callbacks_from_context(ctx, actions),
        )

    def handle_modification_selection_callback(call: Any) -> None:
        confirmation_question.handle_modification_selection(
            ctx,
            call,
            confirmation_question.callbacks_from_context(ctx, actions),
        )

    def handle_continue_or_stop_selection(call: Any) -> None:
        restart_question.handle_continue_or_stop_selection(
            ctx,
            call,
            restart_question.callbacks_from_context(ctx, actions),
        )

    def handle_text_messages(message: Any) -> None:
        text_router.handle_text_messages(ctx, message, actions)

    bot_instance.callback_query_handler(func=lambda call: call.data == "restart")(handle_restart)
    bot_instance.message_handler(commands=["start"])(send_welcome)
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("language_"))(
        handle_language_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("consent_"))(
        handle_consent
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "post_consent_continue")(
        handle_post_consent_continue
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("purpose_"))(
        handle_purpose_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("enjoyment_"))(
        handle_enjoyment_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_enjoyment")(
        confirm_enjoyment
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("visitor_"))(
        handle_visitor_type_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("duration_"))(
        handle_duration_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_duration")(
        confirm_duration
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("accessibility_"))(
        handle_accessibility_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("regularity_"))(
        handle_regularity_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_regularity")(
        confirm_regularity
    )
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith("frequency_change_")
    )(handle_frequency_change_selection)
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("noticed_changes_"))(
        handle_noticed_changes_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_noticed_changes")(
        confirm_noticed_changes
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("changes_detail_"))(
        handle_changes_detail_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("wishlist_"))(
        handle_wishlist_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("age_"))(
        handle_age_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_age")(confirm_age)
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("gender_"))(
        handle_gender_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_gender")(
        confirm_gender
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("occupation_"))(
        handle_occupation_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_occupation")(
        confirm_occupation
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("income_"))(
        handle_income_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "confirm_income")(
        confirm_income
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("kremenchuk_"))(
        handle_kremenchuk_selection
    )
    bot_instance.callback_query_handler(func=lambda call: call.data == "description_skip")(
        handle_description_skip
    )
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("final_"))(
        handle_final_confirmation_choice
    )
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith("modify_") or call.data == "modification_done"
    )(handle_modification_selection_callback)
    bot_instance.callback_query_handler(func=lambda call: call.data.startswith("continue_"))(
        handle_continue_or_stop_selection
    )
    bot_instance.message_handler(func=lambda message: True, content_types=["text"])(
        handle_text_messages
    )
