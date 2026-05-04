import pytest

fernet_module = pytest.importorskip("cryptography.fernet")

from ukrainability_telegram_bot.security import build_fernet, encrypt_text


def test_build_fernet_encrypts_and_decrypts_text():
    key = fernet_module.Fernet.generate_key().decode()
    fernet = build_fernet(key)

    encrypted = encrypt_text(fernet, "survey response")

    assert encrypted != "survey response"
    assert fernet.decrypt(encrypted.encode()).decode() == "survey response"


def test_build_fernet_rejects_invalid_key():
    with pytest.raises(ValueError, match="Invalid encryption key"):
        build_fernet("not-a-fernet-key")
