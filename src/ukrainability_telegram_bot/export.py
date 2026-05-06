"""Decrypt stored survey responses and voice files for controlled export.

Partial decrypt failures are reported in the command output, but do not make
the export command fail; the successfully decrypted data is still written.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path

from cryptography.fernet import InvalidToken, MultiFernet

from . import config, security, storage

DECRYPT_FAILED = "<decrypt-failed>"
logger = logging.getLogger(__name__)


def default_storage_dir(environ: Mapping[str, str] | None = None) -> Path:
    """Return the configured storage directory used for export defaults."""

    env = os.environ if environ is None else environ
    return Path(env.get("UKRAINABILITY_STORAGE_DIR", config.DEFAULT_STORAGE_DIR))


def load_encryption_keys(
    environ: Mapping[str, str] | None = None,
    *,
    load_dotenv_file: bool = True,
) -> tuple[str, tuple[str, ...]]:
    """Load the active Fernet key and retiring keys from env or credentials."""

    if environ is None:
        env = os.environ
        if load_dotenv_file and config.load_dotenv is not None:
            config.load_dotenv()
    else:
        env = environ

    credentials_file = Path(
        env.get("UKRAINABILITY_CREDENTIALS_FILE", config.DEFAULT_CREDENTIALS_FILE)
    )
    credentials = config.read_export_file(credentials_file)
    encryption_keys = config.split_keys(
        env.get("ENCRYPTION_KEYS") or credentials.get("ENCRYPTION_KEYS", "")
    )
    encryption_key = (
        encryption_keys[0]
        if encryption_keys
        else env.get("ENCRYPTION_KEY") or credentials.get("ENCRYPTION_KEY")
    )
    if not encryption_key:
        raise ValueError("Missing required configuration: ENCRYPTION_KEY")

    return str(encryption_key), tuple(encryption_keys[1:])


def decrypt_field(
    fernet: MultiFernet,
    value: str | bytes | int | float | None,
) -> str | int | float | None:
    """Decrypt one encrypted response field, preserving empty/plain values."""

    if value is None or value == "":
        return value
    if not isinstance(value, str | bytes):
        return value
    encrypted = value.encode() if isinstance(value, str) else value
    try:
        return fernet.decrypt(encrypted).decode("utf-8", errors="strict")
    except (InvalidToken, UnicodeDecodeError):
        return DECRYPT_FAILED


def export_responses(db_path: Path, out_csv: Path, fernet: MultiFernet) -> int:
    """Write decrypted responses to CSV and return failed field count."""

    encrypted_cols = set(storage.ENCRYPTED_COLUMNS)
    drop_cols = {"id"}

    con = sqlite3.connect(db_path)
    try:
        con.row_factory = sqlite3.Row
        cur = con.execute("SELECT * FROM responses ORDER BY timestamp")
        columns = [description[0] for description in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()

    out_columns = [column for column in columns if column not in drop_cols]
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    failed = 0
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(out_columns)
        for row in rows:
            out_row = []
            for column in out_columns:
                if column in encrypted_cols:
                    decrypted = decrypt_field(fernet, row[column])
                    if decrypted == DECRYPT_FAILED:
                        failed += 1
                        logger.warning(
                            "Decrypt failed for column %s in response row %s",
                            column,
                            row["id"],
                        )
                    out_row.append(decrypted)
                else:
                    out_row.append(row[column])
            writer.writerow(out_row)

    summary = f"responses: {len(rows)} rows -> {out_csv}"
    if failed:
        summary += f" ({failed} failed fields)"
    print(summary)
    return failed


def export_voice(voice_dir: Path, out_dir: Path, fernet: MultiFernet) -> tuple[int, int]:
    """Decrypt encrypted voice files and return ``(ok, failed)`` counts."""

    out_dir.mkdir(parents=True, exist_ok=True)
    ok = failed = 0
    for encrypted_file in voice_dir.glob("*.enc"):
        try:
            (out_dir / encrypted_file.stem).with_suffix(".ogg").write_bytes(
                fernet.decrypt(encrypted_file.read_bytes())
            )
            ok += 1
        except InvalidToken:
            failed += 1
    print(f"voice: {ok} decrypted, {failed} failed -> {out_dir}")
    return ok, failed


def _build_parser(env: Mapping[str, str]) -> argparse.ArgumentParser:
    storage_dir = default_storage_dir(env)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=storage_dir / config.RESPONSES_DB_FILENAME,
        help="SQLite database path (default: %(default)s).",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output CSV path.")
    parser.add_argument(
        "--voice-dir",
        type=Path,
        default=storage_dir / config.VOICE_MESSAGES_DIRNAME,
        help="Encrypted voice message directory (default: %(default)s).",
    )
    parser.add_argument(
        "--voice-out",
        type=Path,
        default=None,
        help="Output directory for decrypted voice files.",
    )
    parser.add_argument(
        "--no-voice",
        action="store_true",
        help="Skip voice decryption even if voice messages exist.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    load_dotenv_file: bool = True,
) -> None:
    """Run the export command."""

    if environ is None:
        env = os.environ
        if load_dotenv_file and config.load_dotenv is not None:
            config.load_dotenv()
    else:
        env = environ

    parser = _build_parser(env)
    args = parser.parse_args(argv)

    encryption_key, retiring_keys = load_encryption_keys(env, load_dotenv_file=False)
    fernet = security.build_fernet(encryption_key, list(retiring_keys))
    export_responses(args.db, args.out, fernet)

    voice_out = args.voice_out or args.out.with_name("voice_decrypted")
    if not args.no_voice and args.voice_dir.is_dir():
        export_voice(args.voice_dir, voice_out, fernet)


if __name__ == "__main__":
    main()
