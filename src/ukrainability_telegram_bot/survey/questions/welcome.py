"""Welcome and restart survey handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import escape_html, safe_answer_callback, safe_send_message
from . import consent as consent_question
from .base import register, resolve_actions


@dataclass(frozen=True)
class WelcomeCallbacks:
    update_activity_timestamp: Callable[[int], Any]
    get_user_hash: Callable[[int], str]
    get_user_nickname: Callable[[str], str | None]
    generate_unique_nickname: Callable[[], str]
    save_user_nickname: Callable[[str, str], Any]
    send_welcome: Callable[..., Any]


def callbacks_from_context(ctx: AppContext, actions: Any | None = None) -> WelcomeCallbacks:
    actions = resolve_actions(ctx, actions)
    return WelcomeCallbacks(
        update_activity_timestamp=actions.update_activity_timestamp,
        get_user_hash=actions.get_user_hash,
        get_user_nickname=actions.get_user_nickname,
        generate_unique_nickname=actions.generate_unique_nickname,
        save_user_nickname=actions.save_user_nickname,
        send_welcome=actions.send_welcome,
    )


@register("welcome")
class WelcomeQuestion:
    """Discovery entry for welcome flow until registration is centralized.

    Welcome is a special case during Phase 5 because it has multiple entry
    points: the `/start` message handler, the `restart` callback, and
    programmatic restarts after saving. `_legacy.py` routes those entry points
    explicitly while this class keeps the question visible in the registry.
    """

    name = "welcome"
    callback_prefix = "restart"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        _send_language_prompt(ctx, chat_id)

    def handle(self, ctx: AppContext, call: Any) -> None:
        raise NotImplementedError("welcome handlers need explicit callbacks")


def handle_restart(ctx: AppContext, call: Any, callbacks: WelcomeCallbacks) -> None:
    chat_id = call.message.chat.id
    try:
        user_id = call.from_user.id
        safe_answer_callback(ctx, call, messages["en"]["restart_acknowledgement"])
        callbacks.send_welcome(chat_id=chat_id, user_id=user_id, start_param="restart")
    except Exception as exc:
        logging.exception(f"Error in handle_restart: {exc}")
        safe_send_message(ctx, chat_id, messages["en"]["restart_error"])


def send_welcome(
    ctx: AppContext,
    *,
    callbacks: WelcomeCallbacks,
    message: Any = None,
    chat_id: int | None = None,
    user_id: int | None = None,
    start_param: str | None = None,
) -> None:
    try:
        if message:
            chat_id = message.chat.id
            user_id = message.from_user.id
            callbacks.update_activity_timestamp(user_id)
            if message.text.startswith("/start "):
                start_param = message.text.split(" ", 1)[1]
        elif chat_id and user_id:
            pass
        else:
            return

        user_hash = callbacks.get_user_hash(user_id)
        nickname = callbacks.get_user_nickname(user_hash)
        if not nickname:
            nickname = callbacks.generate_unique_nickname()
            callbacks.save_user_nickname(user_hash, nickname)

        ctx.sessions.set_data(user_id, "nickname", nickname)

        if start_param == "restart":
            for key in (
                "location",
                "enjoyment",
                "purpose_visit",
                "regularity",
                "frequency_change",
                "noticed_changes",
                "changes_detail",
                "wishlist",
                "kremenchuk",
                "accessibility",
                "description",
                "voice_submitted",
            ):
                ctx.sessions.remove_data(user_id, key)

        language = ctx.sessions.get_profile(user_id, "language")
        if language:
            ctx.sessions.set_data(user_id, "language", language)
            consent = ctx.sessions.get_profile(user_id, "consent")
            if consent is False:
                ctx.sessions.set_profile(user_id, "consent", True)
                _send_consent_continue(ctx, chat_id, language, nickname)
                return
            if consent is True:
                _send_consent_continue(ctx, chat_id, language, nickname)
                return

            consent_question.ConsentQuestion().ask(ctx, chat_id, user_id, language)
            return

        _send_language_prompt(ctx, chat_id)
    except Exception as exc:
        logging.exception(f"Error in send_welcome: {exc}")
        if chat_id is not None:
            safe_send_message(ctx, chat_id, messages["en"]["error_occurred"])


def _send_consent_continue(
    ctx: AppContext,
    chat_id: int,
    language: str,
    nickname: str,
) -> None:
    consent_message = messages[language]["consent_given"].format(
        nickname=f"<b>{escape_html(nickname)}</b>"
    )
    inline_kb = types.InlineKeyboardMarkup()
    continue_button = types.InlineKeyboardButton(
        messages[language]["continue_button"],
        callback_data="post_consent_continue",
    )
    inline_kb.add(continue_button)
    safe_send_message(
        ctx,
        chat_id,
        consent_message,
        parse_mode="HTML",
        reply_markup=inline_kb,
    )


def _send_language_prompt(ctx: AppContext, chat_id: int) -> None:
    inline_kb = types.InlineKeyboardMarkup(row_width=2)
    english_label, ukrainian_label = messages["en"]["language_buttons"]
    english_button = types.InlineKeyboardButton(english_label, callback_data="language_en")
    ukrainian_button = types.InlineKeyboardButton(ukrainian_label, callback_data="language_uk")
    inline_kb.add(english_button, ukrainian_button)
    safe_send_message(
        ctx,
        chat_id,
        messages["en"]["welcome"] + "\n" + messages["uk"]["welcome"],
        reply_markup=inline_kb,
    )
