"""Telegram I/O helpers."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

from .app import AppContext
from .messages import messages


def telegram_retry_after(error: Any, default: int | float = 3) -> float:
    def capped(value: Any) -> float:
        try:
            return min(float(value), 60.0)
        except (TypeError, ValueError):
            return min(float(default), 60.0)

    result_json = getattr(error, "result_json", None)
    if isinstance(result_json, dict):
        retry_after = result_json.get("parameters", {}).get("retry_after")
        if retry_after is not None:
            return capped(retry_after)
    result = getattr(error, "result", None)
    if isinstance(result, dict):
        retry_after = result.get("parameters", {}).get("retry_after")
        if retry_after is not None:
            return capped(retry_after)
    return capped(default)


def redacted_coordinate(value: Any) -> float | str:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return "unknown"


def callback_suffix(callback_data: str, prefix: str) -> str:
    marker = f"{prefix}_"
    if not callback_data.startswith(marker):
        raise ValueError(f"Unexpected callback prefix for {prefix}")
    return callback_data[len(marker):]


def callback_index(callback_data: str, prefix: str, options: list[str]) -> int:
    suffix = callback_suffix(callback_data, prefix)
    idx = int(suffix)
    if idx < 0 or idx >= len(options):
        raise IndexError(f"Callback index {idx} out of range for {prefix}")
    return idx


def register_message_id(ctx: AppContext, user_id: int, message_type: str, message_id: int) -> None:
    """Register a message ID for a specific user and message type."""

    ctx.sessions.register_message_id(user_id, message_type, message_id)


def get_message_id(ctx: AppContext, user_id: int, message_type: str) -> int | None:
    """Get a previously registered message ID."""

    return ctx.sessions.get_message_id(user_id, message_type)


def clear_message_ids(ctx: AppContext, user_id: int) -> None:
    """Clear all message IDs for a user."""

    ctx.sessions.clear_message_ids(user_id)


def send_keyboard_message(
    ctx: AppContext,
    chat_id: int,
    user_id: int,
    text: str,
    keyboard: Any,
    message_type: str,
    parse_mode: str | None = None,
) -> Any:
    """Send a message with a keyboard and register its ID for future updates."""

    try:
        msg = safe_send_message(ctx, chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)
        register_message_id(ctx, user_id, message_type, msg.message_id)
        return msg
    except Exception as e:
        ctx.flow_logger.error(f"Error sending keyboard message: {e}")
        return safe_send_message(ctx, chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)


def edit_keyboard(
    ctx: AppContext,
    user_id: int,
    chat_id: int,
    message_type: str,
    new_keyboard: Any,
) -> bool:
    """Update a previously sent keyboard using the tracked message ID."""

    message_id = get_message_id(ctx, user_id, message_type)
    if not message_id:
        ctx.flow_logger.warning(f"No message ID found for {message_type}, cannot edit keyboard")
        return False

    try:
        ctx.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=new_keyboard
        )
        return True
    except ApiTelegramException as e:
        if "message is not modified" in str(e):
            return True
        ctx.flow_logger.error(f"Failed to edit keyboard: {e}")
        return False
    except Exception as e:
        ctx.flow_logger.error(f"Error editing keyboard: {e}")
        return False


def safe_send_message(
    ctx: AppContext,
    chat_id: int,
    text: str,
    reply_markup: Any = None,
    parse_mode: str | None = None,
    max_retries: int = 3,
) -> Any:
    """Safely send a message with retry logic for rate limits and connection issues."""

    for attempt in range(max_retries):
        try:
            return ctx.bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except ApiTelegramException as e:
            if getattr(e, "error_code", None) == 429:
                retry_after = telegram_retry_after(e, default=3)
                ctx.flow_logger.warning(f"Rate limited, waiting {retry_after}s before retry {attempt+1}/{max_retries}")
                time.sleep(retry_after)
                continue
            if attempt < max_retries - 1:
                ctx.flow_logger.warning(f"API error: {e}, retrying in {2**attempt}s")
                time.sleep(2**attempt)
                continue
            ctx.flow_logger.error(f"Failed to send message after {max_retries} attempts: {e}")
            raise
        except Exception as e:
            if attempt == 0:
                ctx.flow_logger.warning(f"Error sending message: {e}, retrying once")
                time.sleep(1)
                continue
            ctx.flow_logger.error(f"Failed to send message: {e}")
            raise
    raise RuntimeError("Failed to send message after retry loop")


def send_next_step_prompt(
    ctx: AppContext,
    chat_id: int,
    text: str,
    handler: Callable[..., Any],
    reply_markup: Any = None,
    parse_mode: str | None = None,
) -> Any:
    """Register the next-step handler before sending the prompt."""

    ctx.bot.register_next_step_handler_by_chat_id(chat_id, handler)
    return safe_send_message(
        ctx,
        chat_id,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


def escape_html(text: Any) -> str:
    if not isinstance(text, str):
        text = str(text)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _language_for(ctx: AppContext, user_id: int) -> str:
    language = ctx.sessions.get_data(user_id, "language")
    if language:
        return language
    language = ctx.sessions.get_profile(user_id, "language")
    return language or "en"


def handle_callback_error(
    ctx: AppContext,
    call: Any,
    e: Exception,
    func_name: str,
    *,
    clear_callback_state: Callable[[int], None] | None = None,
) -> None:
    """Enhanced error handler for callback functions with proper state clearing."""

    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        logging.exception(f"Error in {func_name}: {e}")
        language = _language_for(ctx, user_id)
        error_msg = messages[language].get(
            'error_occurred', "An error occurred. Please try again later.")

        if clear_callback_state is not None:
            clear_callback_state(user_id)

        try:
            ctx.bot.answer_callback_query(call.id, "Error occurred / Виникла помилка")
            safe_send_message(ctx, chat_id, error_msg)

            inline_kb = types.InlineKeyboardMarkup()
            restart_text = "Restart" if language == 'en' else "Перезапустити"
            restart_button = types.InlineKeyboardButton(text=restart_text, callback_data='restart')
            inline_kb.add(restart_button)

            safe_send_message(
                ctx,
                chat_id,
                "You can restart the survey if needed:" if language == 'en' else
                "Ви можете перезапустити опитування за потреби:",
                reply_markup=inline_kb
            )
        except Exception as send_error:
            logging.critical(f"Failed to send error message to user: {send_error}")
    except Exception as recovery_error:
        logging.critical(f"Error handler failed: {recovery_error}")


def safe_answer_callback(ctx: AppContext, call: Any, message: str) -> None:
    """Safely answer a callback query, ignoring expired queries."""

    try:
        ctx.bot.answer_callback_query(call.id, message)
    except telebot.apihelper.ApiTelegramException as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            ctx.flow_logger.info(f"Ignoring expired callback query: {e}")
        else:
            ctx.flow_logger.error(f"API exception in safe_answer_callback: {e}")
            try:
                user_id = call.from_user.id
                language = _language_for(ctx, user_id)
                ctx.bot.send_message(call.message.chat.id, messages[language].get(
                    'error_occurred', "An error occurred. Please try again."))
            except Exception:
                pass


def hide_keyboard(ctx: AppContext, chat_id: int) -> None:
    """Hide the reply keyboard in the chat."""

    try:
        remove_keyboard = types.ReplyKeyboardRemove()
        ctx.bot.send_message(
            chat_id,
            "\u200B",
            reply_markup=remove_keyboard
        )
    except Exception as e:
        logging.warning(f"Failed to hide keyboard: {e}")
