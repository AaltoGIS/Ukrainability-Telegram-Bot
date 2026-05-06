"""Application configuration loading."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is installed in normal use
    load_dotenv = None


DEFAULT_STORAGE_DIR = "/home/ubuntu/kremenchuk"
DEFAULT_CREDENTIALS_FILE = "/home/ubuntu/kremenchuk/secure/credentials"
RESPONSES_DB_FILENAME = "responses_kremenchuk.db"
VOICE_MESSAGES_DIRNAME = "voice_messages"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings for the Telegram bot."""

    telegram_bot_token: str
    encryption_key: str
    user_hash_salt: str
    retiring_encryption_keys: tuple[str, ...] = ()
    storage_dir: Path = Path(DEFAULT_STORAGE_DIR)
    credentials_file: Path | None = Path(DEFAULT_CREDENTIALS_FILE)
    bot_errors_log: str = "bot_errors.log"
    flow_control_log: str = "flow_control.log"
    log_max_bytes: int = 5_000_000
    log_backup_count: int = 5
    voice_retention_days: int = 30
    cleanup_interval_seconds: int = 24 * 60 * 60

    @property
    def db_file(self) -> Path:
        return self.storage_dir / RESPONSES_DB_FILENAME

    @property
    def voice_files_dir(self) -> Path:
        return self.storage_dir / VOICE_MESSAGES_DIRNAME

    @classmethod
    def from_env(
        cls,
        environ: MutableMapping[str, str] | None = None,
        *,
        load_dotenv_file: bool = True,
    ) -> AppConfig:
        env = os.environ if environ is None else environ
        if load_dotenv_file and load_dotenv is not None:
            load_dotenv()

        credentials_file = Path(env.get("UKRAINABILITY_CREDENTIALS_FILE", DEFAULT_CREDENTIALS_FILE))
        credentials = read_export_file(credentials_file)

        token = env.get("TELEGRAM_BOT_TOKEN") or credentials.get("TELEGRAM_BOT_TOKEN")
        encryption_keys = split_keys(
            env.get("ENCRYPTION_KEYS") or credentials.get("ENCRYPTION_KEYS", "")
        )
        encryption_key = (
            encryption_keys[0]
            if encryption_keys
            else env.get("ENCRYPTION_KEY") or credentials.get("ENCRYPTION_KEY")
        )
        retiring_encryption_keys = tuple(encryption_keys[1:])
        user_hash_salt = env.get("UKRAINABILITY_USER_HASH_SALT") or credentials.get(
            "UKRAINABILITY_USER_HASH_SALT"
        )

        missing = [
            name
            for name, value in (
                ("TELEGRAM_BOT_TOKEN", token),
                ("ENCRYPTION_KEY", encryption_key),
                ("UKRAINABILITY_USER_HASH_SALT", user_hash_salt),
            )
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required configuration: {joined}")

        storage_dir = Path(env.get("UKRAINABILITY_STORAGE_DIR", DEFAULT_STORAGE_DIR))

        return cls(
            telegram_bot_token=str(token),
            encryption_key=str(encryption_key),
            user_hash_salt=str(user_hash_salt),
            retiring_encryption_keys=retiring_encryption_keys,
            storage_dir=storage_dir,
            credentials_file=credentials_file,
            bot_errors_log=env.get("UKRAINABILITY_BOT_ERRORS_LOG", "bot_errors.log"),
            flow_control_log=env.get("UKRAINABILITY_FLOW_CONTROL_LOG", "flow_control.log"),
            log_max_bytes=_int_env(env, "UKRAINABILITY_LOG_MAX_BYTES", 5_000_000),
            log_backup_count=_int_env(env, "UKRAINABILITY_LOG_BACKUP_COUNT", 5),
            voice_retention_days=_int_env(env, "UKRAINABILITY_VOICE_RETENTION_DAYS", 30),
            cleanup_interval_seconds=_int_env(
                env, "UKRAINABILITY_CLEANUP_INTERVAL_SECONDS", 24 * 60 * 60
            ),
        )


def read_export_file(path: Path) -> Mapping[str, str]:
    """Read shell-style ``export NAME=value`` lines from a credentials file."""

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or not stripped.startswith("export "):
            continue
        key_value = stripped[len("export ") :]
        if "=" not in key_value:
            continue
        key, value = key_value.split("=", 1)
        stripped_value = value.strip()
        if _has_unbalanced_quotes(stripped_value):
            logger.warning("Credentials value for %s contains unbalanced quotes", key.strip())
            values[key.strip()] = stripped_value
            continue
        values[key.strip()] = stripped_value.strip("\"'")

    return values


def split_keys(value: str) -> tuple[str, ...]:
    """Split a comma-separated key list into stripped non-empty keys."""

    return tuple(key.strip() for key in value.split(",") if key.strip())


def _has_unbalanced_quotes(value: str) -> bool:
    return value.count('"') % 2 == 1 or value.count("'") % 2 == 1


def _int_env(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
