import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ukrainability_telegram_bot import telegram_io


def test_telegram_io_raises_when_unbound(monkeypatch):
    monkeypatch.setattr(telegram_io, "_bot", None)
    monkeypatch.setattr(telegram_io, "_flow_logger", None)

    with pytest.raises(RuntimeError, match="telegram_io.bind"):
        telegram_io.safe_send_message(123, "hello")


def test_telegram_io_bind_allows_safe_send_message(monkeypatch):
    monkeypatch.setattr(telegram_io, "_bot", None)
    monkeypatch.setattr(telegram_io, "_flow_logger", None)
    mock_bot = MagicMock()
    mock_bot.send_message.return_value = SimpleNamespace(message_id=42)

    telegram_io.bind(bot=mock_bot, flow_logger=logging.getLogger("test.telegram_io"))

    msg = telegram_io.safe_send_message(123, "hello")

    assert msg.message_id == 42
    mock_bot.send_message.assert_called_once_with(
        123,
        "hello",
        reply_markup=None,
        parse_mode=None,
    )
