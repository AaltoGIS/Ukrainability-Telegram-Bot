"""Context-bound survey continuation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import nickname_db, startup
from ..app import AppContext
from ..telegram_io import clear_message_ids
from .questions import (
    accessibility as accessibility_question,
)
from .questions import (
    changes_detail as changes_detail_question,
)
from .questions import (
    confirmation as confirmation_question,
)
from .questions import (
    demographics as demographics_question,
)
from .questions import (
    description as description_question,
)
from .questions import (
    duration as duration_question,
)
from .questions import (
    enjoyment as enjoyment_question,
)
from .questions import (
    frequency as frequency_question,
)
from .questions import (
    kremenchuk as kremenchuk_question,
)
from .questions import (
    location as location_question,
)
from .questions import (
    noticed_changes as noticed_changes_question,
)
from .questions import (
    purpose as purpose_question,
)
from .questions import (
    regularity as regularity_question,
)
from .questions import (
    restart as restart_question,
)
from .questions import (
    visitor_type as visitor_type_question,
)
from .questions import (
    welcome as welcome_question,
)
from .questions import (
    wishlist as wishlist_question,
)


class SurveyActions:
    """Small adapter that binds survey callbacks to one AppContext."""

    def __init__(
        self,
        ctx: AppContext,
        clear_callback_state: Callable[[int], Any] | None = None,
    ) -> None:
        self.ctx = ctx
        self.clear_callback_state = clear_callback_state

    def update_activity_timestamp(self, user_id: int) -> None:
        startup.update_activity_timestamp(self.ctx, user_id)

    def get_user_hash(self, user_id: int) -> str:
        return nickname_db.get_user_hash(self.ctx, user_id)

    def get_user_nickname(self, user_hash: str) -> str | None:
        return nickname_db.get_user_nickname(self.ctx, user_hash)

    def generate_unique_nickname(self) -> str:
        return nickname_db.generate_unique_nickname(self.ctx)

    def save_user_nickname(self, user_hash: str, nickname: str) -> None:
        nickname_db.save_user_nickname(self.ctx, user_hash, nickname)

    def clear_message_ids(self, user_id: int) -> None:
        clear_message_ids(self.ctx, user_id)

    def send_welcome(self, **kwargs: Any) -> None:
        welcome_question.send_welcome(
            self.ctx,
            callbacks=welcome_question.callbacks_from_context(self.ctx, self),
            **kwargs,
        )

    def handle_location_step(self, message: Any) -> None:
        location_question.handle_location_step(
            self.ctx,
            message,
            location_question.callbacks_from_context(self.ctx, self),
        )

    def handle_description(self, message: Any) -> None:
        description_question.handle_description(
            self.ctx,
            message,
            description_question.callbacks_from_context(self.ctx, self),
        )

    def ask_purpose_visit(self, chat_id: int, user_id: int, language: str) -> None:
        purpose_question.ask_purpose_visit(self.ctx, chat_id, user_id, language)

    def ask_enjoyment(self, chat_id: int, user_id: int, language: str) -> None:
        enjoyment_question.ask_enjoyment(self.ctx, chat_id, user_id, language)

    def ask_visitor_type(self, chat_id: int, user_id: int, language: str) -> None:
        visitor_type_question.ask_visitor_type(self.ctx, chat_id, user_id, language)

    def ask_duration(self, chat_id: int, user_id: int, language: str) -> None:
        duration_question.ask_duration(self.ctx, chat_id, user_id, language)

    def ask_accessibility(self, chat_id: int, user_id: int, language: str) -> None:
        accessibility_question.ask_accessibility(self.ctx, chat_id, user_id, language)

    def ask_regularity(self, chat_id: int, user_id: int, language: str) -> None:
        regularity_question.ask_regularity(self.ctx, chat_id, user_id, language)

    def ask_frequency_change(self, chat_id: int, user_id: int, language: str) -> None:
        frequency_question.ask_frequency_change(self.ctx, chat_id, user_id, language)

    def ask_noticed_changes(self, chat_id: int, user_id: int, language: str) -> None:
        noticed_changes_question.ask_noticed_changes(self.ctx, chat_id, user_id, language)

    def ask_changes_detail(self, chat_id: int, user_id: int, language: str) -> None:
        changes_detail_question.ask_changes_detail(self.ctx, chat_id, user_id, language)

    def ask_wishlist(self, chat_id: int, user_id: int, language: str) -> None:
        wishlist_question.ask_wishlist(self.ctx, chat_id, user_id, language)

    def ask_age(self, chat_id: int, user_id: int, language: str) -> None:
        demographics_question.ask_age(
            self.ctx,
            chat_id,
            user_id,
            language,
            demographics_question.callbacks_from_context(self.ctx, self),
        )

    def ask_gender(self, chat_id: int, user_id: int, language: str) -> None:
        demographics_question.ask_gender(
            self.ctx,
            chat_id,
            user_id,
            language,
            demographics_question.callbacks_from_context(self.ctx, self),
        )

    def ask_occupation(self, chat_id: int, user_id: int, language: str) -> None:
        demographics_question.ask_occupation(
            self.ctx,
            chat_id,
            user_id,
            language,
            demographics_question.callbacks_from_context(self.ctx, self),
        )

    def ask_income(self, chat_id: int, user_id: int, language: str) -> None:
        demographics_question.ask_income(
            self.ctx,
            chat_id,
            user_id,
            language,
            demographics_question.callbacks_from_context(self.ctx, self),
        )

    def ask_kremenchuk(self, chat_id: int, user_id: int, language: str) -> None:
        kremenchuk_question.ask_kremenchuk(self.ctx, chat_id, user_id, language)

    def ask_description(self, chat_id: int, user_id: int, language: str) -> None:
        description_question.ask_description(
            self.ctx,
            chat_id,
            user_id,
            language,
            description_question.callbacks_from_context(self.ctx, self),
        )

    def ask_final_confirmation(self, chat_id: int, user_id: int, language: str) -> None:
        confirmation_question.ask_final_confirmation(self.ctx, chat_id, user_id, language)

    def ask_continue_or_stop(self, chat_id: int, user_id: int, language: str) -> None:
        restart_question.ask_continue_or_stop(self.ctx, chat_id, user_id, language)

    def save_data_and_restart(
        self,
        chat_id: int,
        user_id: int,
        language: str,
        restart_survey: bool = False,
    ) -> bool:
        return restart_question.save_data_and_restart(
            self.ctx,
            chat_id,
            user_id,
            language,
            restart_survey,
            restart_question.callbacks_from_context(self.ctx, self),
        )

    def get_anonymous_id(self, user_id: int) -> str:
        return nickname_db.get_user_hash(self.ctx, user_id)

    def clear_dependent_fields(
        self,
        user_id: int,
        field: str,
        old_value: Any,
        new_value: Any,
    ) -> list[str]:
        return confirmation_question.clear_dependent_fields(
            self.ctx,
            user_id,
            field,
            old_value,
            new_value,
            self.get_anonymous_id,
        )
