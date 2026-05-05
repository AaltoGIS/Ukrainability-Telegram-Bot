"""Runtime setup, handler registration, and polling."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler

import requests
import telebot
from telebot.apihelper import ApiTelegramException

from .app import AppContext
from .cleanup import cleanup_old_voice_messages, cleanup_stop_event, start_cleanup_scheduler
from .config import AppConfig
from .handlers import register_handlers
from .security import build_fernet
from .sessions import SessionStore
from . import startup
from .telegram_io import telegram_retry_after


flow_logger = logging.getLogger('flow_control')
flow_logger.setLevel(logging.INFO)


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

    _configure_logging(config)
    config.storage_dir.mkdir(parents=True, exist_ok=True)
    config.voice_files_dir.mkdir(parents=True, exist_ok=True)

    fernet = build_fernet(config.encryption_key, list(config.retiring_encryption_keys))

    real_bot = telebot.TeleBot(config.telegram_bot_token, threaded=True)

    bot_info = real_bot.get_me()
    ctx = AppContext(
        config=config,
        bot=real_bot,
        fernet=fernet,
        sessions=SessionStore(),
        flow_logger=flow_logger,
        bot_username=bot_info.username,
        cleanup_stop_event=cleanup_stop_event,
    )
    register_handlers(ctx)
    return ctx


def check_telegram_connection(ctx: AppContext) -> bool:
    """Check if the connection to Telegram API is active."""

    try:
        ctx.bot.get_me()
        return True
    except Exception as e:
        flow_logger.error(f"Connection check failed: {e}")
        return False


def start_polling_with_retry(ctx: AppContext) -> bool:
    max_retries = 10
    initial_delay = 5
    max_delay = 300

    for retry in range(max_retries):
        try:
            ctx.bot.polling(non_stop=True, interval=1, timeout=60)
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
    ctx = configure_runtime(config)
    if initialize_database is None:
        initialize_database = lambda: startup.initialize_database(ctx)
    if recover_user_sessions is None:
        recover_user_sessions = lambda: startup.recover_user_sessions(ctx)

    startup_message = f"Bot starting with username: {ctx.bot_username}"
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

            polling_successful = start_polling_with_retry(ctx)

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
                    if check_telegram_connection(ctx):
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
