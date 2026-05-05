from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from ukrainability_telegram_bot import runtime
from ukrainability_telegram_bot.config import AppConfig


@pytest.fixture(autouse=True)
def reset_runtime_bot(monkeypatch):
    registry = runtime.HandlerRegistry()
    monkeypatch.setattr(runtime, "bot", registry)
    monkeypatch.setattr(runtime, "bot_username", None)
    yield registry


def make_config(tmp_path):
    return AppConfig(
        telegram_bot_token="token",
        encryption_key=Fernet.generate_key().decode("ascii"),
        user_hash_salt="salt",
        storage_dir=tmp_path,
        bot_errors_log=str(tmp_path / "bot_errors.log"),
        flow_control_log=str(tmp_path / "flow_control.log"),
        voice_retention_days=7,
        cleanup_interval_seconds=60,
    )


def test_configure_runtime_binds_dependencies_and_registered_handlers(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    real_bot = MagicMock()
    real_bot.get_me.return_value = SimpleNamespace(username="testbot")
    registered_handlers = []

    def message_handler(*args, **kwargs):
        def decorator(func):
            registered_handlers.append((args, kwargs, func))
            return func

        return decorator

    real_bot.message_handler.side_effect = message_handler
    monkeypatch.setattr(runtime.telebot, "TeleBot", MagicMock(return_value=real_bot))
    monkeypatch.setattr(runtime, "_configure_logging", MagicMock())
    cleanup_bind = MagicMock()
    telegram_io_bind = MagicMock()
    monkeypatch.setattr(runtime.cleanup_module, "bind", cleanup_bind)
    monkeypatch.setattr(runtime.telegram_io_module, "bind", telegram_io_bind)

    def handler(message):
        return message

    runtime.bot.message_handler(commands=["start"])(handler)

    configured_bot = runtime.configure_runtime(
        config,
        cleanup_stale_sessions=lambda hours_inactive=48: None,
        safe_get_language=lambda user_id: "en",
        clear_callback_state=lambda user_id: None,
    )

    assert configured_bot is real_bot
    assert runtime.bot is real_bot
    assert runtime.bot_username == "testbot"
    assert registered_handlers == [((), {"commands": ["start"]}, handler)]
    cleanup_bind.assert_called_once()
    cleanup_kwargs = cleanup_bind.call_args.kwargs
    assert cleanup_kwargs["voice_files_dir"] == str(config.voice_files_dir)
    assert cleanup_kwargs["voice_retention_days"] == 7
    assert cleanup_kwargs["cleanup_interval_seconds"] == 60
    assert cleanup_kwargs["flow_logger"] is runtime.flow_logger
    telegram_io_bind.assert_called_once()
    telegram_kwargs = telegram_io_bind.call_args.kwargs
    assert telegram_kwargs["bot"] is real_bot
    assert telegram_kwargs["flow_logger"] is runtime.flow_logger
    assert callable(telegram_kwargs["safe_get_language"])
    assert callable(telegram_kwargs["clear_callback_state"])


def test_run_calls_after_configure_after_configure_runtime(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    calls = []

    def configure_runtime(*args, **kwargs):
        calls.append("configure_runtime")

    def after_configure():
        calls.append("after_configure")

    def stop_polling():
        raise KeyboardInterrupt

    monkeypatch.setattr(runtime, "configure_runtime", configure_runtime)
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", MagicMock())
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())
    monkeypatch.setattr(runtime, "start_polling_with_retry", stop_polling)

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=lambda: calls.append("initialize_database"),
            recover_user_sessions=lambda: calls.append("recover_user_sessions"),
            cleanup_stale_sessions=lambda hours_inactive=48: None,
            safe_get_language=lambda user_id: "en",
            clear_callback_state=lambda user_id: None,
            after_configure=after_configure,
        )

    assert calls[:2] == ["configure_runtime", "after_configure"]
    assert calls.count("after_configure") == 1


def test_run_exits_when_database_initialization_fails(monkeypatch, tmp_path):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock())

    def fail_initialize_database():
        raise RuntimeError("database unavailable")

    with pytest.raises(SystemExit) as exc_info:
        runtime.run(
            config,
            initialize_database=fail_initialize_database,
            recover_user_sessions=MagicMock(),
            cleanup_stale_sessions=lambda hours_inactive=48: None,
            safe_get_language=lambda user_id: "en",
            clear_callback_state=lambda user_id: None,
            after_configure=MagicMock(),
        )

    assert exc_info.value.code == 1
