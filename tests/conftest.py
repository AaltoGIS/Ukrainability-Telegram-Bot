import sys
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet, MultiFernet


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from ukrainability_telegram_bot.app import AppContext
from ukrainability_telegram_bot.cleanup import cleanup_stop_event
from ukrainability_telegram_bot.config import AppConfig
from ukrainability_telegram_bot.sessions import SessionStore
from ukrainability_telegram_bot.storage import initialize_database


def make_mocked_telebot():
    bot = MagicMock()
    bot.message_handler = MagicMock(side_effect=lambda *args, **kwargs: lambda func: func)
    bot.callback_query_handler = MagicMock(
        side_effect=lambda *args, **kwargs: lambda func: func
    )
    bot.get_me.return_value = SimpleNamespace(username="testbot")
    return bot


@pytest.fixture
def mocked_telebot():
    return make_mocked_telebot()


@pytest.fixture
def app_context(tmp_path):
    bot = make_mocked_telebot()
    initialize_database(tmp_path / "responses_kremenchuk.db")
    config = AppConfig(
        telegram_bot_token="token",
        encryption_key=Fernet.generate_key().decode("ascii"),
        user_hash_salt="salt",
        storage_dir=tmp_path,
        bot_errors_log=str(tmp_path / "bot_errors.log"),
        flow_control_log=str(tmp_path / "flow_control.log"),
        voice_retention_days=30,
        cleanup_interval_seconds=24 * 60 * 60,
    )
    return AppContext(
        config=config,
        bot=bot,
        fernet=MultiFernet([Fernet(config.encryption_key.encode("ascii"))]),
        sessions=SessionStore(),
        flow_logger=logging.getLogger("test.flow"),
        bot_username="testbot",
        cleanup_stop_event=cleanup_stop_event,
    )
