"""Nickname generation helpers."""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence

from .constants import ADJECTIVES, NOUNS


def generate_unique_nickname(
    used_nicknames: Iterable[str],
    *,
    adjectives: Sequence[str] = ADJECTIVES,
    nouns: Sequence[str] = NOUNS,
    rng: random.Random | None = None,
) -> str:
    randomizer = rng or random
    used = set(used_nicknames)
    total = len(adjectives) * len(nouns) * 100
    if len(used) >= total:
        raise RuntimeError("No nickname combinations are available")

    while True:
        nickname = (
            f"{randomizer.choice(adjectives)}"
            f"{randomizer.choice(nouns)}"
            f"{randomizer.randint(0, 99):02d}"
        )
        if nickname not in used:
            return nickname
