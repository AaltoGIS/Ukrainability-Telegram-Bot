import importlib
import sys
from collections import Counter

from ukrainability_telegram_bot import runtime


EXPECTED_HANDLER_NAMES = {
    "send_welcome",
    "handle_restart",
    "handle_language_selection",
    "handle_consent",
    "handle_post_consent_continue",
    "handle_purpose_selection",
    "handle_enjoyment_selection",
    "confirm_enjoyment",
    "handle_visitor_type_selection",
    "handle_duration_selection",
    "confirm_duration",
    "handle_accessibility_selection",
    "handle_regularity_selection",
    "confirm_regularity",
    "handle_frequency_change_selection",
    "handle_noticed_changes_selection",
    "confirm_noticed_changes",
    "handle_changes_detail_selection",
    "handle_wishlist_selection",
    "handle_age_selection",
    "confirm_age",
    "handle_gender_selection",
    "confirm_gender",
    "handle_occupation_selection",
    "confirm_occupation",
    "handle_income_selection",
    "confirm_income",
    "handle_kremenchuk_selection",
    "handle_description_skip",
    "handle_final_confirmation_choice",
    "handle_modification_selection_callback",
    "handle_continue_or_stop_selection",
    "handle_text_messages",
}


def _load_legacy_with_fresh_registry(monkeypatch):
    module_name = "ukrainability_telegram_bot._legacy"
    previous_module = sys.modules.pop(module_name, None)
    registry = runtime.HandlerRegistry()
    monkeypatch.setattr(runtime, "bot", registry)
    try:
        importlib.import_module(module_name)
    finally:
        sys.modules.pop(module_name, None)
        if previous_module is not None:
            sys.modules[module_name] = previous_module
    return registry


def test_handlers_registered_once(monkeypatch):
    registry = _load_legacy_with_fresh_registry(monkeypatch)
    counts = Counter(
        (handler_name, handler_func.__name__)
        for handler_name, _args, _kwargs, handler_func in registry._handlers
    )

    duplicates = {
        handler: count
        for handler, count in counts.items()
        if count > 1
    }
    assert duplicates == {}


def test_no_callbacks_lost(monkeypatch):
    registry = _load_legacy_with_fresh_registry(monkeypatch)
    registered_names = {
        handler_func.__name__
        for _handler_name, _args, _kwargs, handler_func in registry._handlers
    }

    assert EXPECTED_HANDLER_NAMES <= registered_names
