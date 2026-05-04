from ukrainability_telegram_bot.state import (
    UserState,
    dependent_fields,
    requires_changes_detail,
    requires_follow_up,
    skips_changes_questions,
)


def test_user_state_stores_copies_and_clears_keys():
    state = UserState()
    state.set(42, "purpose_visit", ["Walking"])

    snapshot = state.get(42)
    snapshot["purpose_visit"].append("Mutated outside")

    assert state.get(42, "purpose_visit") == ["Walking"]

    state.clear_keys(42, ["purpose_visit"])
    assert state.get(42, "purpose_visit") is None


def test_survey_dependency_helpers_cover_branching_logic():
    assert dependent_fields("regularity") == [
        "frequency_change",
        "noticed_changes",
        "changes_detail",
    ]
    assert requires_follow_up("I visit this place regularly")
    assert skips_changes_questions("This is my first time here")
    assert requires_changes_detail("Yes, changes for the better")
    assert not requires_changes_detail("No changes")
