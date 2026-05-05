"""Command-line entrypoint for the Ukrainability Telegram bot."""

from __future__ import annotations


def main() -> None:
    from .bot import run
    from .config import AppConfig

    run(AppConfig.from_env())
