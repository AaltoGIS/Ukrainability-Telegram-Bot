"""Description text/voice question handlers."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from telebot import types
from telebot.apihelper import ApiTelegramException

from ...app import AppContext
from ...messages import messages
from ...telegram_io import (
    escape_html,
    get_message_id,
    safe_send_message,
    send_next_step_prompt,
    telegram_retry_after,
)
from ...voice import new_voice_filename, safe_nickname_directory
from .base import DescriptionCallbacks


def callbacks_from_bridge(bridge: Any) -> DescriptionCallbacks:
    return DescriptionCallbacks(
        ask_final_confirmation=bridge.ask_final_confirmation,
        description_handler=bridge.handle_description,
    )


def ask_description(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    language: str,
    callbacks: DescriptionCallbacks,
) -> None:
    try:
        if ctx.sessions.get_data(user_id, "kremenchuk") is None:
            profile_kremenchuk = ctx.sessions.get_profile(user_id, "kremenchuk")
            if profile_kremenchuk is not None:
                ctx.sessions.set_data(user_id, "kremenchuk", profile_kremenchuk)

        if ctx.sessions.get_data(user_id, "description_done") and not (
            ctx.sessions.get_data(user_id, "modifying")
            and ctx.sessions.get_data(user_id, "modifying_field") == "description"
        ):
            callbacks.ask_final_confirmation(chat_id, user_id, language)
            return

        if ctx.sessions.get_data(user_id, "modifying"):
            field_modified = ctx.sessions.get_data(user_id, "modifying_field")
            if field_modified != "description":
                callbacks.ask_final_confirmation(chat_id, user_id, language)
                return

        inline_kb = types.InlineKeyboardMarkup()
        skip_button = types.InlineKeyboardButton(
            text=messages[language]["skip_button"],
            callback_data="description_skip",
        )
        inline_kb.add(skip_button)

        enhanced_instructions = (
            f"{messages[language]['add_description']}\n\n"
            f"({messages[language]['voice_instruction']})"
        )

        send_next_step_prompt(
            ctx,
            chat_id,
            enhanced_instructions,
            callbacks.description_handler,
            reply_markup=inline_kb,
        )
    except Exception as exc:
        logging.exception(f"Error in ask_description: {exc}")
        safe_send_message(
            ctx,
            chat_id,
            messages[language].get(
                "error_occurred",
                messages["en"]["error_occurred"],
            ),
        )


def handle_description_skip(
    ctx: AppContext,
    call: Any,
    callbacks: DescriptionCallbacks,
) -> None:
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = ctx.sessions.get_data(user_id, "language", "en")
        ctx.bot.clear_step_handler_by_chat_id(chat_id)
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None,
        )
        ctx.sessions.set_data(user_id, "description_done", True)
        safe_send_message(ctx, chat_id, messages[language]["description_skipped"])
        callbacks.ask_final_confirmation(chat_id, user_id, language)
    except Exception as exc:
        logging.exception(f"Error in handle_description_skip: {exc}")
        safe_send_message(ctx, chat_id, messages["en"]["error_occurred"])


def handle_description(
    ctx: AppContext,
    message: Any,
    callbacks: DescriptionCallbacks,
) -> None:
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        language = ctx.sessions.get_data(user_id, "language")
        if not language:
            profile_language = ctx.sessions.get_profile(user_id, "language")
            if profile_language:
                language = profile_language
                ctx.sessions.set_data(user_id, "language", language)
            else:
                safe_send_message(
                    ctx,
                    chat_id,
                    messages["en"]["please_use_start"],
                )
                return

        description = ""
        voice_submitted = ""

        try:
            message_id = get_message_id(ctx, user_id, "description_request")
            if message_id:
                ctx.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=None,
                )
        except Exception:
            pass

        if message.content_type == "text":
            description = message.text.strip()
            safe_send_message(
                ctx,
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(description)}</i>",
                parse_mode="HTML",
            )
        elif message.content_type == "voice":
            if ctx.fernet is None:
                ctx.flow_logger.error("Encryption system not initialized, voice message not saved")
                safe_send_message(
                    ctx,
                    chat_id,
                    messages[language]["voice_processing_error"],
                    parse_mode="HTML",
                )
                ctx.bot.register_next_step_handler_by_chat_id(
                    chat_id, callbacks.description_handler
                )
                return

            try:
                downloaded_file = _download_voice_with_retry(ctx, message)
                encrypted_voice = ctx.fernet.encrypt(downloaded_file)
                nickname = ctx.sessions.get_data(user_id, "nickname")
                user_voice_dir = safe_nickname_directory(
                    str(ctx.config.voice_files_dir), nickname
                )
                os.makedirs(user_voice_dir, exist_ok=True)
                filename = new_voice_filename(nickname)
                voice_filename = user_voice_dir / filename
                with open(voice_filename, "wb") as new_file:
                    new_file.write(encrypted_voice)
                voice_submitted = os.path.join(nickname, filename)
                safe_send_message(
                    ctx,
                    chat_id,
                    f"<b>{messages[language]['your_response']}</b> {messages[language]['voice_message_submitted']}",
                    parse_mode="HTML",
                )
            except Exception as voice_error:
                ctx.flow_logger.error(f"Error processing voice message: {voice_error}")
                safe_send_message(
                    ctx,
                    chat_id,
                    messages[language]["voice_processing_error"],
                    parse_mode="HTML",
                )
                ctx.bot.register_next_step_handler_by_chat_id(
                    chat_id, callbacks.description_handler
                )
                return
        else:
            safe_send_message(ctx, chat_id, messages[language]["please_send_text_or_voice"])
            ctx.bot.register_next_step_handler_by_chat_id(
                chat_id, callbacks.description_handler
            )
            return

        ctx.sessions.set_data(user_id, "description", description)
        ctx.sessions.set_data(user_id, "voice_submitted", voice_submitted)
        ctx.sessions.set_data(user_id, "description_done", True)
        callbacks.ask_final_confirmation(chat_id, user_id, language)
    except Exception as exc:
        logging.exception(f"Error in handle_description: {exc}")
        try:
            language = ctx.sessions.get_data(user_id, "language", "en")
            error_msg = messages.get(language, {}).get(
                "error_occurred", messages["en"]["error_occurred"]
            )
            safe_send_message(ctx, chat_id, error_msg)
            inline_kb = types.InlineKeyboardMarkup()
            skip_text = messages.get(language, {}).get("skip_button", "Skip")
            skip_button = types.InlineKeyboardButton(
                text=skip_text, callback_data="description_skip"
            )
            inline_kb.add(skip_button)
            safe_send_message(
                ctx,
                chat_id,
                messages.get(language, {}).get(
                    "description_retry_or_skip",
                    messages["en"]["description_retry_or_skip"],
                ),
                reply_markup=inline_kb,
            )
        except Exception:
            ctx.bot.reply_to(message, messages["en"]["error_occurred"])


def _download_voice_with_retry(ctx: AppContext, message: Any) -> bytes:
    for attempt in range(3):
        try:
            voice_file_id = message.voice.file_id
            file_info = ctx.bot.get_file(voice_file_id)
            return ctx.bot.download_file(file_info.file_path)
        except ApiTelegramException as exc:
            if getattr(exc, "error_code", None) == 429:
                retry_after = telegram_retry_after(exc, default=3)
                ctx.flow_logger.warning(
                    f"Voice download error: {exc}, retrying in {retry_after}s"
                )
                time.sleep(retry_after)
            elif attempt < 2:
                retry_after = 2 ** attempt
                ctx.flow_logger.warning(
                    f"Voice download API error: {exc}, retrying in {retry_after}s"
                )
                time.sleep(retry_after)
            else:
                raise
    raise RuntimeError("Voice download retry loop exhausted")
