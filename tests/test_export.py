import csv
import sqlite3
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from ukrainability_telegram_bot import export
from ukrainability_telegram_bot.security import build_fernet
from ukrainability_telegram_bot.storage import RESPONSE_COLUMNS, insert_response
from ukrainability_telegram_bot.survey.persistence import encrypt_row


def _insert_encrypted_row(app_context, **overrides):
    row = {column: f"value-{column}" for column in RESPONSE_COLUMNS}
    row.update(overrides)
    encrypted = encrypt_row(app_context.fernet, row)
    return insert_response(app_context.config.db_file, encrypted)


def _read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_csv_header(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def test_export_responses_writes_plaintext_csv(app_context, tmp_path):
    for index in range(3):
        _insert_encrypted_row(
            app_context,
            nickname=f"Nickname{index}",
            timestamp=f"2025-01-0{index + 1} 12:00:00",
        )
    out_csv = tmp_path / "responses.csv"

    failed = export.export_responses(app_context.config.db_file, out_csv, app_context.fernet)

    assert failed == 0
    assert _read_csv_header(out_csv) == list(RESPONSE_COLUMNS)
    rows = _read_csv(out_csv)
    assert [row["nickname"] for row in rows] == ["Nickname0", "Nickname1", "Nickname2"]
    assert rows[0]["latitude"] == "value-latitude"


def test_export_responses_omits_id_column(app_context, tmp_path):
    _insert_encrypted_row(app_context)
    out_csv = tmp_path / "responses.csv"

    export.export_responses(app_context.config.db_file, out_csv, app_context.fernet)

    assert "id" not in _read_csv_header(out_csv)


def test_export_responses_creates_parent_dir(app_context, tmp_path):
    _insert_encrypted_row(app_context)
    out_csv = tmp_path / "deep" / "nested" / "responses.csv"

    export.export_responses(app_context.config.db_file, out_csv, app_context.fernet)

    assert out_csv.exists()


def test_export_responses_marks_corrupt_row_as_failed(app_context, tmp_path):
    _insert_encrypted_row(app_context)
    with sqlite3.connect(app_context.config.db_file) as conn:
        conn.execute("UPDATE responses SET nickname = 'garbage'")
    out_csv = tmp_path / "responses.csv"

    failed = export.export_responses(app_context.config.db_file, out_csv, app_context.fernet)

    assert failed == 1
    assert _read_csv(out_csv)[0]["nickname"] == export.DECRYPT_FAILED


def test_export_responses_orders_rows_by_timestamp(app_context, tmp_path):
    _insert_encrypted_row(app_context, nickname="Later", timestamp="2025-01-02 12:00:00")
    _insert_encrypted_row(app_context, nickname="Earlier", timestamp="2025-01-01 12:00:00")
    out_csv = tmp_path / "responses.csv"

    export.export_responses(app_context.config.db_file, out_csv, app_context.fernet)

    rows = _read_csv(out_csv)
    assert [row["nickname"] for row in rows] == ["Earlier", "Later"]


def test_export_voice_decrypts_to_ogg(app_context, tmp_path):
    voice_dir = tmp_path / "voice_messages"
    voice_dir.mkdir()
    encrypted = app_context.fernet.encrypt(b"voice-bytes")
    (voice_dir / "AbcCat03.enc").write_bytes(encrypted)
    out_dir = tmp_path / "voice_decrypted"

    assert export.export_voice(voice_dir, out_dir, app_context.fernet) == (1, 0)
    assert (out_dir / "AbcCat03.ogg").read_bytes() == b"voice-bytes"


def test_export_voice_counts_corrupt_files(app_context, tmp_path, capsys):
    voice_dir = tmp_path / "voice_messages"
    voice_dir.mkdir()
    (voice_dir / "good.enc").write_bytes(app_context.fernet.encrypt(b"ok"))
    (voice_dir / "bad.enc").write_bytes(b"not-a-token")
    out_dir = tmp_path / "voice_decrypted"

    assert export.export_voice(voice_dir, out_dir, app_context.fernet) == (1, 1)
    assert "voice: 1 decrypted, 1 failed" in capsys.readouterr().out


def test_export_voice_creates_output_directory(app_context, tmp_path):
    voice_dir = tmp_path / "voice_messages"
    voice_dir.mkdir()
    (voice_dir / "good.enc").write_bytes(app_context.fernet.encrypt(b"ok"))
    out_dir = tmp_path / "missing" / "voice_decrypted"

    export.export_voice(voice_dir, out_dir, app_context.fernet)

    assert out_dir.is_dir()


def test_main_integration_end_to_end(app_context, tmp_path, monkeypatch):
    def fail_if_called():
        raise AssertionError("load_dotenv should not run when environ is explicit")

    _insert_encrypted_row(app_context, nickname="ExportNick", timestamp="2025-01-01 12:00:00")
    voice_dir = tmp_path / "voice_messages"
    voice_dir.mkdir()
    (voice_dir / "VoiceNick.enc").write_bytes(app_context.fernet.encrypt(b"voice"))
    out_csv = tmp_path / "out.csv"
    monkeypatch.setattr(export.config, "load_dotenv", fail_if_called)

    result = export.main(
        ["--out", str(out_csv)],
        environ={
            "ENCRYPTION_KEY": app_context.config.encryption_key,
            "UKRAINABILITY_STORAGE_DIR": str(tmp_path),
        },
    )

    assert result is None
    assert _read_csv(out_csv)[0]["nickname"] == "ExportNick"
    assert (tmp_path / "voice_decrypted" / "VoiceNick.ogg").read_bytes() == b"voice"


def test_main_missing_key_raises(tmp_path):
    with pytest.raises(ValueError, match="Missing required configuration: ENCRYPTION_KEY"):
        export.main(
            ["--out", str(tmp_path / "out.csv")],
            environ={},
            load_dotenv_file=False,
        )


def test_main_no_voice_skips_voice_export(app_context, tmp_path):
    _insert_encrypted_row(app_context, nickname="ExportNick", timestamp="2025-01-01 12:00:00")
    voice_dir = tmp_path / "voice_messages"
    voice_dir.mkdir()
    (voice_dir / "VoiceNick.enc").write_bytes(app_context.fernet.encrypt(b"voice"))
    out_csv = tmp_path / "out.csv"

    export.main(
        ["--out", str(out_csv), "--no-voice"],
        environ={
            "ENCRYPTION_KEY": app_context.config.encryption_key,
            "UKRAINABILITY_STORAGE_DIR": str(tmp_path),
        },
        load_dotenv_file=False,
    )

    assert out_csv.exists()
    assert not (tmp_path / "voice_decrypted").exists()


def test_load_encryption_keys_supports_rotation():
    active = Fernet.generate_key().decode("ascii")
    retiring = Fernet.generate_key().decode("ascii")

    active_key, retiring_keys = export.load_encryption_keys(
        {"ENCRYPTION_KEYS": f"{active},{retiring}"},
        load_dotenv_file=False,
    )
    fernet = build_fernet(active_key, list(retiring_keys))
    encrypted_with_retiring_key = Fernet(retiring.encode("ascii")).encrypt(b"rotated")

    assert fernet.decrypt(encrypted_with_retiring_key) == b"rotated"


def test_load_encryption_keys_skips_dotenv_when_environ_supplied(monkeypatch):
    encryption_key = Fernet.generate_key().decode("ascii")

    def fail_if_called():
        raise AssertionError("load_dotenv should not run when environ is explicit")

    monkeypatch.setattr(export.config, "load_dotenv", fail_if_called)

    assert export.load_encryption_keys({"ENCRYPTION_KEY": encryption_key}) == (
        encryption_key,
        (),
    )


def test_load_encryption_keys_reads_credentials_file(tmp_path):
    encryption_key = Fernet.generate_key().decode("ascii")
    credentials = tmp_path / "credentials"
    credentials.write_text(f'export ENCRYPTION_KEY="{encryption_key}"\n', encoding="utf-8")

    assert export.load_encryption_keys(
        {"UKRAINABILITY_CREDENTIALS_FILE": str(credentials)},
        load_dotenv_file=False,
    ) == (encryption_key, ())


def test_decrypt_field_passes_through_non_strings(app_context):
    assert export.decrypt_field(app_context.fernet, None) is None
    assert export.decrypt_field(app_context.fernet, "") == ""
    assert export.decrypt_field(app_context.fernet, 5) == 5


def test_decrypt_field_strict_utf8_failure_counted(app_context):
    encrypted = app_context.fernet.encrypt(b"\xff\xfe")

    assert export.decrypt_field(app_context.fernet, encrypted) == export.DECRYPT_FAILED


def test_main_returns_none_on_partial_decrypt_failure(app_context, tmp_path):
    _insert_encrypted_row(app_context, nickname="Good", timestamp="2025-01-01 12:00:00")
    _insert_encrypted_row(app_context, nickname="Bad", timestamp="2025-01-02 12:00:00")
    with sqlite3.connect(app_context.config.db_file) as conn:
        conn.execute("UPDATE responses SET nickname = 'garbage' WHERE id = 2")

    assert (
        export.main(
            ["--out", str(tmp_path / "out.csv"), "--no-voice"],
            environ={
                "ENCRYPTION_KEY": app_context.config.encryption_key,
                "UKRAINABILITY_STORAGE_DIR": str(tmp_path),
            },
            load_dotenv_file=False,
        )
        is None
    )
