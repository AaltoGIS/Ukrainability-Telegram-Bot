from ukrainability_telegram_bot.messages import messages


def test_messages_include_supported_languages_and_core_prompts():
    assert {"en", "uk"} <= set(messages)
    assert messages["en"]["welcome"]
    assert messages["uk"]["welcome"]
    assert "consent_options" in messages["en"]
    assert "consent_options" in messages["uk"]
