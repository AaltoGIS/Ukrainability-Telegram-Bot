"""Runtime Telegram bot implementation.

This module intentionally preserves the legacy survey behavior while moving
startup work behind `configure_runtime()` and `run()`.
"""

# Imports and configuration
import logging

import telebot
from telebot import types

from .messages import messages
from . import nickname_db
from . import startup
from . import runtime as runtime_module
from .runtime import flow_logger
from .survey.questions import consent as consent_question
from .survey.questions import description as description_question
from .survey.questions import accessibility as accessibility_question
from .survey.questions import changes_detail as changes_detail_question
from .survey.questions import confirmation as confirmation_question
from .survey.questions import demographics as demographics_question
from .survey.questions import duration as duration_question
from .survey.questions import enjoyment as enjoyment_question
from .survey.questions import frequency as frequency_question
from .survey.questions import kremenchuk as kremenchuk_question
from .survey.questions import language as language_question
from .survey.questions import location as location_question
from .survey.questions import noticed_changes as noticed_changes_question
from .survey.questions import purpose as purpose_question
from .survey.questions import regularity as regularity_question
from .survey.questions import restart as restart_question
from .survey.questions import visitor_type as visitor_type_question
from .survey.questions import welcome as welcome_question
from .survey.questions import wishlist as wishlist_question
from .survey.questions.accessibility import AccessibilityCallbacks
from .survey.questions.changes_detail import ChangesDetailCallbacks
from .survey.questions.confirmation import ConfirmationCallbacks
from .survey.questions.demographics import DemographicsCallbacks
from .survey.questions.duration import DurationCallbacks
from .survey.questions.enjoyment import EnjoymentCallbacks
from .survey.questions.frequency import FrequencyCallbacks
from .survey.questions.kremenchuk import KremenchukCallbacks
from .survey.questions.noticed_changes import NoticedChangesCallbacks
from .survey.questions.regularity import RegularityCallbacks
from .survey.questions.restart import RestartCallbacks
from .survey.questions.visitor_type import VisitorTypeCallbacks
from .survey.questions.wishlist import WishlistCallbacks
from .survey.questions.base import (
    ConsentCallbacks,
    DescriptionCallbacks,
    PurposeCallbacks,
)
from . import telegram_io as telegram_io_module
from .telegram_io import (
    callback_index,
    callback_suffix,
    escape_html,
    telegram_retry_after,
)


def configure_runtime(config):
    """Configure global legacy runtime objects for one bot process."""

    return runtime_module.configure_runtime(config)


# URLs for privacy notices and participant information





# Messages dictionary




class LegacyBridge:
    """Bind the remaining legacy survey wrappers to one AppContext."""

    def __init__(self, ctx):
        self.ctx = ctx

    def _user_data(self):
        return self.ctx.sessions.data

    def _user_profiles(self):
        return self.ctx.sessions.profiles

    def _session_lock(self):
        return self.ctx.sessions.lock

    def get_user_hash(self, user_id):
        return nickname_db.get_user_hash(self.ctx, user_id)

    def register_message_id(self, user_id, message_type, message_id):
        return telegram_io_module.register_message_id(self.ctx, user_id, message_type, message_id)

    def get_message_id(self, user_id, message_type):
        return telegram_io_module.get_message_id(self.ctx, user_id, message_type)

    def clear_message_ids(self, user_id):
        return telegram_io_module.clear_message_ids(self.ctx, user_id)

    def send_keyboard_message(self, *args, **kwargs):
        return telegram_io_module.send_keyboard_message(self.ctx, *args, **kwargs)

    def edit_keyboard(self, *args, **kwargs):
        return telegram_io_module.edit_keyboard(self.ctx, *args, **kwargs)

    def safe_send_message(self, *args, **kwargs):
        return telegram_io_module.safe_send_message(self.ctx, *args, **kwargs)

    def send_next_step_prompt(self, *args, **kwargs):
        return telegram_io_module.send_next_step_prompt(self.ctx, *args, **kwargs)

    def handle_callback_error(self, *args, **kwargs):
        return telegram_io_module.handle_callback_error(
            self.ctx,
            *args,
            clear_callback_state=self.clear_callback_state,
            **kwargs,
        )

    def safe_answer_callback(self, *args, **kwargs):
        return telegram_io_module.safe_answer_callback(self.ctx, *args, **kwargs)

    def hide_keyboard(self, *args, **kwargs):
        return telegram_io_module.hide_keyboard(self.ctx, *args, **kwargs)

    # Helper functions
    def generate_unique_nickname(self):
        return nickname_db.generate_unique_nickname(self.ctx)


    def get_all_used_nicknames(self):
        return nickname_db.get_all_used_nicknames(self.ctx)


    def create_inline_keyboard(self, options, prefix, single_select=False):
        """
        Creates an InlineKeyboardMarkup with buttons based on the provided options.

        Args:
            options (list): List of option strings.
            prefix (str): Prefix for callback_data to identify the question.
            single_select (bool): If True, only one selection is allowed.

        Returns:
            InlineKeyboardMarkup: The generated inline keyboard.
        """
        try:
            inline_kb = types.InlineKeyboardMarkup(
                row_width=1 if single_select else 2)
            buttons = [
                types.InlineKeyboardButton(text=option, callback_data=f"{prefix}_{idx}")
                for idx, option in enumerate(options)
            ]
            if single_select:
                # For single selection, no "Done" button is necessary
                inline_kb.add(*buttons)
            else:
                # For multiple selections, add a "Done" button
                done_text = "Done" if prefix != 'modify' else "Продовжити"
                done_button = types.InlineKeyboardButton(
                    text=done_text, callback_data=f"{prefix}_done")
                inline_kb.add(*buttons, done_button)
            return inline_kb
        except Exception as e:
            logging.exception(f"Error in create_inline_keyboard: {e}")
            # Return an empty keyboard to prevent further errors
            return types.InlineKeyboardMarkup()


    def get_user_nickname(self, user_hash):
        return nickname_db.get_user_nickname(self.ctx, user_hash)

    def save_user_nickname(self, user_hash, nickname):
        nickname_db.save_user_nickname(self.ctx, user_hash, nickname)


    # Add this function to the top of your script to help with error handling


    def safe_get_language(self, user_id):
        """
        Safely tries to get user's language preference with fallbacks.

        Args:
            user_id (int): The user's ID

        Returns:
            str: Language code ('en' or 'uk') with fallback to 'en'
        """
        try:
            # Try self._user_data() first
            if user_id in self._user_data() and 'language' in self._user_data()[user_id]:
                return self._user_data()[user_id]['language']

            # Try self._user_profiles() next
            if user_id in self._user_profiles() and 'language' in self._user_profiles()[user_id]:
                return self._user_profiles()[user_id]['language']

            # Default fallback
            return 'en'
        except Exception:
            # Ultimate fallback
            return 'en'


    def clear_callback_state(self, user_id):
        """Clear transient callback state for a user after a handler error."""

        with self._session_lock():
            if user_id in self._user_data():
                keys_to_remove = []
                for key in self._user_data()[user_id]:
                    if (key.startswith('temp_') or
                        key == 'awaiting_multiple_select' or
                        key == 'current_question' or
                        key == 'modifying' or
                        key == 'modifying_field'):
                        keys_to_remove.append(key)

                for key in keys_to_remove:
                    self._user_data()[user_id].pop(key, None)


    def ensure_session_valid(self, call):
        """
        Ensures a user has a valid session with language set.

        Args:
            call: The callback query object

        Returns:
            tuple: (is_valid, language) - is_valid is True if session is valid, False otherwise
        """
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        # Ensure user exists in self._user_data() and has language
        if user_id not in self._user_data() or 'language' not in self._user_data()[user_id]:
            # Try to get language from self._user_profiles()
            if user_id in self._user_profiles() and 'language' in self._user_profiles()[user_id]:
                # Initialize user data if needed
                if user_id not in self._user_data():
                    self._user_data()[user_id] = {}
                self._user_data()[user_id]['language'] = self._user_profiles()[user_id]['language']
                return True, self._user_data()[user_id]['language']
            else:
                # Cannot proceed without language
                try:
                    self.ctx.bot.answer_callback_query(
                        call.id, messages["en"]["start_again"])
                    self.ctx.bot.send_message(
                        chat_id,
                        messages["en"]["session_expired"])
                except Exception:
                    pass
                return False, 'en'
        else:
            return True, self._user_data()[user_id]['language']


    def cleanup_stale_sessions(self, hours_inactive=48):
        """
        Remove stale user sessions to free memory.
        This should be called periodically to prevent memory leaks.

        Args:
            hours_inactive (int): Number of hours of inactivity before cleaning up
        """
        try:
            flow_logger.info(
                f"Starting stale session cleanup, removing sessions inactive for {hours_inactive} hours")
            removed_users = self.ctx.sessions.evict_inactive(hours_inactive)
            for user_id in removed_users:
                flow_logger.info(f"Removed stale session for user {user_id}")

            flow_logger.info(
                f"Stale session cleanup complete. Removed {len(removed_users)} sessions.")
        except Exception as e:
            flow_logger.error(f"Error in stale session cleanup: {e}")


    def update_activity_timestamp(self, user_id):
        startup.update_activity_timestamp(self.ctx, user_id)


    def register_handlers(self):
        """Register legacy wrapper entry points against a configured TeleBot."""

        bot_instance = self.ctx.bot
        bot_instance.callback_query_handler(func=lambda call: call.data == 'restart')(
            self.handle_restart
        )
        bot_instance.message_handler(commands=['start'])(self.send_welcome)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('language_')
        )(self.handle_language_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('consent_')
        )(self.handle_consent)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == 'post_consent_continue'
        )(self.handle_post_consent_continue)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('purpose_')
        )(self.handle_purpose_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('enjoyment_')
        )(self.handle_enjoyment_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_enjoyment"
        )(self.confirm_enjoyment)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('visitor_')
        )(self.handle_visitor_type_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('duration_')
        )(self.handle_duration_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_duration"
        )(self.confirm_duration)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('accessibility_')
        )(self.handle_accessibility_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('regularity_')
        )(self.handle_regularity_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_regularity"
        )(self.confirm_regularity)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('frequency_change_')
        )(self.handle_frequency_change_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('noticed_changes_')
        )(self.handle_noticed_changes_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_noticed_changes"
        )(self.confirm_noticed_changes)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('changes_detail_')
        )(self.handle_changes_detail_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('wishlist_')
        )(self.handle_wishlist_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('age_')
        )(self.handle_age_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_age"
        )(self.confirm_age)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('gender_')
        )(self.handle_gender_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_gender"
        )(self.confirm_gender)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('occupation_')
        )(self.handle_occupation_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_occupation"
        )(self.confirm_occupation)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('income_')
        )(self.handle_income_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == "confirm_income"
        )(self.confirm_income)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('kremenchuk_')
        )(self.handle_kremenchuk_selection)
        bot_instance.callback_query_handler(
            func=lambda call: call.data == 'description_skip'
        )(self.handle_description_skip)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('final_')
        )(self.handle_final_confirmation_choice)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('modify_')
            or call.data == 'modification_done'
        )(self.handle_modification_selection_callback)
        bot_instance.callback_query_handler(
            func=lambda call: call.data.startswith('continue_')
        )(self.handle_continue_or_stop_selection)
        bot_instance.message_handler(func=lambda m: True, content_types=['text'])(
            self.handle_text_messages
        )

    # Start, language, and location handlers
    def _welcome_callbacks(self):
        return welcome_question.WelcomeCallbacks(
            update_activity_timestamp=self.update_activity_timestamp,
            get_user_hash=self.get_user_hash,
            get_user_nickname=self.get_user_nickname,
            generate_unique_nickname=self.generate_unique_nickname,
            save_user_nickname=self.save_user_nickname,
            send_welcome=self.send_welcome,
        )


    def _language_callbacks(self):
        return language_question.LanguageCallbacks(
            location_handler=self.handle_location_step,
        )


    def _location_callbacks(self):
        return location_question.LocationCallbacks(
            update_activity_timestamp=self.update_activity_timestamp,
            send_welcome=self.send_welcome,
            ask_purpose_visit=self.ask_purpose_visit,
            location_handler=self.handle_location_step,
        )


    def handle_restart(self, call):
        welcome_question.handle_restart(self.ctx, call, self._welcome_callbacks())


    def send_welcome(self, message=None, chat_id=None, user_id=None, start_param=None):
        welcome_question.send_welcome(
            self.ctx,
            callbacks=self._welcome_callbacks(),
            message=message,
            chat_id=chat_id,
            user_id=user_id,
            start_param=start_param,
        )


    def handle_language_selection(self, call):
        language_question.handle_language_selection(self.ctx, call, self._language_callbacks())

    def handle_consent(self, call):
        consent_question.handle_consent(self.ctx, call)


    def handle_post_consent_continue(self, call):
        consent_question.handle_post_consent_continue(
            self.ctx,
            call,
            ConsentCallbacks(location_handler=self.handle_location_step),
        )




    def handle_location_step(self, message):
        location_question.handle_location_step(self.ctx, message, self._location_callbacks())



    # Purpose visit handler
    # Updated ask_purpose_visit function
    def ask_purpose_visit(self, chat_id, user_id, language):
        purpose_question.ask_purpose_visit(self.ctx, chat_id, user_id, language)


    # Updated handle_purpose_selection function
    def handle_purpose_selection(self, call):
        purpose_question.handle_purpose_selection(
            self.ctx,
            call,
            PurposeCallbacks(
                ask_enjoyment=self.ask_enjoyment,
                ask_final_confirmation=self.ask_final_confirmation,
                clear_callback_state=self.clear_callback_state,
            ),
        )


    # Updated update_purpose_selection_keyboard function
    def update_purpose_selection_keyboard(self, message, user_id, language):
        purpose_question.update_purpose_selection_keyboard(
            self.ctx, message, user_id, language
        )



    # Enjoyment and visitor type handlers
    def ask_enjoyment(self, chat_id, user_id, language, remove_keyboard=False):
        enjoyment_question.ask_enjoyment(
            self.ctx, chat_id, user_id, language, remove_keyboard=remove_keyboard
        )


    def handle_enjoyment_selection(self, call):
        enjoyment_question.handle_enjoyment_selection(
            self.ctx,
            call,
            EnjoymentCallbacks(
                ask_visitor_type=self.ask_visitor_type,
                ask_final_confirmation=self.ask_final_confirmation,
            ),
        )


    def confirm_enjoyment(self, call):
        enjoyment_question.confirm_enjoyment(
            self.ctx,
            call,
            EnjoymentCallbacks(
                ask_visitor_type=self.ask_visitor_type,
                ask_final_confirmation=self.ask_final_confirmation,
            ),
        )


    # Visitor type handler modifications
    def ask_visitor_type(self, chat_id, user_id, language):
        visitor_type_question.ask_visitor_type(self.ctx, chat_id, user_id, language)


    def handle_visitor_type_selection(self, call):
        visitor_type_question.handle_visitor_type_selection(
            self.ctx,
            call,
            VisitorTypeCallbacks(
                ask_duration=self.ask_duration,
                ask_final_confirmation=self.ask_final_confirmation,
            ),
        )


    def update_visitor_type_keyboard(self, message, user_id, language, options):
        visitor_type_question.update_visitor_type_keyboard(
            self.ctx, message, user_id, language, options
        )



    # Duration and accessibility handlers
    def ask_duration(self, chat_id, user_id, language):
        duration_question.ask_duration(self.ctx, chat_id, user_id, language)


    def handle_duration_selection(self, call):
        duration_question.handle_duration_selection(self.ctx, call)


    def confirm_duration(self, call):
        duration_question.confirm_duration(
            self.ctx,
            call,
            DurationCallbacks(
                ask_accessibility=self.ask_accessibility,
                ask_final_confirmation=self.ask_final_confirmation,
            ),
        )


    # Accessibility handler modifications
    def ask_accessibility(self, chat_id, user_id, language):
        accessibility_question.ask_accessibility(self.ctx, chat_id, user_id, language)


    def handle_accessibility_selection(self, call):
        accessibility_question.handle_accessibility_selection(
            self.ctx,
            call,
            AccessibilityCallbacks(
                ask_regularity=self.ask_regularity,
                ask_final_confirmation=self.ask_final_confirmation,
            ),
        )


    def update_accessibility_keyboard(self, message, user_id, language, options):
        accessibility_question.update_accessibility_keyboard(
            self.ctx, message, user_id, language, options
        )



    def ask_regularity(self, chat_id, user_id, language):
        regularity_question.ask_regularity(self.ctx, chat_id, user_id, language)


    def handle_regularity_selection(self, call):
        regularity_question.handle_regularity_selection(self.ctx, call)


    def confirm_regularity(self, call):
        regularity_question.confirm_regularity(
            self.ctx,
            call,
            RegularityCallbacks(
                ask_noticed_changes=self.ask_noticed_changes,
                ask_wishlist=self.ask_wishlist,
                ask_final_confirmation=self.ask_final_confirmation,
                clear_dependent_fields=self.clear_dependent_fields,
                get_anonymous_id=self.get_anonymous_id,
            ),
        )


    def ask_frequency_change(self, chat_id, user_id, language):
        frequency_question.ask_frequency_change(self.ctx, chat_id, user_id, language)


    def handle_frequency_change_selection(self, call):
        frequency_question.handle_frequency_change_selection(
            self.ctx,
            call,
            FrequencyCallbacks(
                ask_noticed_changes=self.ask_noticed_changes,
                ask_wishlist=self.ask_wishlist,
                ask_final_confirmation=self.ask_final_confirmation,
                clear_dependent_fields=self.clear_dependent_fields,
                get_anonymous_id=self.get_anonymous_id,
            ),
        )


    # Noticed changes and changes details handlers
    def ask_noticed_changes(self, chat_id, user_id, language):
        noticed_changes_question.ask_noticed_changes(self.ctx, chat_id, user_id, language)


    def handle_noticed_changes_selection(self, call):
        noticed_changes_question.handle_noticed_changes_selection(self.ctx, call)


    def confirm_noticed_changes(self, call):
        noticed_changes_question.confirm_noticed_changes(
            self.ctx,
            call,
            NoticedChangesCallbacks(
                ask_changes_detail=self.ask_changes_detail,
                ask_wishlist=self.ask_wishlist,
                ask_final_confirmation=self.ask_final_confirmation,
                clear_dependent_fields=self.clear_dependent_fields,
                get_anonymous_id=self.get_anonymous_id,
            ),
        )


    def ask_changes_detail(self, chat_id, user_id, language):
        changes_detail_question.ask_changes_detail(self.ctx, chat_id, user_id, language)


    def handle_changes_detail_selection(self, call):
        changes_detail_question.handle_changes_detail_selection(
            self.ctx,
            call,
            ChangesDetailCallbacks(
                ask_wishlist=self.ask_wishlist,
                ask_final_confirmation=self.ask_final_confirmation,
                get_anonymous_id=self.get_anonymous_id,
            ),
        )


    def update_changes_detail_selection_keyboard(self, message, user_id, language):
        changes_detail_question.update_changes_detail_selection_keyboard(
            self.ctx, message, user_id, language
        )


    # Wishlist handler modifications
    def ask_wishlist(self, chat_id, user_id, language):
        wishlist_question.ask_wishlist(self.ctx, chat_id, user_id, language)


    def handle_wishlist_selection(self, call):
        wishlist_question.handle_wishlist_selection(
            self.ctx,
            call,
            WishlistCallbacks(
                ask_age=self.ask_age,
                ask_final_confirmation=self.ask_final_confirmation,
                get_anonymous_id=self.get_anonymous_id,
            ),
        )


    def update_wishlist_keyboard(self, message, user_id, language, options):
        wishlist_question.update_wishlist_keyboard(self.ctx, message, user_id, language, options)



    # Socioeconomic questions
    def _demographics_callbacks(self):
        return DemographicsCallbacks(
            ask_gender=self.ask_gender,
            ask_occupation=self.ask_occupation,
            ask_income=self.ask_income,
            ask_kremenchuk=self.ask_kremenchuk,
            ask_description=self.ask_description,
            ask_final_confirmation=self.ask_final_confirmation,
        )


    def ask_age(self, chat_id, user_id, language):
        demographics_question.ask_age(
            self.ctx, chat_id, user_id, language, self._demographics_callbacks()
        )


    def handle_age_selection(self, call):
        demographics_question.handle_age_selection(self.ctx, call)


    def confirm_age(self, call):
        demographics_question.confirm_age(self.ctx, call, self._demographics_callbacks())


    def ask_gender(self, chat_id, user_id, language):
        demographics_question.ask_gender(
            self.ctx, chat_id, user_id, language, self._demographics_callbacks()
        )


    def handle_gender_selection(self, call):
        demographics_question.handle_gender_selection(self.ctx, call)


    def confirm_gender(self, call):
        demographics_question.confirm_gender(self.ctx, call, self._demographics_callbacks())


    def ask_occupation(self, chat_id, user_id, language):
        demographics_question.ask_occupation(
            self.ctx, chat_id, user_id, language, self._demographics_callbacks()
        )


    def handle_occupation_selection(self, call):
        demographics_question.handle_occupation_selection(self.ctx, call)


    def confirm_occupation(self, call):
        demographics_question.confirm_occupation(self.ctx, call, self._demographics_callbacks())


    def ask_income(self, chat_id, user_id, language):
        demographics_question.ask_income(
            self.ctx, chat_id, user_id, language, self._demographics_callbacks()
        )


    def handle_income_selection(self, call):
        demographics_question.handle_income_selection(self.ctx, call)


    def confirm_income(self, call):
        demographics_question.confirm_income(self.ctx, call, self._demographics_callbacks())


    # Kremenchuk handler modifications
    def ask_kremenchuk(self, chat_id, user_id, language):
        kremenchuk_question.ask_kremenchuk(self.ctx, chat_id, user_id, language)


    def handle_kremenchuk_selection(self, call):
        kremenchuk_question.handle_kremenchuk_selection(
            self.ctx,
            call,
            KremenchukCallbacks(
                ask_description=self.ask_description,
                ask_final_confirmation=self.ask_final_confirmation,
            ),
        )


    def update_kremenchuk_keyboard(self, message, user_id, language, options):
        kremenchuk_question.update_kremenchuk_keyboard(
            self.ctx, message, user_id, language, options
        )



    # Description handlers
    def ask_description(self, chat_id, user_id, language):
        description_question.ask_description(
            self.ctx,
            chat_id,
            user_id,
            language,
            DescriptionCallbacks(
                ask_final_confirmation=self.ask_final_confirmation,
                description_handler=self.handle_description,
            ),
        )


    def handle_description_skip(self, call):
        description_question.handle_description_skip(
            self.ctx,
            call,
            DescriptionCallbacks(
                ask_final_confirmation=self.ask_final_confirmation,
                description_handler=self.handle_description,
            ),
        )


    def handle_description(self, message):
        description_question.handle_description(
            self.ctx,
            message,
            DescriptionCallbacks(
                ask_final_confirmation=self.ask_final_confirmation,
                description_handler=self.handle_description,
            ),
        )


    # Response confirmation and modification
    def _confirmation_callbacks(self):
        return ConfirmationCallbacks(
            ask_enjoyment=self.ask_enjoyment,
            ask_purpose_visit=self.ask_purpose_visit,
            ask_regularity=self.ask_regularity,
            ask_accessibility=self.ask_accessibility,
            ask_noticed_changes=self.ask_noticed_changes,
            ask_changes_detail=self.ask_changes_detail,
            ask_wishlist=self.ask_wishlist,
            ask_kremenchuk=self.ask_kremenchuk,
            ask_age=self.ask_age,
            ask_gender=self.ask_gender,
            ask_occupation=self.ask_occupation,
            ask_income=self.ask_income,
            ask_description=self.ask_description,
            ask_visitor_type=self.ask_visitor_type,
            ask_duration=self.ask_duration,
            ask_continue_or_stop=self.ask_continue_or_stop,
            save_data_and_restart=self.save_data_and_restart,
            get_anonymous_id=self.get_anonymous_id,
        )


    def ask_final_confirmation(self, chat_id, user_id, language):
        confirmation_question.ask_final_confirmation(self.ctx, chat_id, user_id, language)


    def get_responses_text(self, user_id, language):
        return confirmation_question.get_responses_text(self.ctx, user_id, language)


    def handle_final_confirmation_choice(self, call):
        confirmation_question.handle_final_confirmation_choice(
            self.ctx, call, self._confirmation_callbacks()
        )


    def ask_which_responses_to_modify(self, chat_id, user_id, language):
        confirmation_question.ask_which_responses_to_modify(
            self.ctx, chat_id, user_id, language, self._confirmation_callbacks()
        )


    def handle_modification_selection_callback(self, call):
        self.handle_modification_selection(call)


    def handle_modification_selection(self, call):
        confirmation_question.handle_modification_selection(
            self.ctx, call, self._confirmation_callbacks()
        )


    def get_question_dependencies(self):
        return confirmation_question.get_question_dependencies()


    def requires_follow_up(self, regularity_response):
        return confirmation_question.requires_follow_up(regularity_response)


    def skips_changes_questions(self, frequency_response):
        return confirmation_question.skips_changes_questions(frequency_response)


    def requires_changes_detail(self, changes_response):
        return confirmation_question.requires_changes_detail(changes_response)


    def clear_dependent_fields(self, user_id, field, old_value, new_value):
        return confirmation_question.clear_dependent_fields(
            self.ctx, user_id, field, old_value, new_value, self.get_anonymous_id
        )


    # Continue or stop handlers
    def _restart_callbacks(self):
        return RestartCallbacks(
            location_handler=self.handle_location_step,
            send_welcome=self.send_welcome,
            get_user_hash=self.get_user_hash,
            get_user_nickname=self.get_user_nickname,
            generate_unique_nickname=self.generate_unique_nickname,
            save_user_nickname=self.save_user_nickname,
            clear_message_ids=self.clear_message_ids,
        )


    def ask_continue_or_stop(self, chat_id, user_id, language):
        restart_question.ask_continue_or_stop(self.ctx, chat_id, user_id, language)


    def handle_continue_or_stop_selection(self, call):
        restart_question.handle_continue_or_stop_selection(
            self.ctx, call, self._restart_callbacks()
        )


    def handle_text_messages(self, m):
        """
        Handles all text messages sent by the user.
        """
        chat_id = m.chat.id
        user_id = m.from_user.id
        self.update_activity_timestamp(user_id)

        # Handle /start command explicitly here to ensure it always works
        if m.text.startswith('/start'):
            self.send_welcome(m)
            return

        # Check if user has any active session
        if user_id not in self._user_data() or 'language' not in self._user_data()[user_id]:
            # Try to get language from self._user_profiles()
            if user_id in self._user_profiles() and 'language' in self._user_profiles()[user_id]:
                self._user_data()[user_id] = {
                    'language': self._user_profiles()[user_id]['language']}
                language = self._user_data()[user_id]['language']
            else:
                # Send a start message if the user doesn't have an active session
                self.ctx.bot.send_message(
                    chat_id,
                    "Please use /start to begin a new survey.\nБудь ласка, використайте /start для початку нового опитування."
                )
                return
        else:
            language = self._user_data()[user_id]['language']

        if 'awaiting_multiple_select' in self._user_data()[user_id]:
            mode = self._user_data()[user_id]['awaiting_multiple_select']
            user_input = m.text.strip()

            # Handle custom input for each multiple-select question type
            if mode == 'purpose_visit':
                if 'custom_purposes' not in self._user_data()[user_id]:
                    self._user_data()[user_id]['custom_purposes'] = []
                self._user_data()[user_id]['custom_purposes'].append(user_input)
                ack_text = messages[language]['multiple_select_input_noted']
                self.ctx.bot.send_message(chat_id, ack_text)

            elif mode == 'changes_detail':
                if 'custom_changes' not in self._user_data()[user_id]:
                    self._user_data()[user_id]['custom_changes'] = []
                self._user_data()[user_id]['custom_changes'].append(user_input)
                ack_text = messages[language]['multiple_select_input_noted']
                self.ctx.bot.send_message(chat_id, ack_text)

            elif mode == 'visitor_type':
                if 'custom_visitor_types' not in self._user_data()[user_id]:
                    self._user_data()[user_id]['custom_visitor_types'] = []
                self._user_data()[user_id]['custom_visitor_types'].append(user_input)
                ack_text = messages[language]['multiple_select_input_noted']
                self.ctx.bot.send_message(chat_id, ack_text)

            elif mode == 'accessibility':
                if 'custom_accessibility' not in self._user_data()[user_id]:
                    self._user_data()[user_id]['custom_accessibility'] = []
                self._user_data()[user_id]['custom_accessibility'].append(user_input)
                ack_text = messages[language]['multiple_select_input_noted']
                self.ctx.bot.send_message(chat_id, ack_text)

            elif mode == 'wishlist':
                if 'custom_wishlist' not in self._user_data()[user_id]:
                    self._user_data()[user_id]['custom_wishlist'] = []
                self._user_data()[user_id]['custom_wishlist'].append(user_input)
                ack_text = messages[language]['multiple_select_input_noted']
                self.ctx.bot.send_message(chat_id, ack_text)

            elif mode == 'kremenchuk':
                if 'custom_kremenchuk' not in self._user_data()[user_id]:
                    self._user_data()[user_id]['custom_kremenchuk'] = []
                self._user_data()[user_id]['custom_kremenchuk'].append(user_input)
                ack_text = messages[language]['multiple_select_input_noted']
                self.ctx.bot.send_message(chat_id, ack_text)

            else:
                # Unknown multiple select mode
                self.ctx.bot.send_message(chat_id, messages[language]['multiple_select_prompt'])
        else:
            # Outside multiple-select mode, handle single-select questions
            current_question = self._user_data()[user_id].get('current_question')
            single_select_questions = [
                'enjoyment',
                'duration',
                'regularity',
                'frequency_change',
                'noticed_changes',
                'age',
                'gender',
                'occupation',
                'income']

            if current_question in single_select_questions:
                # Re-prompt user to select from options with a clearer message
                self.ctx.bot.send_message(
                    chat_id,
                    messages[language]['single_select_prompt']
                )

                # Re-send the appropriate question
                if current_question == 'enjoyment':
                    self.ask_enjoyment(chat_id, user_id, language)
                elif current_question == 'duration':
                    self.ask_duration(chat_id, user_id, language)
                elif current_question == 'regularity':
                    self.ask_regularity(chat_id, user_id, language)
                elif current_question == 'frequency_change':
                    self.ask_frequency_change(chat_id, user_id, language)
                elif current_question == 'noticed_changes':
                    self.ask_noticed_changes(chat_id, user_id, language)
                elif current_question == 'age':
                    self.ask_age(chat_id, user_id, language)
                elif current_question == 'gender':
                    self.ask_gender(chat_id, user_id, language)
                elif current_question == 'occupation':
                    self.ask_occupation(chat_id, user_id, language)
                elif current_question == 'income':
                    self.ask_income(chat_id, user_id, language)
            else:
                # For unsolicited text messages, guide the user
                help_text = messages[language]['unsolicited_text_help']
                self.ctx.bot.send_message(chat_id, help_text)



    # Data saving
    def save_data_and_restart(self, chat_id, user_id, language, restart_survey=False):
        return restart_question.save_data_and_restart(
            self.ctx,
            chat_id,
            user_id,
            language,
            restart_survey,
            self._restart_callbacks(),
        )


def create_legacy_bridge(ctx):
    return LegacyBridge(ctx)


def register_handlers(ctx):
    return create_legacy_bridge(ctx).register_handlers()
