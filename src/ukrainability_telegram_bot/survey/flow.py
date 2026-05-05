"""Survey flow ordering and dependency predicates."""

from __future__ import annotations


FIELD_ORDER = [
    "location",
    "purpose_visit",
    "enjoyment",
    "visitor_type",
    "duration_visit",
    "accessibility",
    "regularity",
    "noticed_changes",
    "changes_detail",
    "wishlist",
    "kremenchuk",
    "description",
    "age",
    "gender",
    "occupation",
    "income",
]

QUESTION_DEPENDENCIES = {
    "regularity": ["noticed_changes", "changes_detail"],
    "noticed_changes": ["changes_detail"],
}


def get_question_dependencies() -> dict[str, list[str]]:
    return dict(QUESTION_DEPENDENCIES)


def requires_follow_up(regularity_response: str) -> bool:
    if not regularity_response:
        return False
    skip_options = [
        "One-time visit",
        "Разове відвідування",
        "Visited before 2022 but not anymore",
        "Відвідував(-ла) до 2022 р., але не зараз",
        "Prefer not to disclose",
        "Надаю перевагу не вказувати",
    ]
    return not any(option in regularity_response for option in skip_options)


def skips_changes_questions(frequency_response: str) -> bool:
    return frequency_response in {
        "I didn't visit this place before the invasion",
        "Не відвідував(ла) це місце до вторгнення",
    }


def requires_changes_detail(changes_response: str) -> bool:
    return changes_response in {
        "Yes, positive changes",
        "Yes, negative changes",
        "Так, позитивні зміни",
        "Так, негативні зміни",
    }
