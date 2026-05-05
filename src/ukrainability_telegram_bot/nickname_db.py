"""Nickname persistence helpers bound to an application context."""

from __future__ import annotations

import datetime
import random

from .app import AppContext
from . import nicknames
from .pseudonym import hash_user_id
from .storage import get_all_used_nicknames as fetch_all_used_nicknames
from .storage import get_latest_user_nickname as fetch_latest_user_nickname
from .storage import save_user_nickname as persist_user_nickname


def get_user_hash(ctx: AppContext, user_id: int) -> str:
    return hash_user_id(user_id, ctx.config.user_hash_salt)


def get_user_nickname(ctx: AppContext, user_hash: str) -> str | None:
    return fetch_latest_user_nickname(ctx.config.db_file, user_hash)


def get_all_used_nicknames(ctx: AppContext) -> set[str]:
    return fetch_all_used_nicknames(ctx.config.db_file)


def save_user_nickname(
    ctx: AppContext,
    user_hash: str,
    nickname: str,
    *,
    month_year: str | None = None,
) -> None:
    if month_year is None:
        month_year = datetime.datetime.now().strftime("%Y-%m")
    persist_user_nickname(ctx.config.db_file, user_hash, nickname, month_year)


def generate_unique_nickname(
    ctx: AppContext,
    *,
    rng: random.Random | None = None,
) -> str:
    try:
        return nicknames.generate_unique_nickname(
            get_all_used_nicknames(ctx),
            adjectives=nicknames.LEGACY_ADJECTIVES,
            nouns=nicknames.LEGACY_NOUNS,
            separator=" ",
            number_range=1000,
            number_width=0,
            rng=rng,
        )
    except RuntimeError as exc:
        raise Exception("All nickname combinations have been used.") from exc
