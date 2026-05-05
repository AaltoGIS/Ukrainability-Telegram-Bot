"""Application context shared across runtime modules."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import MultiFernet

from .config import AppConfig
from .sessions import SessionStore


@dataclass
class AppContext:
    """Runtime dependencies for one bot process."""

    config: AppConfig
    bot: Any
    fernet: MultiFernet
    sessions: SessionStore
    flow_logger: logging.Logger
    bot_username: str
    cleanup_stop_event: threading.Event
