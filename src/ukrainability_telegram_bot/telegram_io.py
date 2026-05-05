"""Telegram I/O helpers.

Phase 1 refactor note: this module uses temporary bind-set dependencies to
avoid importing from the legacy `bot.py` module. Phase 2 replaces these
module-level bindings with `AppContext` parameters.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

from .messages import messages


_bot: Any | None = None
_flow_logger: logging.Logger | None = None
_safe_get_language: Callable[[int], str] | None = None
_clear_callback_state: Callable[[int], None] | None = None

message_id_registry: dict[int, dict[str, int]] = {}
message_id_lock = threading.Lock()


def bind(
    *,
    bot: Any,
    flow_logger: logging.Logger,
    safe_get_language: Callable[[int], str] | None = None,
    clear_callback_state: Callable[[int], None] | None = None,
) -> None:
    """Bind temporary legacy dependencies until AppContext replaces them."""

    global _bot
    global _flow_logger
    global _safe_get_language
    global _clear_callback_state

    _bot = bot
    _flow_logger = flow_logger
    _safe_get_language = safe_get_language
    _clear_callback_state = clear_callback_state


def _require_bound() -> tuple[Any, logging.Logger]:
    if _bot is None or _flow_logger is None:
        raise RuntimeError("telegram_io.bind() must be called before use")
    return _bot, _flow_logger


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


def register_message_id(user_id: int, message_type: str, message_id: int) -> None:
    """Register a message ID for a specific user and message type."""

    with message_id_lock:
        if user_id not in message_id_registry:
            message_id_registry[user_id] = {}
        message_id_registry[user_id][message_type] = message_id


def get_message_id(user_id: int, message_type: str) -> int | None:
    """Get a previously registered message ID."""

    with message_id_lock:
        return message_id_registry.get(user_id, {}).get(message_type)


def clear_message_ids(user_id: int) -> None:
    """Clear all message IDs for a user."""

    with message_id_lock:
        if user_id in message_id_registry:
            message_id_registry.pop(user_id)


def send_keyboard_message(
    chat_id: int,
    user_id: int,
    text: str,
    keyboard: Any,
    message_type: str,
    parse_mode: str | None = None,
) -> Any:
    """Send a message with a keyboard and register its ID for future updates."""

    _, flow_logger = _require_bound()
    try:
        msg = safe_send_message(chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)
        register_message_id(user_id, message_type, msg.message_id)
        return msg
    except Exception as e:
        flow_logger.error(f"Error sending keyboard message: {e}")
        # Fall back to regular send without tracking
        return safe_send_message(chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)


def edit_keyboard(user_id: int, chat_id: int, message_type: str, new_keyboard: Any) -> bool:
    """Update a previously sent keyboard using the tracked message ID."""

    bot, flow_logger = _require_bound()
    message_id = get_message_id(user_id, message_type)
    if not message_id:
        flow_logger.warning(f"No message ID found for {message_type}, cannot edit keyboard")
        return False

    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=new_keyboard
        )
        return True
    except ApiTelegramException as e:
        if "message is not modified" in str(e):
            # This is normal, not an error
            return True
        flow_logger.error(f"Failed to edit keyboard: {e}")
        return False
    except Exception as e:
        flow_logger.error(f"Error editing keyboard: {e}")
        return False


def safe_send_message(
    chat_id: int,
    text: str,
    reply_markup: Any = None,
    parse_mode: str | None = None,
    max_retries: int = 3,
) -> Any:
    """Safely send a message with retry logic for rate limits and connection issues."""

    bot, flow_logger = _require_bound()
    for attempt in range(max_retries):
        try:
            return bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except ApiTelegramException as e:
            # Handle rate limiting
            if getattr(e, "error_code", None) == 429:
                retry_after = telegram_retry_after(e, default=3)
                flow_logger.warning(f"Rate limited, waiting {retry_after}s before retry {attempt+1}/{max_retries}")
                time.sleep(retry_after)
                continue
            elif attempt < max_retries - 1:
                # For other API errors, retry with backoff
                flow_logger.warning(f"API error: {e}, retrying in {2**attempt}s")
                time.sleep(2**attempt)
                continue
            else:
                # Last attempt failed, log and raise
                flow_logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            # Non-Telegram exceptions are not rate limits; retry once quickly.
            if attempt == 0:
                flow_logger.warning(f"Error sending message: {e}, retrying once")
                time.sleep(1)
                continue
            else:
                flow_logger.error(f"Failed to send message: {e}")
                raise
    raise RuntimeError("Failed to send message after retry loop")


def send_next_step_prompt(
    chat_id: int,
    text: str,
    handler: Callable[..., Any],
    reply_markup: Any = None,
    parse_mode: str | None = None,
) -> Any:
    """Register the next-step handler before sending the prompt."""

    bot, _ = _require_bound()
    bot.register_next_step_handler_by_chat_id(chat_id, handler)
    return safe_send_message(
        chat_id,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


def escape_html(text: Any) -> str:
    if not isinstance(text, str):
        text = str(text)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _language_for(user_id: int) -> str:
    if _safe_get_language is None:
        return "en"
    return _safe_get_language(user_id)


def handle_callback_error(call: Any, e: Exception, func_name: str) -> None:
    """Enhanced error handler for callback functions with proper state clearing."""

    bot, _ = _require_bound()
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        # Log the error with full details
        logging.exception(f"Error in {func_name}: {e}")

        # Get language safely
        language = _language_for(user_id)
        error_msg = messages[language].get(
            'error_occurred', "An error occurred. Please try again later.")

        # Attempt to clear user's state in a thread-safe way
        if _clear_callback_state is not None:
            _clear_callback_state(user_id)

        # Use safe send to inform the user
        try:
            bot.answer_callback_query(call.id, "Error occurred / Виникла помилка")
            safe_send_message(chat_id, error_msg)

            # Provide a way for the user to recover
            inline_kb = types.InlineKeyboardMarkup()
            restart_text = "Restart" if language == 'en' else "Перезапустити"
            restart_button = types.InlineKeyboardButton(text=restart_text, callback_data='restart')
            inline_kb.add(restart_button)

            safe_send_message(
                chat_id,
                "You can restart the survey if needed:" if language == 'en' else
                "Ви можете перезапустити опитування за потреби:",
                reply_markup=inline_kb
            )
        except Exception as send_error:
            logging.critical(f"Failed to send error message to user: {send_error}")
    except Exception as recovery_error:
        # Last resort logging if the error handler itself fails
        logging.critical(f"Error handler failed: {recovery_error}")


def safe_answer_callback(call: Any, message: str) -> None:
    """Safely answer a callback query, ignoring expired queries."""

    bot, flow_logger = _require_bound()
    try:
        bot.answer_callback_query(call.id, message)
    except telebot.apihelper.ApiTelegramException as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            # Quietly ignore expired callback queries
            flow_logger.info(f"Ignoring expired callback query: {e}")
        else:
            # Re-raise other API exceptions
            flow_logger.error(f"API exception in safe_answer_callback: {e}")
            # Try to send a message to inform user something went wrong
            try:
                user_id = call.from_user.id
                language = _language_for(user_id)
                bot.send_message(call.message.chat.id, messages[language].get(
                    'error_occurred', "An error occurred. Please try again."))
            except Exception:
                pass


def hide_keyboard(chat_id: int) -> None:
    """
    Helper function to hide the keyboard in the chat.
    Uses a completely invisible character (zero-width space) to hide the keyboard.
    """

    bot, _ = _require_bound()
    try:
        remove_keyboard = types.ReplyKeyboardRemove()
        # Use zero-width space (U+200B) - completely invisible character
        bot.send_message(
            chat_id,
            "\u200B",  # Zero-width space character
            reply_markup=remove_keyboard
        )
    except Exception as e:
        # Just log, don't interrupt flow if this fails
        logging.warning(f"Failed to hide keyboard: {e}")
