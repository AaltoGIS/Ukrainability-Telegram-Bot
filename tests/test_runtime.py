from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests
from cryptography.fernet import Fernet
from telebot.apihelper import ApiTelegramException

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


def test_configure_logging_attaches_rotating_handlers(tmp_path):
    config = make_config(tmp_path)
    runtime._configure_logging(config)

    runtime._configure_logging(config)


def test_check_telegram_connection_returns_true_on_success(app_context):
    assert runtime.check_telegram_connection(app_context) is True


def test_check_telegram_connection_returns_false_on_exception(app_context):
    app_context.bot.get_me.side_effect = ConnectionError("boom")

    assert runtime.check_telegram_connection(app_context) is False


def test_start_polling_with_retry_returns_true_on_clean_polling(app_context):
    assert runtime.start_polling_with_retry(app_context) is True
    app_context.bot.polling.assert_called_once_with(non_stop=True, interval=1, timeout=60)


def test_start_polling_with_retry_handles_read_timeout(app_context, monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    app_context.bot.polling.side_effect = [requests.exceptions.ReadTimeout("slow"), None]

    assert runtime.start_polling_with_retry(app_context) is True
    assert app_context.bot.polling.call_count == 2


def test_start_polling_with_retry_handles_connection_error_and_internet_check_ok(
    app_context, monkeypatch
):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "ukrainability_telegram_bot.runtime.requests.get",
        MagicMock(return_value=SimpleNamespace(status_code=200)),
    )
    app_context.bot.polling.side_effect = [requests.exceptions.ConnectionError("no net"), None]

    assert runtime.start_polling_with_retry(app_context) is True


def test_start_polling_with_retry_handles_connection_error_and_internet_check_bad_status(
    app_context, monkeypatch
):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "ukrainability_telegram_bot.runtime.requests.get",
        MagicMock(return_value=SimpleNamespace(status_code=503)),
    )
    app_context.bot.polling.side_effect = [requests.exceptions.ConnectionError("no net"), None]

    assert runtime.start_polling_with_retry(app_context) is True


def test_start_polling_with_retry_handles_connection_error_when_internet_check_raises(
    app_context, monkeypatch
):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "ukrainability_telegram_bot.runtime.requests.get",
        MagicMock(side_effect=ConnectionError("DNS")),
    )
    app_context.bot.polling.side_effect = [requests.exceptions.ConnectionError("no net"), None]

    assert runtime.start_polling_with_retry(app_context) is True


def test_start_polling_with_retry_handles_429_then_success(app_context, monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    rate_limited = ApiTelegramException(
        "/getUpdates",
        "/getUpdates",
        {"error_code": 429, "description": "Too Many Requests", "parameters": {"retry_after": 1}},
    )
    app_context.bot.polling.side_effect = [rate_limited, None]

    assert runtime.start_polling_with_retry(app_context) is True


def test_start_polling_with_retry_handles_other_telegram_api_error_then_success(
    app_context, monkeypatch
):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    other_err = ApiTelegramException(
        "/getUpdates",
        "/getUpdates",
        {"error_code": 502, "description": "Bad gateway"},
    )
    app_context.bot.polling.side_effect = [other_err, None]

    assert runtime.start_polling_with_retry(app_context) is True


def test_start_polling_with_retry_handles_unexpected_exception_then_success(
    app_context, monkeypatch
):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    app_context.bot.polling.side_effect = [RuntimeError("?"), None]

    assert runtime.start_polling_with_retry(app_context) is True


def test_start_polling_with_retry_returns_false_when_retries_exhausted(app_context, monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    app_context.bot.polling.side_effect = requests.exceptions.ReadTimeout("slow")

    assert runtime.start_polling_with_retry(app_context) is False


def test_run_uses_default_database_callable_when_none(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", MagicMock())
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())

    init_db = MagicMock()
    recover = MagicMock()
    monkeypatch.setattr(runtime.startup, "initialize_database", init_db)
    monkeypatch.setattr(runtime.startup, "recover_user_sessions", recover)
    monkeypatch.setattr(
        runtime, "start_polling_with_retry", MagicMock(side_effect=KeyboardInterrupt)
    )

    with pytest.raises(KeyboardInterrupt):
        runtime.run(config)

    init_db.assert_called_once_with(app_context)
    recover.assert_called_once_with(app_context)


def test_run_swallows_session_recovery_failure(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", MagicMock())
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())
    monkeypatch.setattr(
        runtime, "start_polling_with_retry", MagicMock(side_effect=KeyboardInterrupt)
    )

    def fail_recover():
        raise RuntimeError("nope")

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=MagicMock(),
            recover_user_sessions=fail_recover,
        )


def test_run_swallows_voice_cleanup_failure(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))
    monkeypatch.setattr(
        runtime, "cleanup_old_voice_messages", MagicMock(side_effect=RuntimeError("boom"))
    )
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())
    monkeypatch.setattr(
        runtime, "start_polling_with_retry", MagicMock(side_effect=KeyboardInterrupt)
    )

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=MagicMock(),
            recover_user_sessions=MagicMock(),
        )


def test_run_recovers_when_polling_returns_false(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", MagicMock())
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)

    polling_results = [False, KeyboardInterrupt]

    def polling(ctx):
        result = polling_results.pop(0)
        if isinstance(result, type) and issubclass(result, BaseException):
            raise result()
        return result

    monkeypatch.setattr(runtime, "start_polling_with_retry", polling)

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=MagicMock(),
            recover_user_sessions=MagicMock(),
        )


def test_run_handles_polling_exception_and_then_keyboard_interrupt(
    monkeypatch, tmp_path, app_context
):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", MagicMock())
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())

    sleeps = []
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda d: sleeps.append(d))

    polling_calls = {"n": 0}

    def polling(ctx):
        polling_calls["n"] += 1
        if polling_calls["n"] == 1:
            raise RuntimeError("polling crashed")
        raise KeyboardInterrupt()

    monkeypatch.setattr(runtime, "start_polling_with_retry", polling)

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=MagicMock(),
            recover_user_sessions=MagicMock(),
        )

    assert polling_calls["n"] == 2


def test_run_extended_recovery_after_many_fast_failures(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", MagicMock())
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    monkeypatch.setattr(runtime, "check_telegram_connection", MagicMock(return_value=True))

    counter = {"n": 0}
    init_db = MagicMock()

    def polling(ctx):
        counter["n"] += 1
        if counter["n"] <= 10:
            raise RuntimeError("fast fail")
        raise KeyboardInterrupt()

    monkeypatch.setattr(runtime, "start_polling_with_retry", polling)

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=init_db,
            recover_user_sessions=MagicMock(),
        )

    assert init_db.call_count >= 2


def test_run_extended_recovery_handles_check_connection_failure(monkeypatch, tmp_path, app_context):
    config = make_config(tmp_path)
    monkeypatch.setattr(runtime, "configure_runtime", MagicMock(return_value=app_context))
    monkeypatch.setattr(runtime, "cleanup_old_voice_messages", MagicMock())
    monkeypatch.setattr(runtime, "start_cleanup_scheduler", MagicMock())
    monkeypatch.setattr("ukrainability_telegram_bot.runtime.time.sleep", lambda _: None)
    monkeypatch.setattr(
        runtime,
        "check_telegram_connection",
        MagicMock(side_effect=RuntimeError("conn check failed")),
    )

    counter = {"n": 0}

    def polling(ctx):
        counter["n"] += 1
        if counter["n"] <= 10:
            raise RuntimeError("fast fail")
        raise KeyboardInterrupt()

    monkeypatch.setattr(runtime, "start_polling_with_retry", polling)

    init_db = MagicMock(side_effect=[None] + [RuntimeError("db re-init failed")] * 20)

    with pytest.raises(KeyboardInterrupt):
        runtime.run(
            config,
            initialize_database=init_db,
            recover_user_sessions=MagicMock(),
        )
