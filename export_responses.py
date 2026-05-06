"""Decrypt the Ukrainability responses database and voice files to plaintext.

Reads ENCRYPTION_KEY (or comma-separated ENCRYPTION_KEYS for rotated keys)
from the environment. Writes a CSV of decrypted responses and  a directory of decrypted voice messages.
"""
from __future__ import annotations
import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from ukrainability_telegram_bot import storage


def build_fernet() -> MultiFernet:
    keys_env = os.environ.get("ENCRYPTION_KEYS") or os.environ.get("ENCRYPTION_KEY")
    if not keys_env:
        sys.exit("Set ENCRYPTION_KEY or ENCRYPTION_KEYS before running.")
    return MultiFernet([Fernet(k.strip().encode()) for k in keys_env.split(",")])


def decrypt_field(fernet: MultiFernet, value):
    if value is None or value == "":
        return value
    if not isinstance(value, (str, bytes)):  # ints, floats — pass through
        return value
    if isinstance(value, str):
        value = value.encode()
    try:
        return fernet.decrypt(value).decode("utf-8", errors="replace")
    except InvalidToken:
        return "<decrypt-failed>"


def export_responses(db_path: Path, out_csv: Path, fernet: MultiFernet) -> int:
    plaintext_cols = set(storage.PLAINTEXT_COLUMNS)
    encrypted_cols = set(storage.RESPONSE_COLUMNS) - plaintext_cols
    drop_cols = {"user_hash"}

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.execute("SELECT * FROM responses ORDER BY timestamp")
    columns = [d[0] for d in cur.description]
    rows = cur.fetchall()
    con.close()

    out_columns = [c for c in columns if c not in drop_cols]

    n_fail = 0
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(out_columns)
        for r in rows:
            out = []
            for col in out_columns:
                if col in encrypted_cols:
                    dec = decrypt_field(fernet, r[col])
                    if dec == "<decrypt-failed>":
                        n_fail += 1
                    out.append(dec)
                else:
                    out.append(r[col])
            w.writerow(out)
    print(f"responses: {len(rows)} rows -> {out_csv}"
          + (f" ({n_fail} failed fields)" if n_fail else ""))
    return n_fail

def export_voice(voice_dir: Path, out_dir: Path, fernet: MultiFernet) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = bad = 0
    for enc in voice_dir.glob("*.enc"):
        try:
            (out_dir / enc.stem).with_suffix(".ogg").write_bytes(
                fernet.decrypt(enc.read_bytes())
            )
            ok += 1
        except InvalidToken:
            bad += 1
    print(f"voice: {ok} decrypted, {bad} failed -> {out_dir}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--voice-dir", type=Path, default=None)
    p.add_argument("--voice-out", type=Path, default=None)
    p.add_argument("--no-voice", action="store_true",
                   help="Skip voice decryption even if voice_messages/ exists.")
    args = p.parse_args()

    fernet = build_fernet()
    export_responses(args.db, args.out, fernet)

    voice_dir = args.voice_dir or (args.db.parent / "voice_messages")
    voice_out = args.voice_out or args.out.with_name("voice_decrypted")
    if not args.no_voice and voice_dir.is_dir():
        export_voice(voice_dir, voice_out, fernet)


if __name__ == "__main__":
    main()
