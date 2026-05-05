import logging
import threading
import time

import pytest

from ukrainability_telegram_bot import cleanup


def test_cleanup_raises_when_unbound(monkeypatch):
    monkeypatch.setattr(cleanup, "_voice_files_dir", None)
    monkeypatch.setattr(cleanup, "_flow_logger", None)
    monkeypatch.setattr(cleanup, "_cleanup_stale_sessions", None)

    with pytest.raises(RuntimeError, match="cleanup.bind"):
        cleanup.cleanup_old_voice_messages()


def test_cleanup_scheduler_runs_once_at_startup_then_waits(monkeypatch, tmp_path):
    calls = []
    first_pass = threading.Event()

    def cleanup_sessions(hours_inactive):
        calls.append("sessions")

    def cleanup_voice(days_to_keep):
        calls.append("voice")
        first_pass.set()

    cleanup.bind(
        voice_files_dir=str(tmp_path),
        voice_retention_days=30,
        cleanup_interval_seconds=0.05,
        flow_logger=logging.getLogger("test.cleanup"),
        cleanup_stale_sessions=cleanup_sessions,
    )
    monkeypatch.setattr(
        cleanup,
        "cleanup_old_voice_messages",
        cleanup_voice,
    )

    cleanup.cleanup_stop_event.clear()
    thread = threading.Thread(target=cleanup.cleanup_scheduler)
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
