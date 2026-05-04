import hashlib

from ukrainability_telegram_bot.pseudonym import hash_user_id


def test_hash_user_id_uses_keyed_hmac_not_plain_sha1():
    user_id = 123456789

    hashed = hash_user_id(user_id, "deployment-secret")

    assert len(hashed) == 64
    assert hashed != hashlib.sha1(str(user_id).encode()).hexdigest()
    assert hashed == hash_user_id(user_id, "deployment-secret")
    assert hashed != hash_user_id(user_id, "different-secret")
