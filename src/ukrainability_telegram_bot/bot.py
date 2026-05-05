"""Backward-compatible bot module.

Prefer importing from :mod:`ukrainability_telegram_bot.runtime`.
"""

from __future__ import annotations

from .runtime import configure_runtime, run

__all__ = ["configure_runtime", "run"]
