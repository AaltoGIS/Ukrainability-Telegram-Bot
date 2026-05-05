"""Noticed-changes question handlers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import telebot
from telebot import types

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    callback_index,
    escape_html,
    hide_keyboard,
    safe_answer_callback,
    safe_send_message,
)
from .base import register, resolve_actions


DETAIL_REQUIRING_INDICES = frozenset({0, 1})


@dataclass(frozen=True)
class NoticedChangesCallbacks:
    ask_changes_detail: Callable[[int, int, str], Any]
    ask_wishlist: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]
    clear_dependent_fields: Callable[[int, str, Any, Any], list[str]]
    get_anonymous_id: Callable[[int], str]


def callbacks_from_context(ctx: AppContext, actions: Any | None = None) -> NoticedChangesCallbacks:
    actions = resolve_actions(ctx, actions)
    return NoticedChangesCallbacks(
        ask_changes_detail=actions.ask_changes_detail,
        ask_wishlist=actions.ask_wishlist,
        ask_final_confirmation=actions.ask_final_confirmation,
        clear_dependent_fields=actions.clear_dependent_fields,
        get_anonymous_id=actions.get_anonymous_id,
    )


@register("noticed_changes")
class NoticedChangesQuestion:
    name = "noticed_changes"
    callback_prefix = "noticed_changes_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_noticed_changes(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_noticed_changes_selection(ctx, call)


def ask_noticed_changes(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
) -> None:
    try:
        ctx.sessions.set_data(user_id, "noticed_changes", "")
        ctx.sessions.set_data(user_id, "current_question", "noticed_changes")

        options = messages[language]["options"]["noticed_changes"]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"noticed_changes_{idx}",
            )
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)
        safe_send_message(
            ctx,
            chat_id,
            messages[language]["changes_question"],
            reply_markup=inline_kb,
        )
    except Exception as exc:
        logging.exception(f"Error in ask_noticed_changes: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_noticed_changes_selection(ctx: AppContext, call: Any) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        options = messages[language]["options"]["noticed_changes"]

        try:
            idx = callback_index(call.data, "noticed_changes", options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        selected_change = options[idx]
        ctx.sessions.set_data(user_id, "temp_noticed_changes", selected_change)
        ctx.sessions.set_data(user_id, "temp_noticed_changes_idx", idx)

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for option_idx, option in enumerate(options):
            text = f"✅ {option}" if option_idx == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"noticed_changes_{option_idx}",
                )
            )
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data="confirm_noticed_changes",
            )
        )

        try:
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb,
            )
        except telebot.apihelper.ApiTelegramException as exc:
            if "message is not modified" not in str(exc):
                logging.exception(f"Error in handle_noticed_changes_selection: {exc}")

        safe_answer_callback(
            ctx,
            call,
            f"{messages[language]['selected']} {selected_change}",
        )
    except Exception as exc:
        logging.exception(f"Error in handle_noticed_changes_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def confirm_noticed_changes(
    ctx: AppContext,
    call: Any,
    callbacks: NoticedChangesCallbacks,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        anon_id = callbacks.get_anonymous_id(user_id)
        selected_change = ctx.sessions.get_data(user_id, "temp_noticed_changes")

        if selected_change:
            selected_idx = ctx.sessions.get_data(user_id, "temp_noticed_changes_idx")
            if selected_idx is None:
                try:
                    selected_idx = messages[language]["options"]["noticed_changes"].index(
                        selected_change
                    )
                except ValueError:
                    selected_idx = -1
            previous_change = ctx.sessions.get_data(user_id, "noticed_changes", "")

            if (
                ctx.sessions.get_data(user_id, "modifying")
                and previous_change != selected_change
            ):
                ctx.flow_logger.info(
                    "User %s: Modified noticed changes from '%s' to '%s'",
                    anon_id,
                    previous_change,
                    selected_change,
                )

            ctx.sessions.set_data(user_id, "noticed_changes", selected_change)
            ctx.sessions.set_profile(user_id, "noticed_changes", selected_change)
            ctx.sessions.remove_data(user_id, "temp_noticed_changes")
            ctx.sessions.remove_data(user_id, "temp_noticed_changes_idx")
            ctx.sessions.remove_data(user_id, "current_question")

            if previous_change != selected_change:
                cleared_fields = callbacks.clear_dependent_fields(
                    user_id,
                    "noticed_changes",
                    previous_change,
                    selected_change,
                )
                if cleared_fields:
                    ctx.flow_logger.info(
                        "User %s: Cleared fields due to noticed_changes change: %s",
                        anon_id,
                        cleared_fields,
                    )

            safe_answer_callback(ctx, call, messages[language]["response_confirmed"])
            ctx.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None,
            )
            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_change)}</i>",
                parse_mode="HTML",
            )
            hide_keyboard(ctx, chat_id)

            if selected_idx in DETAIL_REQUIRING_INDICES:
                ctx.flow_logger.info(
                    "User %s: Selected positive/negative changes, asking for details",
                    anon_id,
                )
                callbacks.ask_changes_detail(chat_id, user_id, language)
            elif ctx.sessions.get_data(user_id, "modifying"):
                ctx.sessions.remove_data(user_id, "modifying")
                ctx.sessions.remove_data(user_id, "modifying_field")
                ctx.flow_logger.info(
                    "User %s: No notable changes while modifying, returning to final confirmation",
                    anon_id,
                )
                callbacks.ask_final_confirmation(chat_id, user_id, language)
            else:
                ctx.flow_logger.info("User %s: No notable changes, skipping to wishlist", anon_id)
                callbacks.ask_wishlist(chat_id, user_id, language)
        else:
            safe_answer_callback(ctx, call, messages[language]["select_option_first"])
    except Exception as exc:
        logging.exception(f"Error in confirm_noticed_changes: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])
