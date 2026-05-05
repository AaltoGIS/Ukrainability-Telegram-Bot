from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from ukrainability_telegram_bot import runtime
from ukrainability_telegram_bot.app import AppContext
from ukrainability_telegram_bot.config import AppConfig


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


def test_configure_runtime_builds_context_and_registers_handlers(monkeypatch, tmp_path):
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

    ctx = runtime.configure_runtime(config)

    assert isinstance(ctx, AppContext)
    assert ctx.bot is real_bot
    assert ctx.config is config
    assert ctx.flow_logger is runtime.flow_logger
    assert ctx.bot_username == "testbot"
    registered_names = {handler.__name__ for _args, _kwargs, handler in registered_handlers}
    assert "send_welcome" in registered_names
    assert "handle_text_messages" in registered_names


def test_runtime_no_longer_exposes_active_context():
    assert not hasattr(runtime, "_active_context")
    assert not hasattr(runtime, "require_active_context")


def test_register_handlers_lives_in_handlers_module():
    assert runtime.register_handlers.__module__ == "ukrainability_telegram_bot.handlers"


def test_runtime_no_longer_exposes_scalar_mirrors():
    removed_names = {
        "token",
        "local_storage_dir",
        "voice_files_dir",
        "user_hash_salt",
        "voice_retention_days",
        "cleanup_interval_seconds",
        "db_file",
        "fernet",
        "bot",
        "bot_username",
    }

    for name in removed_names:
        assert not hasattr(runtime, name)


def test_run_configures_context_before_startup_tasks(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    calls = []

    def configure_runtime(config_arg):
        calls.append(("configure_runtime", config_arg))
        return app_context

    def cleanup_old_voice_messages(ctx):
        calls.append(("cleanup_voice", ctx))

    def start_cleanup_scheduler(ctx):
        calls.append(("start_cleanup", ctx))

    def stop_polling(ctx):
        calls.append(("polling", ctx))
        raise KeyboardInterrupt

    monkeypatch.setattr(runtime, "configure_runtime", configure_runtime)
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", cleanup_old_voice_messages)
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", start_cleanup_scheduler)
    monkeypatch.setattr(runtime, "start_polling_with_retry", stop_polling)

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=lambda: calls.append(("initialize_database", None)),
            recover_user_sessions=lambda: calls.append(("recover_user_sessions", None)),
        )

    assert calls[:4] == [
        ("configure_runtime", config),
        ("initialize_database", None),
        ("recover_user_sessions", None),
        ("cleanup_voice", app_context),
    ]
    assert calls[4] == ("start_cleanup", app_context)
    assert calls[5] == ("polling", app_context)


def test_run_exits_when_database_initialization_fails(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))

    def fail_initialize_database():
        raise RuntimeError("database unavailable")

    with pytest.raises(SystemExit) as exc_info:
        runtime.run(
            config,
            initialize_database=fail_initialize_database,
            recover_user_sessions=MagicMock(),
        )

    assert exc_info.value.code == 1
