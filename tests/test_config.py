from pathlib import Path

import pytest

from ukrainability_telegram_bot.config import AppConfig


def test_config_loads_from_environment(tmp_path):
    env = {
        "TELEGRAM_BOT_TOKEN": "telegram-token",
        "ENCRYPTION_KEY": "fernet-key",
        "UKRAINABILITY_USER_HASH_SALT": "hash-salt",
        "UKRAINABILITY_STORAGE_DIR": str(tmp_path),
    }

    config = AppConfig.from_env(env, load_dotenv_file=False)

    assert config.telegram_bot_token == "telegram-token"
    assert config.encryption_key == "fernet-key"
    assert config.user_hash_salt == "hash-salt"
    assert config.storage_dir == tmp_path
    assert config.db_file == tmp_path / "responses_kremenchuk.db"
    assert config.voice_files_dir == tmp_path / "voice_messages"


def test_config_loads_legacy_credentials_file(tmp_path):
    credentials = tmp_path / "credentials"
    credentials.write_text(
        'export TELEGRAM_BOT_TOKEN="legacy-token"\n'
        "export ENCRYPTION_KEY='legacy-key'\n"
        "export UKRAINABILITY_USER_HASH_SALT='legacy-salt'\n",
        encoding="utf-8",
    )
    env = {
        "UKRAINABILITY_CREDENTIALS_FILE": str(credentials),
        "UKRAINABILITY_STORAGE_DIR": str(tmp_path / "storage"),
    }

    config = AppConfig.from_env(env, load_dotenv_file=False)

    assert config.telegram_bot_token == "legacy-token"
    assert config.encryption_key == "legacy-key"
    assert config.user_hash_salt == "legacy-salt"


def test_config_supports_key_rotation_list(tmp_path):
    env = {
        "TELEGRAM_BOT_TOKEN": "telegram-token",
        "ENCRYPTION_KEYS": "active-key, old-key-1, old-key-2",
        "UKRAINABILITY_USER_HASH_SALT": "hash-salt",
        "UKRAINABILITY_STORAGE_DIR": str(tmp_path),
    }

    config = AppConfig.from_env(env, load_dotenv_file=False)

    assert config.encryption_key == "active-key"
    assert config.retiring_encryption_keys == ("old-key-1", "old-key-2")


def test_config_reports_missing_required_values(tmp_path):
    with pytest.raises(
        ValueError,
        match="TELEGRAM_BOT_TOKEN, ENCRYPTION_KEY, UKRAINABILITY_USER_HASH_SALT",
    ):
        AppConfig.from_env(
            {
                "UKRAINABILITY_CREDENTIALS_FILE": str(tmp_path / "missing"),
            },
            load_dotenv_file=False,
        )
