"""Survey flow ordering and dependency predicates."""

from __future__ import annotations

from ..messages import messages


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

REGULARITY_SKIP_TO_WISHLIST_INDICES = frozenset({4, 5, 6})
FREQUENCY_DID_NOT_VISIT_BEFORE_INDICES = frozenset({3})
NOTICED_CHANGES_DETAIL_REQUIRING_INDICES = frozenset({0, 1})


def get_question_dependencies() -> dict[str, list[str]]:
    return dict(QUESTION_DEPENDENCIES)


def requires_follow_up(regularity_response: str) -> bool:
    if not regularity_response:
        return False
    option_idx = _option_index("regularity", regularity_response)
    if option_idx is None:
        return True
    return option_idx not in REGULARITY_SKIP_TO_WISHLIST_INDICES


def skips_changes_questions(frequency_response: str) -> bool:
    option_idx = _option_index("frequency_change", frequency_response)
    return option_idx in FREQUENCY_DID_NOT_VISIT_BEFORE_INDICES


def requires_changes_detail(changes_response: str) -> bool:
    option_idx = _option_index("noticed_changes", changes_response)
    return option_idx in NOTICED_CHANGES_DETAIL_REQUIRING_INDICES


def _option_index(option_key: str, response: str) -> int | None:
    for language in ("en", "uk"):
        try:
            return messages[language]["options"][option_key].index(response)
        except ValueError:
            continue
    return None
