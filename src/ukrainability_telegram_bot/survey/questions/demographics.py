"""Demographic question handlers."""

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
from .base import register


@dataclass(frozen=True)
class DemographicsCallbacks:
    ask_gender: Callable[[int, int, str], Any]
    ask_occupation: Callable[[int, int, str], Any]
    ask_income: Callable[[int, int, str], Any]
    ask_kremenchuk: Callable[[int, int, str], Any]
    ask_description: Callable[[int, int, str], Any]
    ask_final_confirmation: Callable[[int, int, str], Any]


def callbacks_from_bridge(bridge: Any) -> DemographicsCallbacks:
    return DemographicsCallbacks(
        ask_gender=bridge.ask_gender,
        ask_occupation=bridge.ask_occupation,
        ask_income=bridge.ask_income,
        ask_kremenchuk=bridge.ask_kremenchuk,
        ask_description=bridge.ask_description,
        ask_final_confirmation=bridge.ask_final_confirmation,
    )


@register("age")
class AgeQuestion:
    name = "age"
    callback_prefix = "age_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_age(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_age_selection(ctx, call)


@register("gender")
class GenderQuestion:
    name = "gender"
    callback_prefix = "gender_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_gender(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_gender_selection(ctx, call)


@register("occupation")
class OccupationQuestion:
    name = "occupation"
    callback_prefix = "occupation_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_occupation(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_occupation_selection(ctx, call)


@register("income")
class IncomeQuestion:
    name = "income"
    callback_prefix = "income_"

    def ask(self, ctx: AppContext, chat_id: int, user_id: int, language: str) -> None:
        ask_income(ctx, chat_id, user_id, language)

    def handle(self, ctx: AppContext, call: Any) -> None:
        handle_income_selection(ctx, call)


def ask_age(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    callbacks: DemographicsCallbacks | None = None,
) -> None:
    _ask_profile_backed_question(
        ctx,
        chat_id,
        user_id,
        language,
        field="age",
        question_key="age_question",
        callbacks_next=callbacks.ask_gender if callbacks else None,
    )


def ask_gender(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    callbacks: DemographicsCallbacks | None = None,
) -> None:
    _ask_profile_backed_question(
        ctx,
        chat_id,
        user_id,
        language,
        field="gender",
        question_key="gender_question",
        callbacks_next=callbacks.ask_occupation if callbacks else None,
    )


def ask_occupation(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    callbacks: DemographicsCallbacks | None = None,
) -> None:
    _ask_profile_backed_question(
        ctx,
        chat_id,
        user_id,
        language,
        field="occupation",
        question_key="occupation_question",
        callbacks_next=callbacks.ask_income if callbacks else None,
    )


def ask_income(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    callbacks: DemographicsCallbacks | None = None,
) -> None:
    try:
        if not ctx.sessions.get_data(user_id, "modifying"):
            stored_income = ctx.sessions.get_profile(user_id, "income")
            if stored_income is not None:
                ctx.sessions.set_data(user_id, "income", stored_income)
                if callbacks is None:
                    return
                stored_kremenchuk = ctx.sessions.get_profile(user_id, "kremenchuk")
                if stored_kremenchuk is not None:
                    ctx.sessions.set_data(user_id, "kremenchuk", stored_kremenchuk)
                    callbacks.ask_description(chat_id, user_id, language)
                else:
                    callbacks.ask_kremenchuk(chat_id, user_id, language)
                return

        _send_single_select_question(ctx, chat_id, user_id, language, "income")
    except Exception as exc:
        logging.exception(f"Error in ask_income: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def handle_age_selection(ctx: AppContext, call: Any) -> None:
    _handle_single_selection(ctx, call, "age")


def handle_gender_selection(ctx: AppContext, call: Any) -> None:
    _handle_single_selection(ctx, call, "gender")


def handle_occupation_selection(ctx: AppContext, call: Any) -> None:
    _handle_single_selection(ctx, call, "occupation")


def handle_income_selection(ctx: AppContext, call: Any) -> None:
    _handle_single_selection(ctx, call, "income")


def confirm_age(
    ctx: AppContext,
    call: Any,
    callbacks: DemographicsCallbacks,
) -> None:
    _confirm_single_selection(
        ctx,
        call,
        field="age",
        callbacks=callbacks,
        next_callback=callbacks.ask_gender,
        honor_modifying=False,
    )


def confirm_gender(
    ctx: AppContext,
    call: Any,
    callbacks: DemographicsCallbacks,
) -> None:
    _confirm_single_selection(
        ctx,
        call,
        field="gender",
        callbacks=callbacks,
        next_callback=callbacks.ask_occupation,
    )


def confirm_occupation(
    ctx: AppContext,
    call: Any,
    callbacks: DemographicsCallbacks,
) -> None:
    _confirm_single_selection(
        ctx,
        call,
        field="occupation",
        callbacks=callbacks,
        next_callback=callbacks.ask_income,
    )


def confirm_income(
    ctx: AppContext,
    call: Any,
    callbacks: DemographicsCallbacks,
) -> None:
    def next_after_income(chat_id: int, user_id: int, language: str) -> None:
        stored_kremenchuk = ctx.sessions.get_profile(user_id, "kremenchuk")
        if stored_kremenchuk is not None:
            ctx.sessions.set_data(user_id, "kremenchuk", stored_kremenchuk)
            callbacks.ask_description(chat_id, user_id, language)
        else:
            callbacks.ask_kremenchuk(chat_id, user_id, language)

    _confirm_single_selection(
        ctx,
        call,
        field="income",
        callbacks=callbacks,
        next_callback=next_after_income,
    )


def _ask_profile_backed_question(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    *,
    field: str,
    question_key: str,
    callbacks_next: Callable[[int, int, str], Any] | None,
) -> None:
    try:
        if callbacks_next is not None and not ctx.sessions.get_data(user_id, "modifying"):
            stored_value = ctx.sessions.get_profile(user_id, field)
            if stored_value is not None:
                ctx.sessions.set_data(user_id, field, stored_value)
                callbacks_next(chat_id, user_id, language)
                return

        ctx.sessions.set_data(user_id, "current_question", field)
        options = messages[language]["options"][field]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        inline_kb.add(
            *[
                types.InlineKeyboardButton(
                    text=option,
                    callback_data=f"{field}_{idx}",
                )
                for idx, option in enumerate(options)
            ]
        )
        safe_send_message(
            ctx,
            chat_id,
            messages[language][question_key],
            reply_markup=inline_kb,
        )
    except Exception as exc:
        logging.exception(f"Error in ask_{field}: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def _send_single_select_question(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    field: str,
) -> None:
    ctx.sessions.set_data(user_id, "current_question", field)
    options = messages[language]["options"][field]
    inline_kb = types.InlineKeyboardMarkup(row_width=1)
    for idx, option in enumerate(options):
        inline_kb.add(
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"{field}_{idx}",
            )
        )
    safe_send_message(
        ctx,
        chat_id,
        messages[language][f"{field}_question"],
        reply_markup=inline_kb,
    )


def _language_for_call(ctx: AppContext, call: Any) -> str | None:
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    language = ctx.sessions.get_data(user_id, "language")
    if language:
        return language

    profile_language = ctx.sessions.get_profile(user_id, "language")
    if profile_language:
        ctx.sessions.set_data(user_id, "language", profile_language)
        return profile_language

    safe_answer_callback(ctx, call, messages["en"]["start_again"])
    safe_send_message(
        ctx,
        chat_id,
        messages["en"]["session_expired"],
    )
    return None


def _handle_single_selection(ctx: AppContext, call: Any, field: str) -> None:
    language = "en"
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _language_for_call(ctx, call)
        if language is None:
            return

        options = messages[language]["options"][field]
        try:
            idx = callback_index(call.data, field, options)
        except (ValueError, IndexError):
            safe_answer_callback(ctx, call, messages[language]["invalid_selection"])
            return

        selected_value = options[idx]
        ctx.sessions.set_data(user_id, f"temp_{field}", selected_value)

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for option_idx, option in enumerate(options):
            text = f"✅ {option}" if option_idx == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"{field}_{option_idx}",
                )
            )
        inline_kb.add(
            types.InlineKeyboardButton(
                text=messages[language]["done_button"],
                callback_data=f"confirm_{field}",
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
                logging.exception(f"Error in handle_{field}_selection: {exc}")

        safe_answer_callback(
            ctx,
            call,
            f"{messages[language]['selected']} {selected_value}",
        )
    except Exception as exc:
        logging.exception(f"Error in handle_{field}_selection: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])


def _confirm_single_selection(
    ctx: AppContext,
    call: Any,
    *,
    field: str,
    callbacks: DemographicsCallbacks,
    next_callback: Callable[[int, int, str], Any],
    honor_modifying: bool = True,
) -> None:
    language = "en"
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _language_for_call(ctx, call)
        if language is None:
            return

        selected_value = ctx.sessions.get_data(user_id, f"temp_{field}")
        if not selected_value:
            safe_answer_callback(ctx, call, messages[language]["select_option_first"])
            return

        ctx.sessions.set_data(user_id, field, selected_value)
        ctx.sessions.set_profile(user_id, field, selected_value)
        ctx.sessions.remove_data(user_id, f"temp_{field}")
        ctx.sessions.remove_data(user_id, "current_question")

        safe_answer_callback(ctx, call, messages[language]["response_confirmed"])
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        safe_send_message(
            ctx,
            chat_id,
            f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_value)}</i>",
            parse_mode="HTML",
        )
        hide_keyboard(ctx, chat_id)

        if honor_modifying and ctx.sessions.get_data(user_id, "modifying"):
            field_modified = ctx.sessions.get_data(user_id, "modifying_field")
            ctx.sessions.remove_data(user_id, "modifying")
            ctx.sessions.remove_data(user_id, "modifying_field")
            if field_modified != "description":
                callbacks.ask_final_confirmation(chat_id, user_id, language)
            else:
                callbacks.ask_description(chat_id, user_id, language)
        else:
            next_callback(chat_id, user_id, language)
    except Exception as exc:
        logging.exception(f"Error in confirm_{field}: {exc}")
        safe_send_message(ctx, chat_id, messages[language]["error_occurred"])
