"""Final confirmation and response-modification handlers."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    callback_suffix,
    escape_html,
    safe_answer_callback,
    safe_send_message,
)
from ..flow import (
    FIELD_ORDER,
    get_question_dependencies,
    requires_changes_detail,
    requires_follow_up,
    skips_changes_questions,
)
from .base import register


@dataclass(frozen=True)
class ConfirmationCallbacks:
    ask_enjoyment: Callable[[int, int, str], Any]
    ask_purpose_visit: Callable[[int, int, str], Any]
    ask_regularity: Callable[[int, int, str], Any]
    ask_accessibility: Callable[[int, int, str], Any]
    ask_noticed_changes: Callable[[int, int, str], Any]
    ask_changes_detail: Callable[[int, int, str], Any]
    ask_wishlist: Callable[[int, int, str], Any]
    ask_kremenchuk: Callable[[int, int, str], Any]
    ask_age: Callable[[int, int, str], Any]
    ask_gender: Callable[[int, int, str], Any]
    ask_occupation: Callable[[int, int, str], Any]
    ask_income: Callable[[int, int, str], Any]
    ask_description: Callable[[int, int, str], Any]
    ask_visitor_type: Callable[[int, int, str], Any]
    ask_duration: Callable[[int, int, str], Any]
    ask_continue_or_stop: Callable[[int, int, str], Any]
    save_data_and_restart: Callable[[int, int, str, bool], Any]
    get_anonymous_id: Callable[[int], str]


@register("final_confirmation")
class FinalConfirmationQuestion:
    name = "final_confirmation"
    callback_prefix = "final_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_final_confirmation(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_final_confirmation_choice(ctx, call)


@register("modification")
class ModificationQuestion:
    name = "modification"
    callback_prefix = "modify_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_which_responses_to_modify(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_modification_selection(ctx, call)


def ask_final_confirmation(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
) -> None:
    try:
        if (
            ctx.sessions.get_data(user_id, "kremenchuk") is None
            and ctx.sessions.get_profile(user_id, "kremenchuk") is not None
        ):
            ctx.sessions.set_data(
                user_id,
                "kremenchuk",
                ctx.sessions.get_profile(user_id, "kremenchuk"),
            )

        header_message = (
            "Here's a summary of your responses. Please review them carefully:"
            if language == "en"
            else "Ось підсумок ваших відповідей. Будь ласка, уважно перегляньте їх:"
        )
        safe_send_message(ctx, chat_id, header_message)
        time.sleep(0.5)

        responses_text = get_responses_text(ctx, user_id, language)
        safe_send_message(ctx, chat_id, responses_text, parse_mode="HTML")
        time.sleep(0.5)

        options = [
            messages[language]["modify_responses"],
            messages[language]["confirm_submission"],
        ]
        inline_kb = types.InlineKeyboardMarkup(row_width=2)
        inline_kb.add(
            *[
                types.InlineKeyboardButton(
                    text=option,
                    callback_data=f"final_{idx}",
                )
                for idx, option in enumerate(options)
            ]
        )

        confirmation_text = (
            "Is this information correct? You can modify any response or confirm submission."
            if language == "en"
            else "Чи правильна ця інформація? Ви можете змінити будь-яку відповідь або підтвердити подання."
        )
        safe_send_message(ctx, chat_id, confirmation_text, reply_markup=inline_kb)
    except Exception as exc:
        logging.exception(f"Error in ask_final_confirmation: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def get_responses_text(ctx: AppContext, user_id: int, language: str) -> str:
    try:
        responses = ctx.sessions.get_data(user_id)
        label_mapping = messages[language]["labels"]
        latitude_label = "Latitude" if language == "en" else "Широта"
        longitude_label = "Longitude" if language == "en" else "Довгота"
        skipped_text = "Skipped" if language == "en" else "Пропущено"
        voice_submitted_text = messages[language]["voice_message_submitted"]
        lines: list[str] = []

        for field in FIELD_ORDER:
            if field == "location" and "location" in responses:
                loc = responses["location"]
                loc_label = label_mapping.get(
                    "location", "Location" if language == "en" else "Локація"
                )
                if loc.get("venue_title"):
                    lines.append(
                        f"<b>{loc_label}:</b> "
                        f"{escape_html(loc['venue_title'])}, "
                        f"{escape_html(loc['venue_address'])}"
                    )
                else:
                    lat = loc.get("latitude", "")
                    lon = loc.get("longitude", "")
                    lines.append(
                        f"<b>{loc_label}:</b> {latitude_label} {lat}, {longitude_label} {lon}"
                    )
            elif field == "purpose_visit" and "purpose_visit" in responses:
                purposes = _join_with_custom(
                    responses.get("purpose_visit", []),
                    responses.get("custom_purposes", []),
                )
                lines.append(
                    f"<b>{label_mapping.get('purpose_visit', 'Purpose of visit')}:</b> "
                    f"{escape_html(purposes)}"
                )
            elif field == "visitor_type" and "visitor_type" in responses:
                visitor_type = _join_with_custom(
                    responses.get("visitor_type", []),
                    responses.get("custom_visitor_types", []),
                )
                lines.append(
                    f"<b>{label_mapping.get('visitor_type', 'Type of visitors')}:</b> "
                    f"{escape_html(visitor_type)}"
                )
            elif field == "accessibility" and "accessibility" in responses:
                accessibility = _join_with_custom(
                    responses.get("accessibility", []),
                    responses.get("custom_accessibility", []),
                )
                lines.append(
                    f"<b>{label_mapping.get('accessibility', 'Accessibility')}:</b> "
                    f"{escape_html(accessibility)}"
                )
            elif field == "changes_detail" and "changes_detail" in responses:
                changes = _join_with_custom(
                    responses.get("changes_detail", []),
                    responses.get("custom_changes", []),
                )
                lines.append(
                    f"<b>{label_mapping.get('changes_detail', 'Changes detail')}:</b> "
                    f"{escape_html(changes)}"
                )
            elif field == "wishlist" and "wishlist" in responses:
                wishlist = _join_with_custom(
                    responses.get("wishlist", []),
                    responses.get("custom_wishlist", []),
                )
                lines.append(
                    f"<b>{label_mapping.get('wishlist', 'Improvements wished')}:</b> "
                    f"{escape_html(wishlist)}"
                )
            elif field == "kremenchuk" and (
                "kremenchuk" in responses or "custom_kremenchuk" in responses
            ):
                kremenchuk_text = _join_with_custom(
                    responses.get("kremenchuk", ""),
                    responses.get("custom_kremenchuk", []),
                )
                if kremenchuk_text:
                    lines.append(
                        f"<b>{label_mapping.get('kremenchuk', 'Time living in Kremenchuk')}:</b> "
                        f"{escape_html(kremenchuk_text)}"
                    )
            elif field == "description":
                label = label_mapping.get("description", "Description")
                description_text = responses.get("description", "")
                voice_submitted = responses.get("voice_submitted", "")
                if voice_submitted:
                    lines.append(f"<b>{label}:</b> {voice_submitted_text}")
                elif description_text.strip():
                    lines.append(f"<b>{label}:</b> {escape_html(description_text)}")
                else:
                    lines.append(f"<b>{label}:</b> {skipped_text}")
            elif field in responses:
                value = responses[field]
                label = label_mapping.get(field, field.capitalize())
                if isinstance(value, list):
                    value = "; ".join(value)
                if value and str(value).strip():
                    lines.append(f"<b>{label}:</b> {escape_html(str(value))}")
                else:
                    lines.append(f"<b>{label}:</b> ")

        return "\n".join(lines)
    except Exception as exc:
        logging.exception(f"Error in get_responses_text: {exc}")
        return "Error retrieving responses."


def handle_final_confirmation_choice(
    ctx: AppContext,
    call: Any,
    callbacks: ConfirmationCallbacks | None = None,
) -> None:
    language = "en"
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        ctx.sessions.update_activity(user_id)
        language = _language_for_user(ctx, chat_id, user_id)
        if language is None:
            return

        choice = callback_suffix(call.data, "final")
        if choice == "0":
            if callbacks is not None:
                ctx.flow_logger.info(
                    "User %s: Starting modification process",
                    callbacks.get_anonymous_id(user_id),
                )
            safe_answer_callback(ctx, call, messages[language]["modify_responses"])
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            if callbacks is not None:
                ask_which_responses_to_modify(ctx, chat_id, user_id, language, callbacks)
        elif choice == "1":
            safe_answer_callback(ctx, call, messages[language]["confirm_submission"])
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            if callbacks is not None:
                callbacks.save_data_and_restart(chat_id, user_id, language, False)
                callbacks.ask_continue_or_stop(chat_id, user_id, language)
        else:
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
    except Exception as exc:
        logging.exception(f"Error in handle_final_confirmation_choice: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def ask_which_responses_to_modify(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    callbacks: ConfirmationCallbacks | None = None,
) -> None:
    try:
        label_mapping = messages[language]["labels"]
        combined_data = {
            **ctx.sessions.get_profile(user_id),
            **ctx.sessions.get_data(user_id),
        }
        field_mapping: dict[str, str] = {}
        for field in FIELD_ORDER:
            if field == "location":
                continue
            if field == "description":
                field_mapping[field] = label_mapping.get(field, "Description")
            elif field in combined_data or field in label_mapping:
                field_mapping[field] = label_mapping.get(field, field.capitalize())

        ctx.sessions.set_data(user_id, "field_mapping", field_mapping)

        if callbacks is not None:
            anon_id = callbacks.get_anonymous_id(user_id)
            ctx.flow_logger.info(
                "User %s: Offered these fields for modification: %s",
                anon_id,
                list(field_mapping.keys()),
            )
            dependency_fields = ["regularity", "noticed_changes", "changes_detail"]
            offered_dependencies = [
                field for field in dependency_fields if field in field_mapping
            ]
            if offered_dependencies:
                dependency_values = {
                    field: ctx.sessions.get_data(user_id, field, "not set")
                    for field in offered_dependencies
                }
                ctx.flow_logger.info(
                    "User %s: Current dependency chain values: %s",
                    anon_id,
                    dependency_values,
                )

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        inline_kb.add(
            *[
                types.InlineKeyboardButton(
                    text=label,
                    callback_data=f"modify_{field}",
                )
                for field, label in field_mapping.items()
            ]
        )
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="modification_done",
            )
        )
        safe_send_message(
            ctx,
            chat_id,
            messages[language]["select_questions_to_modify"],
            reply_markup=inline_kb,
        )
    except Exception as exc:
        logging.exception(f"Error in ask_which_responses_to_modify: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_modification_selection(
    ctx: AppContext,
    call: Any,
    callbacks: ConfirmationCallbacks | None = None,
) -> None:
    language = "en"
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        ctx.sessions.update_activity(user_id)
        language = ctx.sessions.get_data(user_id, "language", "en")

        if call.data == "modification_done":
            if callbacks is not None:
                ctx.flow_logger.info(
                    "User %s: Completed modifications, returning to final confirmation",
                    callbacks.get_anonymous_id(user_id),
                )
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            ask_final_confirmation(ctx, chat_id, user_id, language)
            return

        field = callback_suffix(call.data, "modify")
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        ctx.sessions.set_data(user_id, "modifying", True)
        ctx.sessions.set_data(user_id, "modifying_field", field)

        if callbacks is not None:
            anon_id = callbacks.get_anonymous_id(user_id)
            ctx.flow_logger.info("User %s: Modifying field: %s", anon_id, field)
            dependencies = get_question_dependencies()
            if field in dependencies:
                dependent_fields = dependencies[field]
                current_values = {
                    dep: ctx.sessions.get_data(user_id, dep, "not set")
                    for dep in [field] + dependent_fields
                    if dep in ctx.sessions.get_data(user_id)
                }
                ctx.flow_logger.info(
                    "User %s: Field %s has dependencies: %s. Current values: %s",
                    anon_id,
                    field,
                    dependent_fields,
                    current_values,
                )
            _route_modification(ctx, chat_id, user_id, language, field, callbacks)
    except Exception as exc:
        logging.exception(f"Error in handle_modification_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def clear_dependent_fields(
    ctx: AppContext,
    user_id: int,
    field: str,
    old_value: Any,
    new_value: Any,
    get_anonymous_id: Callable[[int], str],
) -> list[str]:
    dependencies = get_question_dependencies()
    cleared_fields: list[str] = []
    if field not in dependencies:
        return cleared_fields

    anon_id = get_anonymous_id(user_id)
    current_values = {
        dep: ctx.sessions.get_data(user_id, dep, "not set")
        for dep in dependencies[field]
        if dep in ctx.sessions.get_data(user_id)
    }

    if field == "regularity" and not requires_follow_up(str(new_value)):
        ctx.flow_logger.info(
            "User %s: Clearing dependent fields because regularity changed to '%s'",
            anon_id,
            new_value,
        )
        for dep_field in dependencies[field]:
            if dep_field in ctx.sessions.get_data(user_id):
                ctx.sessions.remove_data(user_id, dep_field)
                cleared_fields.append(dep_field)
                if dep_field == "changes_detail" and "custom_changes" in ctx.sessions.get_data(user_id):
                    ctx.sessions.remove_data(user_id, "custom_changes")
                    cleared_fields.append("custom_changes")
    elif field == "noticed_changes":
        old_requires_detail = requires_changes_detail(str(old_value))
        new_requires_detail = requires_changes_detail(str(new_value))
        if old_requires_detail and not new_requires_detail:
            if "changes_detail" in ctx.sessions.get_data(user_id):
                ctx.sessions.remove_data(user_id, "changes_detail")
                cleared_fields.append("changes_detail")
                if "custom_changes" in ctx.sessions.get_data(user_id):
                    ctx.sessions.remove_data(user_id, "custom_changes")
                    cleared_fields.append("custom_changes")

    if cleared_fields:
        ctx.flow_logger.info(
            "User %s: Fields cleared due to modification: %s changed from '%s' to '%s'",
            anon_id,
            field,
            old_value,
            new_value,
        )
        ctx.flow_logger.info(
            "User %s: Cleared fields: %s with previous values: %s",
            anon_id,
            cleared_fields,
            current_values,
        )
    return cleared_fields


def _join_with_custom(value: Any, custom: list[str]) -> str:
    base = value if isinstance(value, list) else ([value] if value else [])
    return "; ".join([*base, *custom])


def _language_for_user(ctx: AppContext, chat_id: int, user_id: int) -> str | None:
    language = ctx.sessions.get_data(user_id, "language")
    if language:
        return language
    profile_language = ctx.sessions.get_profile(user_id, "language")
    if profile_language:
        ctx.sessions.set_data(user_id, "language", profile_language)
        return profile_language
    safe_send_message(ctx, chat_id, messages["en"]["please_use_start"])
    return None


def _route_modification(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    field: str,
    callbacks: ConfirmationCallbacks,
) -> None:
    routes = {
        "enjoyment": callbacks.ask_enjoyment,
        "purpose_visit": callbacks.ask_purpose_visit,
        "regularity": callbacks.ask_regularity,
        "accessibility": callbacks.ask_accessibility,
        "noticed_changes": callbacks.ask_noticed_changes,
        "changes_detail": callbacks.ask_changes_detail,
        "wishlist": callbacks.ask_wishlist,
        "kremenchuk": callbacks.ask_kremenchuk,
        "age": callbacks.ask_age,
        "gender": callbacks.ask_gender,
        "occupation": callbacks.ask_occupation,
        "income": callbacks.ask_income,
        "description": callbacks.ask_description,
        "visitor_type": callbacks.ask_visitor_type,
        "duration_visit": callbacks.ask_duration,
    }
    route = routes.get(field)
    if route is None:
        safe_send_message(ctx, chat_id, messages[language]["invalid_selection"])
        ctx.flow_logger.warning(
            "User %s: Attempted to modify invalid field: %s",
            callbacks.get_anonymous_id(user_id),
            field,
        )
        return
    route(chat_id, user_id, language)
