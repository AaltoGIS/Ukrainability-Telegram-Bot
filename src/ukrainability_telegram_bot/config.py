"""Application configuration loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is installed in normal use
    load_dotenv = None


DEFAULT_STORAGE_DIR = "/home/ubuntu/kremenchuk"
DEFAULT_CREDENTIALS_FILE = "/home/ubuntu/kremenchuk/secure/credentials"


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings for the Telegram bot."""

    telegram_bot_token: str
    encryption_key: str
    storage_dir: Path = Path(DEFAULT_STORAGE_DIR)
    credentials_file: Optional[Path] = Path(DEFAULT_CREDENTIALS_FILE)
    bot_errors_log: str = "bot_errors.log"
    flow_control_log: str = "flow_control.log"

    @property
    def db_file(self) -> Path:
        return self.storage_dir / "responses_kremenchuk.db"

    @property
    def voice_files_dir(self) -> Path:
        return self.storage_dir / "voice_messages"

    @classmethod
    def from_env(
        cls,
        environ: Optional[MutableMapping[str, str]] = None,
        *,
        load_dotenv_file: bool = True,
    ) -> "AppConfig":
        env = os.environ if environ is None else environ
        if load_dotenv_file and load_dotenv is not None:
            load_dotenv()

        credentials_file = Path(
            env.get("UKRAINABILITY_CREDENTIALS_FILE", DEFAULT_CREDENTIALS_FILE)
        )
        credentials = _read_export_file(credentials_file)

        token = env.get("TELEGRAM_BOT_TOKEN") or credentials.get("TELEGRAM_BOT_TOKEN")
        encryption_key = env.get("ENCRYPTION_KEY") or credentials.get("ENCRYPTION_KEY")

        missing = [
            name
            for name, value in (
                ("TELEGRAM_BOT_TOKEN", token),
                ("ENCRYPTION_KEY", encryption_key),
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
            storage_dir=storage_dir,
            credentials_file=credentials_file,
            bot_errors_log=env.get("UKRAINABILITY_BOT_ERRORS_LOG", "bot_errors.log"),
            flow_control_log=env.get("UKRAINABILITY_FLOW_CONTROL_LOG", "flow_control.log"),
        )


def _read_export_file(path: Path) -> Mapping[str, str]:
    """Read shell-style `export NAME=value` lines from the legacy credentials file."""

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
        values[key.strip()] = value.strip().strip("\"'")

    return values
