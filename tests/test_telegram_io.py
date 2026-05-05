from types import SimpleNamespace

from ukrainability_telegram_bot import telegram_io


def test_telegram_io_safe_send_message_uses_context_bot(app_context):
    app_context.bot.send_message.return_value = SimpleNamespace(message_id=42)

    msg = telegram_io.safe_send_message(app_context, 123, "hello")

    assert msg.message_id == 42
    app_context.bot.send_message.assert_called_once_with(
        123,
        "hello",
        reply_markup=None,
        parse_mode=None,
    )


def test_telegram_io_message_ids_live_in_session_store(app_context):
    telegram_io.register_message_id(app_context, 123, "purpose_visit", 456)

    assert telegram_io.get_message_id(app_context, 123, "purpose_visit") == 456

    telegram_io.clear_message_ids(app_context, 123)

    assert telegram_io.get_message_id(app_context, 123, "purpose_visit") is None


def test_send_next_step_prompt_registers_before_send(app_context):
    calls = []

    def handler(message):
        return message

    app_context.bot.register_next_step_handler_by_chat_id.side_effect = (
        lambda chat_id, callback: calls.append(("register", chat_id, callback))
    )
    app_context.bot.send_message.side_effect = lambda chat_id, text, **kwargs: calls.append(
        ("send", chat_id, text)
    ) or SimpleNamespace(message_id=1)

    telegram_io.send_next_step_prompt(app_context, 123, "prompt", handler)

    assert calls[0] == ("register", 123, handler)
    assert calls[1] == ("send", 123, "prompt")
