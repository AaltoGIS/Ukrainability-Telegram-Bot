import threading
import time

from ukrainability_telegram_bot import cleanup


def test_cleanup_old_voice_messages_uses_context_storage(app_context, tmp_path):
    user_dir = tmp_path / "voice_messages" / "Test User"
    user_dir.mkdir(parents=True)
    old_file = user_dir / "old.enc"
    old_file.write_bytes(b"encrypted")
    old_time = time.time() - (31 * 24 * 60 * 60)
    old_file.touch()
    import os

    os.utime(old_file, (old_time, old_time))

    cleanup.cleanup_old_voice_messages(app_context, days_to_keep=30)

    assert not old_file.exists()


def test_cleanup_scheduler_runs_once_at_startup_then_waits(monkeypatch, app_context):
    calls = []
    first_pass = threading.Event()
    app_context.config = app_context.config.__class__(
        telegram_bot_token=app_context.config.telegram_bot_token,
        encryption_key=app_context.config.encryption_key,
        user_hash_salt=app_context.config.user_hash_salt,
        storage_dir=app_context.config.storage_dir,
        bot_errors_log=app_context.config.bot_errors_log,
        flow_control_log=app_context.config.flow_control_log,
        voice_retention_days=30,
        cleanup_interval_seconds=0.05,
    )

    def cleanup_voice(ctx, days_to_keep):
        calls.append("voice")
        first_pass.set()

    monkeypatch.setattr(cleanup, "cleanup_old_voice_messages", cleanup_voice)

    def evict_inactive(hours):
        calls.append("sessions")
        return []

    monkeypatch.setattr(app_context.sessions, "evict_inactive", evict_inactive)

    cleanup.cleanup_stop_event.clear()
    thread = threading.Thread(target=cleanup.cleanup_scheduler, args=(app_context,))
    thread.start()
    try:
        assert first_pass.wait(timeout=1)
        assert calls == ["sessions", "voice"]
        time.sleep(0.01)
        assert calls == ["sessions", "voice"]
    finally:
        cleanup.cleanup_stop_event.set()
        thread.join(timeout=1)
        cleanup.cleanup_stop_event.clear()
