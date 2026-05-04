"""Keyboard construction helpers."""

from __future__ import annotations

try:
    from telebot import types
except ImportError:  # pragma: no cover - tests can monkeypatch this module
    types = None


def create_inline_keyboard(
    options: list[str],
    prefix: str,
    *,
    single_select: bool = False,
    done_text: str = "Done",
):
    if types is None:
        raise RuntimeError("pyTelegramBotAPI is required to create Telegram keyboards")

    keyboard = types.InlineKeyboardMarkup()
    for idx, option in enumerate(options):
        keyboard.add(types.InlineKeyboardButton(text=option, callback_data=f"{prefix}_{idx}"))
    if not single_select:
        keyboard.add(types.InlineKeyboardButton(text=done_text, callback_data=f"{prefix}_done"))
    return keyboard
