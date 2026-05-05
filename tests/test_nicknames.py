import random

import pytest

from ukrainability_telegram_bot.nicknames import generate_unique_nickname


def test_generate_unique_nickname_avoids_existing_value():
    nickname = generate_unique_nickname(
        {"BrightFox07"},
        adjectives=["Bright", "Wise"],
        nouns=["Fox"],
        rng=random.Random(0),
    )

    assert nickname != "BrightFox07"
    assert nickname.startswith(("BrightFox", "WiseFox"))


def test_generate_unique_nickname_fails_when_pool_is_exhausted():
    used = {f"BrightFox{i:02d}" for i in range(100)}

    with pytest.raises(RuntimeError, match="No nickname combinations"):
        generate_unique_nickname(used, adjectives=["Bright"], nouns=["Fox"])
