import pytest

from ukrainability_telegram_bot.voice import new_voice_filename, safe_nickname_directory


def test_safe_nickname_directory_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        safe_nickname_directory(tmp_path, "../Bad")


def test_new_voice_filename_uses_random_suffix(monkeypatch):
    monkeypatch.setattr("ukrainability_telegram_bot.voice.secrets.token_hex", lambda n: "abc123")

    assert new_voice_filename("Bright Fox 7") == "Bright Fox 7 abc123.enc"
