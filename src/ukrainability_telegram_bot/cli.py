"""Command-line entrypoint for the Ukrainability Telegram bot."""

from __future__ import annotations


def main() -> None:
    from .config import AppConfig
    from .runtime import run

    run(AppConfig.from_env())
