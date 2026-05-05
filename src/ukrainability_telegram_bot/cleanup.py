"""Cleanup scheduler and voice-file retention helpers.

Phase 1 refactor note: this module uses temporary bind-set dependencies to
avoid importing from the legacy `bot.py` module. Phase 2 replaces these
module-level bindings with `AppContext` parameters.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable


_voice_files_dir: str | None = None
_voice_retention_days = 30
_cleanup_interval_seconds = 24 * 60 * 60
_flow_logger: logging.Logger | None = None
_cleanup_stale_sessions: Callable[[int], None] | None = None

cleanup_stop_event = threading.Event()
cleanup_thread_lock = threading.Lock()
cleanup_thread: threading.Thread | None = None


def bind(
    *,
    voice_files_dir: str,
    voice_retention_days: int,
    cleanup_interval_seconds: int,
    flow_logger: logging.Logger,
    cleanup_stale_sessions: Callable[[int], None],
) -> None:
    """Bind temporary legacy dependencies until AppContext replaces them."""

    global _voice_files_dir
    global _voice_retention_days
    global _cleanup_interval_seconds
    global _flow_logger
    global _cleanup_stale_sessions

    _voice_files_dir = voice_files_dir
    _voice_retention_days = voice_retention_days
    _cleanup_interval_seconds = cleanup_interval_seconds
    _flow_logger = flow_logger
    _cleanup_stale_sessions = cleanup_stale_sessions


def _require_bound() -> tuple[str, logging.Logger, Callable[[int], None]]:
    if (
        _voice_files_dir is None
        or _flow_logger is None
        or _cleanup_stale_sessions is None
    ):
        raise RuntimeError("cleanup.bind() must be called before use")
    return _voice_files_dir, _flow_logger, _cleanup_stale_sessions


def cleanup_old_voice_messages(days_to_keep: int | None = None) -> None:
    """
    Cleans up voice messages older than the specified number of days.
    This prevents unlimited storage growth.
    """

    voice_files_dir, flow_logger, _ = _require_bound()
    try:
        if days_to_keep is None:
            days_to_keep = _voice_retention_days
        flow_logger.info(
            f"Starting voice message cleanup, keeping messages from last {days_to_keep} days")
        current_time = time.time()
        cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
        total_deleted = 0

        # Walk through voice files directory
        for root, dirs, files in os.walk(voice_files_dir):
            for file in files:
                if file.endswith('.enc'):  # Only process encrypted voice files
                    file_path = os.path.join(root, file)
                    file_time = os.path.getmtime(file_path)

                    # Check if file is older than cutoff
                    if file_time < cutoff_time:
                        try:
                            os.remove(file_path)
                            total_deleted += 1
                        except Exception as e:
                            flow_logger.error(
                                f"Failed to delete old voice file {file_path}: {e}")

        flow_logger.info(
            f"Voice message cleanup complete. Deleted {total_deleted} files.")
    except Exception as e:
        flow_logger.error(f"Error in voice message cleanup: {e}")


def cleanup_scheduler() -> None:
    """Periodically runs cleanup tasks in the background."""

    _, flow_logger, cleanup_stale_sessions = _require_bound()

    def run_cleanup_pass() -> None:
        cleanup_stale_sessions(hours_inactive=48)
        cleanup_old_voice_messages(days_to_keep=_voice_retention_days)

    while not cleanup_stop_event.is_set():
        try:
            run_cleanup_pass()
        except Exception as e:
            flow_logger.exception(f"Error in cleanup scheduler: {e}")
            if cleanup_stop_event.wait(min(_cleanup_interval_seconds, 60 * 60)):
                break
            continue

        if cleanup_stop_event.wait(_cleanup_interval_seconds):
            break


def start_cleanup_scheduler() -> threading.Thread:
    """Start the background cleanup thread if it is not already running."""

    global cleanup_thread
    _require_bound()
    with cleanup_thread_lock:
        if cleanup_thread is None or not cleanup_thread.is_alive():
            cleanup_stop_event.clear()
            cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True)
            cleanup_thread.start()
    return cleanup_thread


def stop_cleanup_scheduler(timeout: int | float = 5) -> None:
    """Signal the background cleanup thread to stop and wait briefly."""

    global cleanup_thread
    with cleanup_thread_lock:
        cleanup_stop_event.set()
        thread = cleanup_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout)
