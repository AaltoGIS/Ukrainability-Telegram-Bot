import pytest

fernet_module = pytest.importorskip("cryptography.fernet")

from ukrainability_telegram_bot.security import build_fernet, decrypt_text, encrypt_text


def test_build_fernet_encrypts_and_decrypts_text():
    key = fernet_module.Fernet.generate_key().decode()
    fernet = build_fernet(key)

    encrypted = encrypt_text(fernet, "survey response")

    assert encrypted != "survey response"
    assert decrypt_text(fernet, encrypted) == "survey response"


def test_build_fernet_decrypts_with_retiring_key():
    old_key = fernet_module.Fernet.generate_key().decode()
    new_key = fernet_module.Fernet.generate_key().decode()
    old_fernet = build_fernet(old_key)
    rotated_fernet = build_fernet(new_key, [old_key])

    encrypted_with_old_key = encrypt_text(old_fernet, "historical response")

    assert decrypt_text(rotated_fernet, encrypted_with_old_key) == "historical response"


def test_multifernet_encrypts_and_decrypts_voice_bytes():
    key = fernet_module.Fernet.generate_key().decode()
    fernet = build_fernet(key)
    payload = b"telegram voice bytes"

    encrypted = fernet.encrypt(payload)

    assert encrypted != payload
    assert fernet.decrypt(encrypted) == payload


def test_build_fernet_rejects_invalid_key():
    with pytest.raises(ValueError, match="Invalid encryption key"):
        build_fernet("not-a-fernet-key")
