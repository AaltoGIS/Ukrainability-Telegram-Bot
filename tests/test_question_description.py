from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey.questions import description
from ukrainability_telegram_bot.survey.questions.base import DescriptionCallbacks


def _callbacks(final_confirmation=None, description_handler=None):
    return DescriptionCallbacks(
        ask_final_confirmation=final_confirmation or MagicMock(),
        description_handler=description_handler or MagicMock(),
    )


def _call(data="description_skip", user_id=123, chat_id=456, message_id=789):
    return SimpleNamespace(
        id="callback-id",
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            chat=SimpleNamespace(id=chat_id),
            message_id=message_id,
        ),
    )


def _message(content_type, user_id=123, chat_id=456, text="", voice=None):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(id=user_id),
        content_type=content_type,
        text=text,
        voice=voice,
    )


@pytest.mark.parametrize("language", ["en", "uk"])
def test_ask_description_sends_voice_instructions_and_registers_before_send(
    app_context,
    language,
):
    calls = []
    handler = MagicMock()
    callbacks = _callbacks(description_handler=handler)
    app_context.bot.register_next_step_handler_by_chat_id.side_effect = (
        lambda chat_id, callback: calls.append(("register", chat_id, callback))
    )
    app_context.bot.send_message.side_effect = (
        lambda chat_id, text, **kwargs: calls.append(("send", chat_id, text)) or SimpleNamespace(message_id=1)
    )

    description.ask_description(app_context, 456, 123, language, callbacks)

    assert calls[0] == ("register", 456, handler)
    assert calls[1][0:2] == ("send", 456)
    assert messages[language]["voice_instruction"] in calls[1][2]


def test_handle_description_skip_marks_done_and_calls_confirmation(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    final_confirmation = MagicMock()
    callbacks = _callbacks(final_confirmation=final_confirmation)

    description.handle_description_skip(
        app_context,
        _call(user_id=user_id),
        callbacks,
    )

    app_context.bot.clear_step_handler_by_chat_id.assert_called_once_with(456)
    assert app_context.sessions.get_data(user_id, "description_done") is True
    final_confirmation.assert_called_once_with(456, user_id, "en")


def test_handle_description_text_stores_text_and_calls_confirmation(app_context):
    user_id = 123
    app_context.sessions.set_data(user_id, "language", "en")
    final_confirmation = MagicMock()
    callbacks = _callbacks(final_confirmation=final_confirmation)

    description.handle_description(
        app_context,
        _message("text", user_id=user_id, text="  Lovely <place>  "),
        callbacks,
    )

    assert app_context.sessions.get_data(user_id, "description") == "Lovely <place>"
    assert app_context.sessions.get_data(user_id, "voice_submitted") == ""
    assert app_context.sessions.get_data(user_id, "description_done") is True
    final_confirmation.assert_called_once_with(456, user_id, "en")
    assert "Lovely &lt;place&gt;" in app_context.bot.send_message.call_args.args[1]


def test_handle_description_voice_encrypts_and_records_relative_path(
    app_context,
    monkeypatch,
):
    user_id = 123
    nickname = "SafeNick1"
    filename = "SafeNick1 fixed.enc"
    app_context.sessions.set_data(user_id, "language", "en")
    app_context.sessions.set_data(user_id, "nickname", nickname)
    app_context.bot.get_file.return_value = SimpleNamespace(file_path="voice/file.ogg")
    app_context.bot.download_file.return_value = b"voice-bytes"
    monkeypatch.setattr(description, "new_voice_filename", lambda nick: filename)
    final_confirmation = MagicMock()
    callbacks = _callbacks(final_confirmation=final_confirmation)

    description.handle_description(
        app_context,
        _message(
            "voice",
            user_id=user_id,
            voice=SimpleNamespace(file_id="voice-file-id"),
        ),
        callbacks,
    )

    relative_path = f"{nickname}/{filename}"
    stored_file = Path(app_context.config.voice_files_dir) / nickname / filename
    assert app_context.sessions.get_data(user_id, "description") == ""
    assert app_context.sessions.get_data(user_id, "voice_submitted") == relative_path
    assert app_context.sessions.get_data(user_id, "description_done") is True
    assert app_context.fernet.decrypt(stored_file.read_bytes()) == b"voice-bytes"
    final_confirmation.assert_called_once_with(456, user_id, "en")
