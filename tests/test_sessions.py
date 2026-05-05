from ukrainability_telegram_bot.sessions import SessionStore


def test_session_store_remove_data_returns_value_or_default():
    store = SessionStore()
    store.set_data(1, "language", "en")

    assert store.remove_data(1, "language") == "en"
    assert store.remove_data(1, "language", "missing") == "missing"


def test_session_store_snapshots_are_deep_copies():
    store = SessionStore()
    store.set_data(1, "nested", {"items": ["a"]})
    store.set_profile(1, "profile_nested", {"items": ["b"]})

    data_snapshot = store.snapshot(1)
    profile_snapshot = store.profile_snapshot(1)
    data_snapshot["nested"]["items"].append("changed")
    profile_snapshot["profile_nested"]["items"].append("changed")

    assert store.get_data(1, "nested") == {"items": ["a"]}
    assert store.get_profile(1, "profile_nested") == {"items": ["b"]}


def test_session_store_message_id_round_trip():
    store = SessionStore()

    store.register_message_id(1, "purpose_visit", 42)

    assert store.get_message_id(1, "purpose_visit") == 42
    store.clear_message_ids(1)
    assert store.get_message_id(1, "purpose_visit") is None


def test_session_store_evict_inactive_keeps_recent_users(monkeypatch):
    store = SessionStore()
    monkeypatch.setattr("ukrainability_telegram_bot.sessions.time.time", lambda: 5_000.0)
    store.set_data(1, "last_activity_time", 100.0)
    store.set_data(2, "last_activity_time", 4_950.0)

    removed = store.evict_inactive(hours=1)

    assert removed == [1]
    assert 1 not in store.data
    assert 2 in store.data


def test_session_store_update_activity_uses_current_time(monkeypatch):
    store = SessionStore()
    monkeypatch.setattr("ukrainability_telegram_bot.sessions.time.time", lambda: 123.0)

    store.update_activity(1)

    assert store.get_data(1, "last_activity_time") == 123.0


def test_session_store_lock_is_reentrant():
    store = SessionStore()

    with store.locked():
        store.set_data(1, "language", "uk")
        with store.locked():
            store.set_profile(1, "consent", True)

    assert store.get_data(1, "language") == "uk"
    assert store.get_profile(1, "consent") is True
