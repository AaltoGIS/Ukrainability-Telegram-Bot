from types import SimpleNamespace

import pytest

from ukrainability_telegram_bot import bot


def test_telegram_retry_after_coerces_string_and_caps():
    error = SimpleNamespace(result_json={"parameters": {"retry_after": "120"}})

    assert bot.telegram_retry_after(error) == 60.0


def test_telegram_retry_after_falls_back_for_bad_values():
    error = SimpleNamespace(result_json={"parameters": {"retry_after": "later"}})

    assert bot.telegram_retry_after(error, default=7) == 7.0


def test_callback_index_validates_prefix_and_bounds():
    options = ["yes", "no"]

    assert bot.callback_index("consent_1", "consent", options) == 1
    with pytest.raises(ValueError):
        bot.callback_index("purpose_1", "consent", options)
    with pytest.raises(IndexError):
        bot.callback_index("consent_2", "consent", options)


def test_save_data_and_restart_skips_insert_when_consent_denied(monkeypatch, tmp_path):
    user_id = 123
    monkeypatch.setattr(bot, "db_file", str(tmp_path / "responses.db"))
    monkeypatch.setattr(bot, "clear_message_ids", lambda user_id: None)
    monkeypatch.setattr(bot, "send_welcome", lambda **kwargs: None)

    with bot.user_data_lock:
        bot.user_data[user_id] = {"language": "en"}
        bot.user_profiles[user_id] = {"consent": False}

    try:
        assert bot.save_data_and_restart(456, user_id, "en") is True
        assert not (tmp_path / "responses.db").exists()
    finally:
        with bot.user_data_lock:
            bot.user_data.pop(user_id, None)
            bot.user_profiles.pop(user_id, None)
