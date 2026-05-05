"""Runtime setup, polling, and handler registry.

Phase 2 refactor note: this module owns `AppContext` construction while the
legacy survey handlers still register at import time. Phase 5 removes
`HandlerRegistry` and the temporary active-context bridge.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from typing import Any

import requests
import telebot
from telebot.apihelper import ApiTelegramException

from .app import AppContext
from .cleanup import cleanup_old_voice_messages, cleanup_stop_event, start_cleanup_scheduler
from .config import AppConfig, DEFAULT_STORAGE_DIR
from .security import build_fernet
from .sessions import SessionStore
from .telegram_io import telegram_retry_after


class HandlerRegistry:
    """Collect handler decorators until a real TeleBot is configured.

    `bind()` replays the collected decorators onto the real TeleBot and keeps
    this registry object alive as a proxy. This lets legacy handler code keep
    calling `bot.send_message(...)` through `__getattr__` until Phase 5 removes
    import-time registration.
    """

    def __init__(self):
        self._handlers = []
        self._real_bot = None

    def bind(self, real_bot):
        self._real_bot = real_bot
        for handler_name, args, kwargs, handler_func in self._handlers:
            decorator = getattr(real_bot, handler_name)(*args, **kwargs)
            decorator(handler_func)
        return self

    def __getattr__(self, name):
        """Fall through to the bound TeleBot for legacy `bot.X(...)` calls."""

        if self._real_bot is None:
            raise AttributeError(name)
        return getattr(self._real_bot, name)

    def _register(self, handler_name, *args, **kwargs):
        def decorator(handler_func):
            self._handlers.append((handler_name, args, kwargs, handler_func))
            if self._real_bot is not None:
                getattr(self._real_bot, handler_name)(*args, **kwargs)(handler_func)
            return handler_func

        return decorator

    def message_handler(self, *args, **kwargs):
        return self._register("message_handler", *args, **kwargs)

    def callback_query_handler(self, *args, **kwargs):
        return self._register("callback_query_handler", *args, **kwargs)


flow_logger = logging.getLogger('flow_control')
flow_logger.setLevel(logging.INFO)

# TODO(phase-5): remove these legacy scalar mirrors when bot.py no longer
# depends on import-time module globals; AppContext is the canonical state.
token = None
local_storage_dir = DEFAULT_STORAGE_DIR
voice_files_dir = os.path.join(local_storage_dir, 'voice_messages')
user_hash_salt = None
voice_retention_days = 30
cleanup_interval_seconds = 24 * 60 * 60
db_file = os.path.join(local_storage_dir, 'responses_kremenchuk.db')
fernet = None

# TODO(phase-5): remove with import-time registration.
bot = HandlerRegistry()
bot_username = None

# TODO(phase-5): remove when handlers are registered against an explicit context.
_active_context: AppContext | None = None


def _load_legacy_flow() -> Any:
    """Import legacy survey handlers so their temporary decorators are registered."""

    from .survey import legacy_flow

    return legacy_flow


def require_active_context() -> AppContext:
    if _active_context is None:
        raise RuntimeError("runtime.configure_runtime() must be called before use")
    return _active_context


def _configure_logging(config: AppConfig) -> None:
    root_handler = RotatingFileHandler(
        config.bot_errors_log,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
    )
    root_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)
    if not any(
        isinstance(existing, RotatingFileHandler)
        and getattr(existing, "baseFilename", None).endswith(config.bot_errors_log)
        for existing in root_logger.handlers
    ):
        root_logger.addHandler(root_handler)

    if not any(
        isinstance(existing, RotatingFileHandler)
        and getattr(existing, "baseFilename", None).endswith(config.flow_control_log)
        for existing in flow_logger.handlers
    ):
        handler = RotatingFileHandler(
            config.flow_control_log,
            maxBytes=config.log_max_bytes,
            backupCount=config.log_backup_count,
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'))
        flow_logger.addHandler(handler)
    flow_logger.setLevel(logging.INFO)


def configure_runtime(
    config: AppConfig,
) -> AppContext:
    """Configure runtime dependencies for one bot process."""

    global token
    global local_storage_dir
    global voice_files_dir
    global db_file
    global fernet
    global bot
    global bot_username
    global user_hash_salt
    global voice_retention_days
    global cleanup_interval_seconds
    global _active_context

    _configure_logging(config)
    _load_legacy_flow()
    token = config.telegram_bot_token
    local_storage_dir = str(config.storage_dir)
    voice_files_dir = str(config.voice_files_dir)
    db_file = str(config.db_file)
    user_hash_salt = config.user_hash_salt
    voice_retention_days = config.voice_retention_days
    cleanup_interval_seconds = config.cleanup_interval_seconds

    os.makedirs(local_storage_dir, exist_ok=True)
    os.makedirs(voice_files_dir, exist_ok=True)

    fernet = build_fernet(config.encryption_key, list(config.retiring_encryption_keys))

    real_bot = telebot.TeleBot(token, threaded=True)
    if isinstance(bot, HandlerRegistry):
        bot.bind(real_bot)
    else:
        bot = real_bot

    bot_info = real_bot.get_me()
    bot_username = bot_info.username
    _active_context = AppContext(
        config=config,
        bot=real_bot,
        fernet=fernet,
        sessions=SessionStore(),
        flow_logger=flow_logger,
        bot_username=bot_username,
        cleanup_stop_event=cleanup_stop_event,
    )
    return _active_context


def check_telegram_connection() -> bool:
    """Check if the connection to Telegram API is active."""

    try:
        bot.get_me()
        return True
    except Exception as e:
        flow_logger.error(f"Connection check failed: {e}")
        return False


def start_polling_with_retry() -> bool:
    max_retries = 10
    initial_delay = 5
    max_delay = 300

    for retry in range(max_retries):
        try:
            bot.polling(non_stop=True, interval=1, timeout=60)
            return True
        except requests.exceptions.ReadTimeout:
            delay = min(initial_delay * (2 ** retry), max_delay)
            flow_logger.warning(f"Read timeout occurred (attempt {retry+1}/{max_retries}), retrying in {delay} seconds...")
            time.sleep(delay)
        except requests.exceptions.ConnectionError:
            delay = min(initial_delay * (2 ** retry), max_delay)
            flow_logger.warning(f"Connection error (attempt {retry+1}/{max_retries}), retrying in {delay} seconds...")

            try:
                test_connection = requests.get("https://www.google.com", timeout=5)
                if test_connection.status_code == 200:
                    flow_logger.info("Internet connection appears to be working, likely a Telegram API issue")
                else:
                    flow_logger.warning("Internet connection test failed with status code: " + str(test_connection.status_code))
            except Exception as conn_test_error:
                flow_logger.warning(f"Internet connection test failed: {conn_test_error}")

            time.sleep(delay)
        except ApiTelegramException as e:
            if getattr(e, "error_code", None) == 429:
                retry_after = telegram_retry_after(e, default=30)
                flow_logger.warning(f"Rate limited by Telegram API, waiting {retry_after} seconds before retry")
                time.sleep(retry_after + 5)
            else:
                delay = min(initial_delay * (2 ** retry), max_delay)
                flow_logger.error(f"Telegram API error: {e}, retrying in {delay} seconds")
                time.sleep(delay)
        except Exception as e:
            delay = min(initial_delay * (2 ** retry) * 2, max_delay)
            flow_logger.error(f"Unexpected error in polling: {e}")
            time.sleep(delay)

    flow_logger.critical("Exhausted all polling retries, bot may be down!")
    return False


def run(
    config: AppConfig | None = None,
    *,
    initialize_database: Callable[[], None] | None = None,
    recover_user_sessions: Callable[[], None] | None = None,
) -> None:
    if config is None:
        config = AppConfig.from_env()
    legacy_flow = _load_legacy_flow()
    if initialize_database is None:
        initialize_database = legacy_flow.initialize_database
    if recover_user_sessions is None:
        recover_user_sessions = legacy_flow.recover_user_sessions
    ctx = configure_runtime(config)

    startup_message = f"Bot starting with username: {bot_username}"
    print(startup_message)
    flow_logger.info(startup_message)

    try:
        initialize_database()
        flow_logger.info("Database initialized successfully")
    except Exception as e:
        flow_logger.error(f"Failed to initialize database: {e}")
        print(f"ERROR: Database initialization failed: {e}")
        sys.exit(1)

    try:
        recover_user_sessions()
    except Exception as e:
        flow_logger.error(f"Session recovery failed: {e}")

    try:
        cleanup_old_voice_messages(ctx)
    except Exception as e:
        flow_logger.error(f"Voice message cleanup failed: {e}")

    start_cleanup_scheduler(ctx)

    consecutive_fast_failures = 0
    failure_threshold_time = 5
    max_consecutive_fast_failures = 8
    last_error_time = 0

    while True:
        try:
            current_time = time.time()
            if consecutive_fast_failures > max_consecutive_fast_failures:
                time_since_last_error = current_time - last_error_time
                if time_since_last_error < 60:
                    recovery_time = 60 - time_since_last_error
                    flow_logger.warning(f"Too many errors recently, pausing for {recovery_time:.1f} seconds")
                    time.sleep(recovery_time)
                    consecutive_fast_failures = max_consecutive_fast_failures // 2

            print("Starting bot polling...")
            flow_logger.info("Starting bot polling loop")
            start_time = time.time()

            polling_successful = start_polling_with_retry()

            if not polling_successful:
                flow_logger.critical("All polling retries failed, entering recovery mode")
                time.sleep(60)
                continue

            flow_logger.warning("Bot polling ended normally. Restarting polling loop.")
            time.sleep(3)

        except Exception as e:
            last_error_time = time.time()
            runtime = last_error_time - start_time

            if runtime < failure_threshold_time:
                consecutive_fast_failures += 1
                recovery_delay = min(30, 2 * consecutive_fast_failures)
                error_msg = f"Bot polling failed quickly after {runtime:.2f}s (consecutive failure #{consecutive_fast_failures}): {e}"
            else:
                consecutive_fast_failures = max(0, consecutive_fast_failures - 1)
                recovery_delay = 5
                error_msg = f"Bot polling failed after {runtime:.2f}s: {e}"

            logging.exception(error_msg)
            flow_logger.error(error_msg)
            print(error_msg)

            if consecutive_fast_failures > max_consecutive_fast_failures:
                flow_logger.critical(f"Detected {consecutive_fast_failures} consecutive fast failures. Entering extended recovery mode.")
                recovery_delay = 60

                try:
                    if check_telegram_connection():
                        flow_logger.info("Successfully reconnected to Telegram API")
                        consecutive_fast_failures = consecutive_fast_failures // 2
                except Exception as conn_err:
                    flow_logger.error(f"Failed to check Telegram connection in recovery mode: {conn_err}")

                try:
                    initialize_database()
                    flow_logger.info("Successfully reinitialized database connection")
                except Exception as db_err:
                    flow_logger.error(f"Failed to reinitialize database: {db_err}")

            print(f"Waiting {recovery_delay} seconds before retry...")
            time.sleep(recovery_delay)
