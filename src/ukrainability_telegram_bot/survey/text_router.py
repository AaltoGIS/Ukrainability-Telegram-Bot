"""Fallback text-message router for active survey sessions."""

from __future__ import annotations

from typing import Any

from ..app import AppContext
from ..messages import messages
from ..telegram_io import safe_send_message
from .actions import SurveyActions

CUSTOM_INPUT_KEYS = {
    "purpose_visit": "custom_purposes",
    "changes_detail": "custom_changes",
    "visitor_type": "custom_visitor_types",
    "accessibility": "custom_accessibility",
    "wishlist": "custom_wishlist",
    "kremenchuk": "custom_kremenchuk",
}


def handle_text_messages(
    ctx: AppContext,
    message: Any,
    actions: SurveyActions | None = None,
) -> None:
    """Handle free-form text outside explicit next-step handlers."""

    actions = actions or SurveyActions(ctx)
    chat_id = message.chat.id
    user_id = message.from_user.id
    actions.update_activity_timestamp(user_id)

    if message.text.startswith("/start"):
        actions.send_welcome(message=message)
        return

    language = _ensure_language(ctx, chat_id, user_id)
    if language is None:
        return

    session = ctx.sessions.get_data(user_id)
    if "awaiting_multiple_select" in session:
        _handle_multiple_select_text(ctx, chat_id, user_id, language, message.text)
        return

    _handle_single_select_text(ctx, chat_id, user_id, language, actions)


def _ensure_language(ctx: AppContext, chat_id: int, user_id: int) -> str | None:
    session = ctx.sessions.get_data(user_id)
    if "language" in session:
        return session["language"]

    profile_language = ctx.sessions.get_profile(user_id, "language")
    if profile_language:
        ctx.sessions.set_data(user_id, "language", profile_language)
        return profile_language

    safe_send_message(
        ctx,
        chat_id,
        messages["en"]["please_use_start"],
    )
    return None


def _handle_multiple_select_text(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    text: str,
) -> None:
    session = ctx.sessions.get_data(user_id)
    mode = session["awaiting_multiple_select"]
    user_input = text.strip()
    custom_key = CUSTOM_INPUT_KEYS.get(mode)

    if custom_key is None:
        ctx.bot.send_message(chat_id, messages[language]["multiple_select_prompt"])
        return

    custom_values = ctx.sessions.get_data(user_id, custom_key, [])
    custom_values.append(user_input)
    ctx.sessions.set_data(user_id, custom_key, custom_values)
    ctx.bot.send_message(chat_id, messages[language]["multiple_select_input_noted"])


def _handle_single_select_text(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    actions: SurveyActions,
) -> None:
    current_question = ctx.sessions.get_data(user_id, "current_question")
    if current_question not in {
        "enjoyment",
        "duration",
        "regularity",
        "frequency_change",
        "noticed_changes",
        "age",
        "gender",
        "occupation",
        "income",
    }:
        ctx.bot.send_message(chat_id, messages[language]["unsolicited_text_help"])
        return

    ctx.bot.send_message(chat_id, messages[language]["single_select_prompt"])

    ask_again = {
        "enjoyment": actions.ask_enjoyment,
        "duration": actions.ask_duration,
        "regularity": actions.ask_regularity,
        "frequency_change": actions.ask_frequency_change,
        "noticed_changes": actions.ask_noticed_changes,
        "age": actions.ask_age,
        "gender": actions.ask_gender,
        "occupation": actions.ask_occupation,
        "income": actions.ask_income,
    }[current_question]
    ask_again(chat_id, user_id, language)
