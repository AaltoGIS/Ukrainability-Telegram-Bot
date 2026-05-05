import random

from ukrainability_telegram_bot import nickname_db
from ukrainability_telegram_bot.pseudonym import hash_user_id


class FixedRandom:
    def choice(self, sequence):
        return sequence[0]

    def randint(self, start, end):
        return start


def test_get_user_hash_uses_configured_salt(app_context):
    assert nickname_db.get_user_hash(app_context, 123) == hash_user_id(
        123, app_context.config.user_hash_salt
    )


def test_nickname_persistence_returns_latest_month(app_context):
    user_hash = "user-hash"

    nickname_db.save_user_nickname(app_context, user_hash, "Bright Fox 0", month_year="2026-05")
    nickname_db.save_user_nickname(app_context, user_hash, "Wise Wolf 1", month_year="2026-06")

    assert nickname_db.get_user_nickname(app_context, user_hash) == "Wise Wolf 1"
    assert nickname_db.get_all_used_nicknames(app_context) == {
        "Bright Fox 0",
        "Wise Wolf 1",
    }


def test_generate_unique_nickname_preserves_classic_format(app_context):
    nickname = nickname_db.generate_unique_nickname(app_context, rng=FixedRandom())

    assert nickname == "Agile Antelope 0"


def test_generate_unique_nickname_avoids_existing_classic_value(app_context):
    nickname_db.save_user_nickname(
        app_context, "user-hash", "Agile Antelope 0", month_year="2026-05"
    )

    nickname = nickname_db.generate_unique_nickname(
        app_context,
        rng=random.Random(1),
    )

    assert nickname != "Agile Antelope 0"
