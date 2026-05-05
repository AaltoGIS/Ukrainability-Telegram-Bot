from ukrainability_telegram_bot.messages import messages
from ukrainability_telegram_bot.survey import flow


def test_requires_follow_up_uses_regularity_option_indices():
    regularity_options = messages["en"]["options"]["regularity"]

    assert flow.requires_follow_up(regularity_options[0]) is True
    assert flow.requires_follow_up(regularity_options[4]) is False
    assert flow.requires_follow_up(regularity_options[5]) is False
    assert flow.requires_follow_up(regularity_options[6]) is False


def test_skips_changes_questions_uses_frequency_option_indices():
    frequency_options = messages["en"]["options"]["frequency_change"]

    assert flow.skips_changes_questions(frequency_options[0]) is False
    assert flow.skips_changes_questions(frequency_options[3]) is True


def test_requires_changes_detail_uses_noticed_changes_option_indices():
    noticed_changes_options = messages["uk"]["options"]["noticed_changes"]

    assert flow.requires_changes_detail(noticed_changes_options[0]) is True
    assert flow.requires_changes_detail(noticed_changes_options[1]) is True
    assert flow.requires_changes_detail(noticed_changes_options[2]) is False
