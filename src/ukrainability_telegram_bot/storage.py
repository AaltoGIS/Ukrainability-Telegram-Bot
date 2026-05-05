"""SQLite storage helpers used by the bot and tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional


RESPONSE_COLUMNS = (
    "nickname",
    "month_year",
    "latitude",
    "longitude",
    "venue_title",
    "venue_address",
    "enjoyment",
    "purpose_visit",
    "regularity",
    "noticed_changes",
    "changes_detail",
    "wishlist",
    "kremenchuk",
    "description",
    "voice_submitted",
    "age",
    "gender",
    "occupation",
    "income",
    "language",
    "timestamp",
    "visitor_type",
    "duration_visit",
    "accessibility",
    "consent",
)


def initialize_database(db_file: Path) -> None:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname TEXT,
                month_year TEXT,
                latitude TEXT,
                longitude TEXT,
                venue_title TEXT,
                venue_address TEXT,
                enjoyment TEXT,
                purpose_visit TEXT,
                regularity TEXT,
                noticed_changes TEXT,
                changes_detail TEXT,
                wishlist TEXT,
                kremenchuk TEXT,
                description TEXT,
                voice_submitted TEXT,
                age TEXT,
                gender TEXT,
                occupation TEXT,
                income TEXT,
                language TEXT,
                timestamp TEXT,
                visitor_type TEXT,
                duration_visit TEXT,
                accessibility TEXT,
                consent TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_nicknames (
                user_hash TEXT,
                nickname TEXT NOT NULL,
                month_year TEXT,
                PRIMARY KEY (user_hash, month_year)
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nickname ON responses(nickname)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_hash ON user_nicknames(user_hash)")


def save_user_nickname(
    db_file: Path, user_hash: str, nickname: str, month_year: str
) -> None:
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_nicknames (user_hash, nickname, month_year)
            VALUES (?, ?, ?)
            """,
            (user_hash, nickname, month_year),
        )


def get_user_nickname(db_file: Path, user_hash: str, month_year: str) -> Optional[str]:
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
        cursor = conn.execute(
            """
            SELECT nickname FROM user_nicknames
            WHERE user_hash = ? AND month_year = ?
            """,
            (user_hash, month_year),
        )
        row = cursor.fetchone()
    return row[0] if row else None


def get_all_used_nicknames(db_file: Path) -> set[str]:
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
        cursor = conn.execute("SELECT DISTINCT nickname FROM user_nicknames")
        return {row[0] for row in cursor.fetchall()}


ALLOWED_TABLES = {"responses", "user_nicknames"}


def table_columns(db_file: Path, table: str) -> Iterable[str]:
    if table not in ALLOWED_TABLES:
        allowed = ", ".join(sorted(ALLOWED_TABLES))
        raise ValueError(f"Unsupported table name {table!r}; expected one of: {allowed}")

    with sqlite3.connect(db_file, check_same_thread=False) as conn:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        return [row[1] for row in cursor.fetchall()]
