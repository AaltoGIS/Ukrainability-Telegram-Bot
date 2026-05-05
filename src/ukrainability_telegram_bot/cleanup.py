"""Cleanup scheduler and voice-file retention helpers."""

from __future__ import annotations

import os
import threading
import time

from .app import AppContext

cleanup_stop_event = threading.Event()
cleanup_thread_lock = threading.Lock()
cleanup_thread: threading.Thread | None = None


def cleanup_old_voice_messages(ctx: AppContext, days_to_keep: int | None = None) -> None:
    """
    Cleans up voice messages older than the specified number of days.
    This prevents unlimited storage growth.
    """

    voice_files_dir = str(ctx.config.voice_files_dir)
    flow_logger = ctx.flow_logger
    try:
        if days_to_keep is None:
            days_to_keep = ctx.config.voice_retention_days
        flow_logger.info(
            f"Starting voice message cleanup, keeping messages from last {days_to_keep} days"
        )
        current_time = time.time()
        cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
        total_deleted = 0

        # Walk through voice files directory
        for root, _dirs, files in os.walk(voice_files_dir):
            for file in files:
                if file.endswith(".enc"):  # Only process encrypted voice files
                    file_path = os.path.join(root, file)
                    file_time = os.path.getmtime(file_path)

                    # Check if file is older than cutoff
                    if file_time < cutoff_time:
                        try:
                            os.remove(file_path)
                            total_deleted += 1
                        except Exception as e:
                            flow_logger.error(f"Failed to delete old voice file {file_path}: {e}")

        flow_logger.info(f"Voice message cleanup complete. Deleted {total_deleted} files.")
    except Exception as e:
        flow_logger.error(f"Error in voice message cleanup: {e}")


def cleanup_scheduler(ctx: AppContext) -> None:
    """Periodically runs cleanup tasks in the background."""

    flow_logger = ctx.flow_logger
    voice_retention_days = ctx.config.voice_retention_days
    cleanup_interval_seconds = ctx.config.cleanup_interval_seconds

    def run_cleanup_pass() -> None:
        removed_users = ctx.sessions.evict_inactive(hours=48)
        if removed_users:
            flow_logger.info(
                "Stale session cleanup complete. Removed %s sessions.",
                len(removed_users),
            )
        cleanup_old_voice_messages(ctx, days_to_keep=voice_retention_days)

    while not cleanup_stop_event.is_set():
        try:
            run_cleanup_pass()
        except Exception as e:
            flow_logger.exception(f"Error in cleanup scheduler: {e}")
            if cleanup_stop_event.wait(min(cleanup_interval_seconds, 60 * 60)):
                break
            continue

        if cleanup_stop_event.wait(cleanup_interval_seconds):
            break


def start_cleanup_scheduler(ctx: AppContext) -> threading.Thread:
    """Start the background cleanup thread if it is not already running."""

    global cleanup_thread
    with cleanup_thread_lock:
        if cleanup_thread is None or not cleanup_thread.is_alive():
            cleanup_stop_event.clear()
            cleanup_thread = threading.Thread(target=cleanup_scheduler, args=(ctx,), daemon=True)
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
