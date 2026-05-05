"""Runtime Telegram bot implementation.

This module intentionally preserves the legacy survey behavior while moving
startup work behind `configure_runtime()` and `run()`.
"""

# Imports and configuration
import os
import logging
import time
import datetime
import sqlite3
import random
from pathlib import Path

import telebot
from telebot import types

from .messages import messages
from .pseudonym import hash_user_id
from . import runtime as runtime_module
from .runtime import flow_logger
from .storage import initialize_database as initialize_storage_database
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


class _RuntimeBotProxy:
    # TODO(phase-6): remove once remaining legacy helpers take ctx explicitly.
    def __getattr__(self, name):
        return getattr(_ctx().bot, name)


bot = _RuntimeBotProxy()


def _ctx():
    return runtime_module.require_active_context()


def _user_data():
    return _ctx().sessions.data


def _user_profiles():
    return _ctx().sessions.profiles


def _session_lock():
    return _ctx().sessions.lock


def _db_file():
    return str(_ctx().config.db_file)


def _voice_files_dir():
    return str(_ctx().config.voice_files_dir)


def _fernet():
    return _ctx().fernet


def configure_runtime(config):
    """Configure global legacy runtime objects for one bot process."""

    return runtime_module.configure_runtime(config)


def run(config=None):
    """Run the Telegram bot."""

    return runtime_module.run(
        config,
        initialize_database=initialize_database,
        recover_user_sessions=recover_user_sessions,
    )


def get_user_hash(user_id):
    return hash_user_id(user_id, _ctx().config.user_hash_salt)


def register_message_id(user_id, message_type, message_id):
    return telegram_io_module.register_message_id(_ctx(), user_id, message_type, message_id)


def get_message_id(user_id, message_type):
    return telegram_io_module.get_message_id(_ctx(), user_id, message_type)


def clear_message_ids(user_id):
    return telegram_io_module.clear_message_ids(_ctx(), user_id)


def send_keyboard_message(*args, **kwargs):
    return telegram_io_module.send_keyboard_message(_ctx(), *args, **kwargs)


def edit_keyboard(*args, **kwargs):
    return telegram_io_module.edit_keyboard(_ctx(), *args, **kwargs)


def safe_send_message(*args, **kwargs):
    return telegram_io_module.safe_send_message(_ctx(), *args, **kwargs)


def send_next_step_prompt(*args, **kwargs):
    return telegram_io_module.send_next_step_prompt(_ctx(), *args, **kwargs)


def handle_callback_error(*args, **kwargs):
    return telegram_io_module.handle_callback_error(
        _ctx(),
        *args,
        clear_callback_state=clear_callback_state,
        **kwargs,
    )


def safe_answer_callback(*args, **kwargs):
    return telegram_io_module.safe_answer_callback(_ctx(), *args, **kwargs)


def hide_keyboard(*args, **kwargs):
    return telegram_io_module.hide_keyboard(_ctx(), *args, **kwargs)


# Random nickname generation data
adjectives = [
    'Agile', 'Ancient', 'Angry', 'Brave', 'Bright', 'Calm', 'Charming',
    'Clever', 'Cool', 'Courageous', 'Crazy', 'Creative', 'Cute', 'Daring',
    'Delightful', 'Eager', 'Enchanting', 'Energetic', 'Fancy', 'Friendly',
    'Funny', 'Gentle', 'Glorious', 'Graceful', 'Happy', 'Helpful', 'Honest',
    'Hungry', 'Jolly', 'Kind', 'Lively', 'Lucky', 'Merry', 'Mighty',
    'Mysterious', 'Nice', 'Nimble', 'Peaceful', 'Perfect', 'Playful',
    'Proud', 'Quick', 'Quiet', 'Radiant', 'Rapid', 'Rich', 'Sharp', 'Shiny',
    'Silent', 'Silly', 'Smart', 'Smiling', 'Smooth', 'Soft', 'Sparkling',
    'Strong', 'Swift', 'Thoughtful', 'Tiny', 'Victorious', 'Warm', 'Wild',
    'Wise', 'Witty', 'Zealous', 'Adventurous', 'Affectionate', 'Alert',
    'Ambitious', 'Amused', 'Brilliant', 'Careful', 'Cheerful', 'Confident',
    'Cooperative', 'Courageous', 'Determined', 'Diligent', 'Eager', 'Elated',
    'Enthusiastic', 'Excited', 'Exuberant', 'Fair', 'Faithful', 'Fearless',
    'Frank', 'Friendly', 'Funny', 'Generous', 'Gentle', 'Good', 'Happy',
    'Hardworking', 'Helpful', 'Honest', 'Humorous', 'Imaginative',
    'Intelligent', 'Joyful'
]

nouns = [
    'Antelope', 'Badger', 'Bat', 'Bear', 'Beaver', 'Bee', 'Bird', 'Butterfly',
    'Camel', 'Cat', 'Cheetah', 'Chicken', 'Chimpanzee', 'Cobra', 'Cougar',
    'Cow', 'Coyote', 'Crab', 'Crocodile', 'Deer', 'Dog', 'Dolphin', 'Donkey',
    'Duck', 'Eagle', 'Elephant', 'Falcon', 'Ferret', 'Fish', 'Fox', 'Frog',
    'Giraffe', 'Goat', 'Goose', 'Gorilla', 'Hamster', 'Hawk', 'Hedgehog',
    'Hippo', 'Horse', 'Hyena', 'Jaguar', 'Kangaroo', 'Koala', 'Leopard',
    'Lion', 'Lizard', 'Llama', 'Lobster', 'Monkey', 'Moose', 'Mouse',
    'Octopus', 'Ostrich', 'Otter', 'Owl', 'Panda', 'Panther', 'Parrot',
    'Peacock', 'Penguin', 'Pig', 'Polar Bear', 'Rabbit', 'Raccoon', 'Rat',
    'Raven', 'Reindeer', 'Rhinoceros', 'Seal', 'Shark', 'Sheep', 'Skunk',
    'Sloth', 'Snake', 'Spider', 'Squirrel', 'Swan', 'Tiger', 'Turkey',
    'Turtle', 'Walrus', 'Wasp', 'Weasel', 'Whale', 'Wolf', 'Wombat',
    'Woodpecker', 'Yak', 'Zebra'
]

# URLs for privacy notices and participant information





# Messages dictionary




# Helper functions
def generate_unique_nickname():
    max_combinations = len(adjectives) * len(nouns) * \
        1000  # Adjusted for number range 0-999
    used_nicknames = get_all_used_nicknames()
    if len(used_nicknames) >= max_combinations:
        # All combinations have been used
        raise Exception("All nickname combinations have been used.")
    while True:
        adjective = random.choice(adjectives)
        noun = random.choice(nouns)
        number = random.randint(0, 999)
        nickname = f"{adjective} {noun} {number}"
        if nickname not in used_nicknames:
            return nickname


def get_all_used_nicknames():
    with sqlite3.connect(_db_file(), check_same_thread=False) as conn:
        cursor = conn.execute('SELECT DISTINCT nickname FROM user_nicknames')
        return {row[0] for row in cursor.fetchall()}


def create_inline_keyboard(options, prefix, single_select=False):
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


def get_user_nickname(user_hash):
    with sqlite3.connect(_db_file(), check_same_thread=False) as conn:
        cursor = conn.execute('''
            SELECT nickname FROM user_nicknames
            WHERE user_hash = ?
            ORDER BY month_year DESC LIMIT 1
        ''', (user_hash,))
        result = cursor.fetchone()
        return result[0] if result else None

# Add these helper functions
# Add these helper functions with better error handling
def get_user_data(user_id, key=None, default=None):
    """Thread-safe access to _user_data()."""
    try:
        with _session_lock():
            if user_id not in _user_data():
                _user_data()[user_id] = {}
            if key is None:
                return _user_data()[user_id]
            return _user_data()[user_id].get(key, default)
    except Exception as e:
        flow_logger.error(f"Error in get_user_data: {e}")
        if key is None:
            return {}
        return default

def set_user_data(user_id, key, value):
    """Thread-safe setting of _user_data() values."""
    try:
        with _session_lock():
            if user_id not in _user_data():
                _user_data()[user_id] = {}
            _user_data()[user_id][key] = value
        return True
    except Exception as e:
        flow_logger.error(f"Error in set_user_data: {e}")
        return False

def remove_user_data(user_id, key):
    """Thread-safe removal of _user_data() keys."""
    try:
        with _session_lock():
            if user_id in _user_data() and key in _user_data()[user_id]:
                return _user_data()[user_id].pop(key)
        return None
    except Exception as e:
        flow_logger.error(f"Error in remove_user_data: {e}")
        return None

def get_user_profile(user_id, key=None, default=None):
    """Thread-safe access to _user_profiles()."""
    try:
        with _session_lock():
            if user_id not in _user_profiles():
                _user_profiles()[user_id] = {}
            if key is None:
                return _user_profiles()[user_id]
            return _user_profiles()[user_id].get(key, default)
    except Exception as e:
        flow_logger.error(f"Error in get_user_profile: {e}")
        if key is None:
            return {}
        return default

def set_user_profile(user_id, key, value):
    """Thread-safe setting of _user_profiles() values."""
    try:
        with _session_lock():
            if user_id not in _user_profiles():
                _user_profiles()[user_id] = {}
            _user_profiles()[user_id][key] = value
        return True
    except Exception as e:
        flow_logger.error(f"Error in set_user_profile: {e}")
        return False


def save_user_nickname(user_hash, nickname):
    month_year = datetime.datetime.now().strftime('%Y-%m')
    with sqlite3.connect(_db_file(), check_same_thread=False) as conn:
        conn.execute('''
            INSERT OR IGNORE INTO user_nicknames
            (user_hash, nickname, month_year)
            VALUES (?, ?, ?)
        ''', (user_hash, nickname, month_year))


# Add this function to the top of your script to help with error handling


def safe_get_language(user_id):
    """
    Safely tries to get user's language preference with fallbacks.

    Args:
        user_id (int): The user's ID

    Returns:
        str: Language code ('en' or 'uk') with fallback to 'en'
    """
    try:
        # Try _user_data() first
        if user_id in _user_data() and 'language' in _user_data()[user_id]:
            return _user_data()[user_id]['language']

        # Try _user_profiles() next
        if user_id in _user_profiles() and 'language' in _user_profiles()[user_id]:
            return _user_profiles()[user_id]['language']

        # Default fallback
        return 'en'
    except Exception:
        # Ultimate fallback
        return 'en'


def clear_callback_state(user_id):
    """Clear transient callback state for a user after a handler error."""

    with _session_lock():
        if user_id in _user_data():
            keys_to_remove = []
            for key in _user_data()[user_id]:
                if (key.startswith('temp_') or
                    key == 'awaiting_multiple_select' or
                    key == 'current_question' or
                    key == 'modifying' or
                    key == 'modifying_field'):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                _user_data()[user_id].pop(key, None)


def ensure_session_valid(call):
    """
    Ensures a user has a valid session with language set.

    Args:
        call: The callback query object

    Returns:
        tuple: (is_valid, language) - is_valid is True if session is valid, False otherwise
    """
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # Ensure user exists in _user_data() and has language
    if user_id not in _user_data() or 'language' not in _user_data()[user_id]:
        # Try to get language from _user_profiles()
        if user_id in _user_profiles() and 'language' in _user_profiles()[user_id]:
            # Initialize user data if needed
            if user_id not in _user_data():
                _user_data()[user_id] = {}
            _user_data()[user_id]['language'] = _user_profiles()[user_id]['language']
            return True, _user_data()[user_id]['language']
        else:
            # Cannot proceed without language
            try:
                bot.answer_callback_query(
                    call.id, "Please start again with /start")
                bot.send_message(
                    chat_id,
                    "Session expired. Please use /start to begin.\nСесія закінчилася. Будь ласка, використайте /start для початку.")
            except Exception:
                pass
            return False, 'en'
    else:
        return True, _user_data()[user_id]['language']


def recover_user_sessions():
    """Attempt to recover user sessions after bot restart"""
    try:
        flow_logger.info("Attempting to recover user sessions...")

        # Get a snapshot of current _user_data() to avoid modification during
        # iteration
        with _session_lock():
            users_to_recover = list(_user_data().keys())
        recovered_count = 0

        for user_id in users_to_recover:
            try:
                # Ensure basic data structures exist
                with _session_lock():
                    session = _user_data().get(user_id, {})
                if 'language' not in session:
                    language = get_user_profile(user_id, 'language')
                    if language:
                        set_user_data(user_id, 'language', language)
                    else:
                        # Can't recover without language
                        continue

                # Restore nickname from database if needed
                if 'nickname' not in get_user_data(user_id):
                    user_hash = get_user_hash(user_id)
                    nickname = get_user_nickname(user_hash)
                    if nickname:
                        set_user_data(user_id, 'nickname', nickname)

                # Mark recovery state - will be used to inform users later
                set_user_data(user_id, 'session_recovered', True)
                recovered_count += 1

                flow_logger.info(f"Recovered session for user {user_id}")

            except Exception as inner_e:
                flow_logger.error(
                    f"Error recovering session for user {user_id}: {inner_e}")

        flow_logger.info(
            f"Session recovery complete. Recovered {recovered_count} sessions.")

    except Exception as e:
        flow_logger.error(f"Error in session recovery process: {e}")


def cleanup_stale_sessions(hours_inactive=48):
    """
    Remove stale user sessions to free memory.
    This should be called periodically to prevent memory leaks.

    Args:
        hours_inactive (int): Number of hours of inactivity before cleaning up
    """
    try:
        flow_logger.info(
            f"Starting stale session cleanup, removing sessions inactive for {hours_inactive} hours")
        current_time = time.time()
        cutoff_time = current_time - (hours_inactive * 60 * 60)
        users_to_remove = []

        # First identify which users to remove from a lock-protected snapshot.
        with _session_lock():
            user_items = list(_user_data().items())

        for user_id, data in user_items:
            last_activity = data.get('last_activity_time', 0)
            if last_activity < cutoff_time:
                users_to_remove.append(user_id)

        # Then remove them
        for user_id in users_to_remove:
            try:
                with _session_lock():
                    _user_data().pop(user_id, None)
                flow_logger.info(f"Removed stale session for user {user_id}")
            except Exception as e:
                flow_logger.error(
                    f"Error removing session for user {user_id}: {e}")

        flow_logger.info(
            f"Stale session cleanup complete. Removed {len(users_to_remove)} sessions.")
    except Exception as e:
        flow_logger.error(f"Error in stale session cleanup: {e}")


def update_activity_timestamp(user_id):
    """
    Update the last activity timestamp for a user.
    This helps identify stale sessions.

    Args:
        user_id (int): User identifier
    """
    with _session_lock():
        if user_id in _user_data():
            _user_data()[user_id]['last_activity_time'] = time.time()
        else:
            # If user doesn't exist in _user_data(), initialize it
            _user_data()[user_id] = {'last_activity_time': time.time()}


# Database functions
def initialize_database():
    try:
        initialize_storage_database(Path(_db_file()))
        flow_logger.info("Database initialized successfully")
    except Exception as e:
        logging.exception(f"Error initializing responses database: {e}")
        raise e


def register_handlers(ctx):
    """Register legacy wrapper entry points against a configured TeleBot."""

    bot_instance = ctx.bot
    bot_instance.callback_query_handler(func=lambda call: call.data == 'restart')(
        handle_restart
    )
    bot_instance.message_handler(commands=['start'])(send_welcome)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('language_')
    )(handle_language_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('consent_')
    )(handle_consent)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == 'post_consent_continue'
    )(handle_post_consent_continue)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('purpose_')
    )(handle_purpose_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('enjoyment_')
    )(handle_enjoyment_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_enjoyment"
    )(confirm_enjoyment)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('visitor_')
    )(handle_visitor_type_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('duration_')
    )(handle_duration_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_duration"
    )(confirm_duration)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('accessibility_')
    )(handle_accessibility_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('regularity_')
    )(handle_regularity_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_regularity"
    )(confirm_regularity)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('frequency_change_')
    )(handle_frequency_change_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('noticed_changes_')
    )(handle_noticed_changes_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_noticed_changes"
    )(confirm_noticed_changes)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('changes_detail_')
    )(handle_changes_detail_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('wishlist_')
    )(handle_wishlist_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('age_')
    )(handle_age_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_age"
    )(confirm_age)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('gender_')
    )(handle_gender_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_gender"
    )(confirm_gender)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('occupation_')
    )(handle_occupation_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_occupation"
    )(confirm_occupation)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('income_')
    )(handle_income_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == "confirm_income"
    )(confirm_income)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('kremenchuk_')
    )(handle_kremenchuk_selection)
    bot_instance.callback_query_handler(
        func=lambda call: call.data == 'description_skip'
    )(handle_description_skip)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('final_')
    )(handle_final_confirmation_choice)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('modify_')
        or call.data == 'modification_done'
    )(handle_modification_selection_callback)
    bot_instance.callback_query_handler(
        func=lambda call: call.data.startswith('continue_')
    )(handle_continue_or_stop_selection)
    bot_instance.message_handler(func=lambda m: True, content_types=['text'])(
        handle_text_messages
    )

# Start, language, and location handlers
def _welcome_callbacks():
    return welcome_question.WelcomeCallbacks(
        update_activity_timestamp=update_activity_timestamp,
        get_user_hash=get_user_hash,
        get_user_nickname=get_user_nickname,
        generate_unique_nickname=generate_unique_nickname,
        save_user_nickname=save_user_nickname,
        send_welcome=send_welcome,
    )


def _language_callbacks():
    return language_question.LanguageCallbacks(
        location_handler=handle_location_step,
    )


def _location_callbacks():
    return location_question.LocationCallbacks(
        update_activity_timestamp=update_activity_timestamp,
        send_welcome=send_welcome,
        ask_purpose_visit=ask_purpose_visit,
        location_handler=handle_location_step,
    )


def handle_restart(call):
    welcome_question.handle_restart(_ctx(), call, _welcome_callbacks())


def send_welcome(message=None, chat_id=None, user_id=None, start_param=None):
    welcome_question.send_welcome(
        _ctx(),
        callbacks=_welcome_callbacks(),
        message=message,
        chat_id=chat_id,
        user_id=user_id,
        start_param=start_param,
    )


def handle_language_selection(call):
    language_question.handle_language_selection(_ctx(), call, _language_callbacks())

def handle_consent(call):
    consent_question.handle_consent(_ctx(), call)


def handle_post_consent_continue(call):
    consent_question.handle_post_consent_continue(
        _ctx(),
        call,
        ConsentCallbacks(location_handler=handle_location_step),
    )




def handle_location_step(message):
    location_question.handle_location_step(_ctx(), message, _location_callbacks())



# Purpose visit handler
# Updated ask_purpose_visit function
def ask_purpose_visit(chat_id, user_id, language):
    purpose_question.ask_purpose_visit(_ctx(), chat_id, user_id, language)


# Updated handle_purpose_selection function
def handle_purpose_selection(call):
    purpose_question.handle_purpose_selection(
        _ctx(),
        call,
        PurposeCallbacks(
            ask_enjoyment=ask_enjoyment,
            ask_final_confirmation=ask_final_confirmation,
            clear_callback_state=clear_callback_state,
        ),
    )


# Updated update_purpose_selection_keyboard function
def update_purpose_selection_keyboard(message, user_id, language):
    purpose_question.update_purpose_selection_keyboard(
        _ctx(), message, user_id, language
    )



# Enjoyment and visitor type handlers
def ask_enjoyment(chat_id, user_id, language, remove_keyboard=False):
    enjoyment_question.ask_enjoyment(
        _ctx(), chat_id, user_id, language, remove_keyboard=remove_keyboard
    )


def handle_enjoyment_selection(call):
    enjoyment_question.handle_enjoyment_selection(
        _ctx(),
        call,
        EnjoymentCallbacks(
            ask_visitor_type=ask_visitor_type,
            ask_final_confirmation=ask_final_confirmation,
        ),
    )


def confirm_enjoyment(call):
    enjoyment_question.confirm_enjoyment(
        _ctx(),
        call,
        EnjoymentCallbacks(
            ask_visitor_type=ask_visitor_type,
            ask_final_confirmation=ask_final_confirmation,
        ),
    )


# Visitor type handler modifications
def ask_visitor_type(chat_id, user_id, language):
    visitor_type_question.ask_visitor_type(_ctx(), chat_id, user_id, language)


def handle_visitor_type_selection(call):
    visitor_type_question.handle_visitor_type_selection(
        _ctx(),
        call,
        VisitorTypeCallbacks(
            ask_duration=ask_duration,
            ask_final_confirmation=ask_final_confirmation,
        ),
    )


def update_visitor_type_keyboard(message, user_id, language, options):
    visitor_type_question.update_visitor_type_keyboard(
        _ctx(), message, user_id, language, options
    )



# Duration and accessibility handlers
def ask_duration(chat_id, user_id, language):
    duration_question.ask_duration(_ctx(), chat_id, user_id, language)


def handle_duration_selection(call):
    duration_question.handle_duration_selection(_ctx(), call)


def confirm_duration(call):
    duration_question.confirm_duration(
        _ctx(),
        call,
        DurationCallbacks(
            ask_accessibility=ask_accessibility,
            ask_final_confirmation=ask_final_confirmation,
        ),
    )


# Accessibility handler modifications
def ask_accessibility(chat_id, user_id, language):
    accessibility_question.ask_accessibility(_ctx(), chat_id, user_id, language)


def handle_accessibility_selection(call):
    accessibility_question.handle_accessibility_selection(
        _ctx(),
        call,
        AccessibilityCallbacks(
            ask_regularity=ask_regularity,
            ask_final_confirmation=ask_final_confirmation,
        ),
    )


def update_accessibility_keyboard(message, user_id, language, options):
    accessibility_question.update_accessibility_keyboard(
        _ctx(), message, user_id, language, options
    )



def ask_regularity(chat_id, user_id, language):
    regularity_question.ask_regularity(_ctx(), chat_id, user_id, language)


def handle_regularity_selection(call):
    regularity_question.handle_regularity_selection(_ctx(), call)


def confirm_regularity(call):
    regularity_question.confirm_regularity(
        _ctx(),
        call,
        RegularityCallbacks(
            ask_noticed_changes=ask_noticed_changes,
            ask_wishlist=ask_wishlist,
            ask_final_confirmation=ask_final_confirmation,
            clear_dependent_fields=clear_dependent_fields,
            get_anonymous_id=get_anonymous_id,
        ),
    )


def ask_frequency_change(chat_id, user_id, language):
    frequency_question.ask_frequency_change(_ctx(), chat_id, user_id, language)


def handle_frequency_change_selection(call):
    frequency_question.handle_frequency_change_selection(
        _ctx(),
        call,
        FrequencyCallbacks(
            ask_noticed_changes=ask_noticed_changes,
            ask_wishlist=ask_wishlist,
            ask_final_confirmation=ask_final_confirmation,
            clear_dependent_fields=clear_dependent_fields,
            get_anonymous_id=get_anonymous_id,
        ),
    )


# Noticed changes and changes details handlers
def ask_noticed_changes(chat_id, user_id, language):
    noticed_changes_question.ask_noticed_changes(_ctx(), chat_id, user_id, language)


def handle_noticed_changes_selection(call):
    noticed_changes_question.handle_noticed_changes_selection(_ctx(), call)


def confirm_noticed_changes(call):
    noticed_changes_question.confirm_noticed_changes(
        _ctx(),
        call,
        NoticedChangesCallbacks(
            ask_changes_detail=ask_changes_detail,
            ask_wishlist=ask_wishlist,
            ask_final_confirmation=ask_final_confirmation,
            clear_dependent_fields=clear_dependent_fields,
            get_anonymous_id=get_anonymous_id,
        ),
    )


def ask_changes_detail(chat_id, user_id, language):
    changes_detail_question.ask_changes_detail(_ctx(), chat_id, user_id, language)


def handle_changes_detail_selection(call):
    changes_detail_question.handle_changes_detail_selection(
        _ctx(),
        call,
        ChangesDetailCallbacks(
            ask_wishlist=ask_wishlist,
            ask_final_confirmation=ask_final_confirmation,
            get_anonymous_id=get_anonymous_id,
        ),
    )


def update_changes_detail_selection_keyboard(message, user_id, language):
    changes_detail_question.update_changes_detail_selection_keyboard(
        _ctx(), message, user_id, language
    )


# Wishlist handler modifications
def ask_wishlist(chat_id, user_id, language):
    wishlist_question.ask_wishlist(_ctx(), chat_id, user_id, language)


def handle_wishlist_selection(call):
    wishlist_question.handle_wishlist_selection(
        _ctx(),
        call,
        WishlistCallbacks(
            ask_age=ask_age,
            ask_final_confirmation=ask_final_confirmation,
            get_anonymous_id=get_anonymous_id,
        ),
    )


def update_wishlist_keyboard(message, user_id, language, options):
    wishlist_question.update_wishlist_keyboard(_ctx(), message, user_id, language, options)



# Socioeconomic questions
def _demographics_callbacks():
    return DemographicsCallbacks(
        ask_gender=ask_gender,
        ask_occupation=ask_occupation,
        ask_income=ask_income,
        ask_kremenchuk=ask_kremenchuk,
        ask_description=ask_description,
        ask_final_confirmation=ask_final_confirmation,
    )


def ask_age(chat_id, user_id, language):
    demographics_question.ask_age(
        _ctx(), chat_id, user_id, language, _demographics_callbacks()
    )


def handle_age_selection(call):
    demographics_question.handle_age_selection(_ctx(), call)


def confirm_age(call):
    demographics_question.confirm_age(_ctx(), call, _demographics_callbacks())


def ask_gender(chat_id, user_id, language):
    demographics_question.ask_gender(
        _ctx(), chat_id, user_id, language, _demographics_callbacks()
    )


def handle_gender_selection(call):
    demographics_question.handle_gender_selection(_ctx(), call)


def confirm_gender(call):
    demographics_question.confirm_gender(_ctx(), call, _demographics_callbacks())


def ask_occupation(chat_id, user_id, language):
    demographics_question.ask_occupation(
        _ctx(), chat_id, user_id, language, _demographics_callbacks()
    )


def handle_occupation_selection(call):
    demographics_question.handle_occupation_selection(_ctx(), call)


def confirm_occupation(call):
    demographics_question.confirm_occupation(_ctx(), call, _demographics_callbacks())


def ask_income(chat_id, user_id, language):
    demographics_question.ask_income(
        _ctx(), chat_id, user_id, language, _demographics_callbacks()
    )


def handle_income_selection(call):
    demographics_question.handle_income_selection(_ctx(), call)


def confirm_income(call):
    demographics_question.confirm_income(_ctx(), call, _demographics_callbacks())


# Kremenchuk handler modifications
def ask_kremenchuk(chat_id, user_id, language):
    kremenchuk_question.ask_kremenchuk(_ctx(), chat_id, user_id, language)


def handle_kremenchuk_selection(call):
    kremenchuk_question.handle_kremenchuk_selection(
        _ctx(),
        call,
        KremenchukCallbacks(
            ask_description=ask_description,
            ask_final_confirmation=ask_final_confirmation,
        ),
    )


def update_kremenchuk_keyboard(message, user_id, language, options):
    kremenchuk_question.update_kremenchuk_keyboard(
        _ctx(), message, user_id, language, options
    )



# Description handlers
def ask_description(chat_id, user_id, language):
    description_question.ask_description(
        _ctx(),
        chat_id,
        user_id,
        language,
        DescriptionCallbacks(
            ask_final_confirmation=ask_final_confirmation,
            description_handler=handle_description,
        ),
    )


def handle_description_skip(call):
    description_question.handle_description_skip(
        _ctx(),
        call,
        DescriptionCallbacks(
            ask_final_confirmation=ask_final_confirmation,
            description_handler=handle_description,
        ),
    )


def handle_description(message):
    description_question.handle_description(
        _ctx(),
        message,
        DescriptionCallbacks(
            ask_final_confirmation=ask_final_confirmation,
            description_handler=handle_description,
        ),
    )


# Response confirmation and modification
def _confirmation_callbacks():
    return ConfirmationCallbacks(
        ask_enjoyment=ask_enjoyment,
        ask_purpose_visit=ask_purpose_visit,
        ask_regularity=ask_regularity,
        ask_accessibility=ask_accessibility,
        ask_noticed_changes=ask_noticed_changes,
        ask_changes_detail=ask_changes_detail,
        ask_wishlist=ask_wishlist,
        ask_kremenchuk=ask_kremenchuk,
        ask_age=ask_age,
        ask_gender=ask_gender,
        ask_occupation=ask_occupation,
        ask_income=ask_income,
        ask_description=ask_description,
        ask_visitor_type=ask_visitor_type,
        ask_duration=ask_duration,
        ask_continue_or_stop=ask_continue_or_stop,
        save_data_and_restart=save_data_and_restart,
        get_anonymous_id=get_anonymous_id,
    )


def ask_final_confirmation(chat_id, user_id, language):
    confirmation_question.ask_final_confirmation(_ctx(), chat_id, user_id, language)


def get_responses_text(user_id, language):
    return confirmation_question.get_responses_text(_ctx(), user_id, language)


def handle_final_confirmation_choice(call):
    confirmation_question.handle_final_confirmation_choice(
        _ctx(), call, _confirmation_callbacks()
    )


def ask_which_responses_to_modify(chat_id, user_id, language):
    confirmation_question.ask_which_responses_to_modify(
        _ctx(), chat_id, user_id, language, _confirmation_callbacks()
    )


def handle_modification_selection_callback(call):
    handle_modification_selection(call)


def handle_modification_selection(call):
    confirmation_question.handle_modification_selection(
        _ctx(), call, _confirmation_callbacks()
    )


def get_question_dependencies():
    return confirmation_question.get_question_dependencies()


def requires_follow_up(regularity_response):
    return confirmation_question.requires_follow_up(regularity_response)


def skips_changes_questions(frequency_response):
    return confirmation_question.skips_changes_questions(frequency_response)


def requires_changes_detail(changes_response):
    return confirmation_question.requires_changes_detail(changes_response)


def clear_dependent_fields(user_id, field, old_value, new_value):
    return confirmation_question.clear_dependent_fields(
        _ctx(), user_id, field, old_value, new_value, get_anonymous_id
    )


# Continue or stop handlers
def _restart_callbacks():
    return RestartCallbacks(
        location_handler=handle_location_step,
        send_welcome=send_welcome,
        get_user_hash=get_user_hash,
        get_user_nickname=get_user_nickname,
        generate_unique_nickname=generate_unique_nickname,
        save_user_nickname=save_user_nickname,
        clear_message_ids=clear_message_ids,
    )


def ask_continue_or_stop(chat_id, user_id, language):
    restart_question.ask_continue_or_stop(_ctx(), chat_id, user_id, language)


def handle_continue_or_stop_selection(call):
    restart_question.handle_continue_or_stop_selection(
        _ctx(), call, _restart_callbacks()
    )


def handle_text_messages(m):
    """
    Handles all text messages sent by the user.
    """
    chat_id = m.chat.id
    user_id = m.from_user.id
    update_activity_timestamp(user_id)

    # Handle /start command explicitly here to ensure it always works
    if m.text.startswith('/start'):
        send_welcome(m)
        return

    # Check if user has any active session
    if user_id not in _user_data() or 'language' not in _user_data()[user_id]:
        # Try to get language from _user_profiles()
        if user_id in _user_profiles() and 'language' in _user_profiles()[user_id]:
            _user_data()[user_id] = {
                'language': _user_profiles()[user_id]['language']}
            language = _user_data()[user_id]['language']
        else:
            # Send a start message if the user doesn't have an active session
            bot.send_message(
                chat_id,
                "Please use /start to begin a new survey.\nБудь ласка, використайте /start для початку нового опитування."
            )
            return
    else:
        language = _user_data()[user_id]['language']

    if 'awaiting_multiple_select' in _user_data()[user_id]:
        mode = _user_data()[user_id]['awaiting_multiple_select']
        user_input = m.text.strip()

        # Handle custom input for each multiple-select question type
        if mode == 'purpose_visit':
            if 'custom_purposes' not in _user_data()[user_id]:
                _user_data()[user_id]['custom_purposes'] = []
            _user_data()[user_id]['custom_purposes'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'changes_detail':
            if 'custom_changes' not in _user_data()[user_id]:
                _user_data()[user_id]['custom_changes'] = []
            _user_data()[user_id]['custom_changes'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'visitor_type':
            if 'custom_visitor_types' not in _user_data()[user_id]:
                _user_data()[user_id]['custom_visitor_types'] = []
            _user_data()[user_id]['custom_visitor_types'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'accessibility':
            if 'custom_accessibility' not in _user_data()[user_id]:
                _user_data()[user_id]['custom_accessibility'] = []
            _user_data()[user_id]['custom_accessibility'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'wishlist':
            if 'custom_wishlist' not in _user_data()[user_id]:
                _user_data()[user_id]['custom_wishlist'] = []
            _user_data()[user_id]['custom_wishlist'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'kremenchuk':
            if 'custom_kremenchuk' not in _user_data()[user_id]:
                _user_data()[user_id]['custom_kremenchuk'] = []
            _user_data()[user_id]['custom_kremenchuk'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        else:
            # Unknown multiple select mode
            bot.send_message(chat_id, "Please make a selection from the available options." if language ==
                             'en' else "Будь ласка, зробіть вибір із доступних варіантів.")
    else:
        # Outside multiple-select mode, handle single-select questions
        current_question = _user_data()[user_id].get('current_question')
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
            bot.send_message(
                chat_id,
                "Please select one of the options provided in the buttons below." if language == 'en' else
                "Будь ласка, оберіть один із варіантів, запропонованих у кнопках нижче."
            )

            # Re-send the appropriate question
            if current_question == 'enjoyment':
                ask_enjoyment(chat_id, user_id, language)
            elif current_question == 'duration':
                ask_duration(chat_id, user_id, language)
            elif current_question == 'regularity':
                ask_regularity(chat_id, user_id, language)
            elif current_question == 'frequency_change':
                ask_frequency_change(chat_id, user_id, language)
            elif current_question == 'noticed_changes':
                ask_noticed_changes(chat_id, user_id, language)
            elif current_question == 'age':
                ask_age(chat_id, user_id, language)
            elif current_question == 'gender':
                ask_gender(chat_id, user_id, language)
            elif current_question == 'occupation':
                ask_occupation(chat_id, user_id, language)
            elif current_question == 'income':
                ask_income(chat_id, user_id, language)
        else:
            # For unsolicited text messages, guide the user
            help_text = (
                "I'm not sure what you want to do. Please follow the instructions shown on screen. "
                "If you're stuck, use /start to restart the survey."
            ) if language == 'en' else (
                "Я не впевнений, що ви хочете зробити. Будь ласка, слідуйте інструкціям, показаним на екрані. "
                "Якщо ви застрягли, використовуйте /start для перезапуску опитування."
            )
            bot.send_message(chat_id, help_text)



# Data saving
def save_data_and_restart(chat_id, user_id, language, restart_survey=False):
    return restart_question.save_data_and_restart(
        _ctx(),
        chat_id,
        user_id,
        language,
        restart_survey,
        _restart_callbacks(),
    )

if __name__ == '__main__':
    run()
