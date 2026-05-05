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
from .survey.persistence import (
    DatabaseSaveError,
    EncryptionUnavailableError,
    save_response,
)
from .survey.questions import consent as consent_question
from .survey.questions import description as description_question
from .survey.questions import accessibility as accessibility_question
from .survey.questions import duration as duration_question
from .survey.questions import enjoyment as enjoyment_question
from .survey.questions import language as language_question
from .survey.questions import location as location_question
from .survey.questions import purpose as purpose_question
from .survey.questions import regularity as regularity_question
from .survey.questions import visitor_type as visitor_type_question
from .survey.questions import welcome as welcome_question
from .survey.questions.base import (
    AccessibilityCallbacks,
    ConsentCallbacks,
    DescriptionCallbacks,
    DurationCallbacks,
    EnjoymentCallbacks,
    PurposeCallbacks,
    RegularityCallbacks,
    VisitorTypeCallbacks,
)
from . import telegram_io as telegram_io_module
from .telegram_io import (
    callback_index,
    callback_suffix,
    escape_html,
    telegram_retry_after,
)


# Temporary import-time registry; Phase 5 registers handlers after runtime setup.
bot = runtime_module.bot


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


# Example of how to use these helpers in a callback handler:
"""
@bot.callback_query_handler(func=lambda call: call.data.startswith('example_'))
def handle_example_callback(call):
    try:
        is_valid, language = ensure_session_valid(call)
        if not is_valid:
            return

        # Regular function logic here...

    except Exception as e:
        handle_callback_error(call, e, "handle_example_callback")
"""


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


@bot.callback_query_handler(func=lambda call: call.data == 'restart')
def handle_restart(call):
    welcome_question.handle_restart(_ctx(), call, _welcome_callbacks())


@bot.message_handler(commands=['start'])
def send_welcome(message=None, chat_id=None, user_id=None, start_param=None):
    welcome_question.send_welcome(
        _ctx(),
        callbacks=_welcome_callbacks(),
        message=message,
        chat_id=chat_id,
        user_id=user_id,
        start_param=start_param,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('language_'))
def handle_language_selection(call):
    language_question.handle_language_selection(_ctx(), call, _language_callbacks())

@bot.callback_query_handler(func=lambda call: call.data.startswith('consent_'))
def handle_consent(call):
    consent_question.handle_consent(_ctx(), call)


@bot.callback_query_handler(func=lambda call: call.data ==
                            'post_consent_continue')
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
@bot.callback_query_handler(func=lambda call: call.data.startswith('purpose_'))
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('enjoyment_'))
def handle_enjoyment_selection(call):
    enjoyment_question.handle_enjoyment_selection(
        _ctx(),
        call,
        EnjoymentCallbacks(
            ask_visitor_type=ask_visitor_type,
            ask_final_confirmation=ask_final_confirmation,
        ),
    )


@bot.callback_query_handler(func=lambda call: call.data == "confirm_enjoyment")
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('visitor_'))
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('duration_'))
def handle_duration_selection(call):
    duration_question.handle_duration_selection(_ctx(), call)


@bot.callback_query_handler(func=lambda call: call.data == "confirm_duration")
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


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('accessibility_'))
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('regularity_'))
def handle_regularity_selection(call):
    regularity_question.handle_regularity_selection(_ctx(), call)


@bot.callback_query_handler(func=lambda call: call.data ==
                            "confirm_regularity")
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
    """
    Asks if user's visit frequency has changed compared to previous years.
    Second question in the dependent chain, follows regularity.
    """
    try:
        # Remove flow logging for normal flow
        _user_data()[user_id]['frequency_change'] = ''
        _user_data()[user_id]['current_question'] = 'frequency_change'
        options = messages[language]['options']['frequency_change']
        inline_kb = types.InlineKeyboardMarkup(row_width=1)

        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"frequency_change_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)

        bot.send_message(
            chat_id,
            messages[language]['frequency_change_question'],
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_frequency_change: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('frequency_change_'))
def handle_frequency_change_selection(call):
    """
    Handles user selection for frequency change question.
    """
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        anon_id = get_anonymous_id(user_id)

        options = messages[language]['options']['frequency_change']
        try:
            idx = callback_index(call.data, "frequency_change", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language].get(
                    'invalid_selection', "Invalid selection."))
            return

        selected_frequency_change = options[idx]
        previous_freq_change = _user_data()[user_id].get('frequency_change', '')

        # Only log if this is a modification
        if _user_data()[user_id].get(
                'modifying') and previous_freq_change != selected_frequency_change:
            flow_logger.info(
                f"User {anon_id}: Modified frequency_change from '{previous_freq_change}' to '{selected_frequency_change}'")

        # Save the new selection
        _user_data()[user_id]['frequency_change'] = selected_frequency_change

        # Remove current question marker
        _user_data()[user_id].pop('current_question', None)

        # Notify user of selection
        bot.answer_callback_query(
            call.id, f"{messages[language]['selected']} {selected_frequency_change}")
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None)
        bot.send_message(
            chat_id,
            f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_frequency_change)}</i>",
            parse_mode='HTML')

        # Check for "didn't visit before invasion" option
        didnt_visit_options = [
            "I didn't visit this place before the invasion",
            "Не відвідував(ла) це місце до вторгнення"
        ]

        # Clear dependent fields if appropriate
        if previous_freq_change != selected_frequency_change:
            clear_dependent_fields(
                user_id,
                'frequency_change',
                previous_freq_change,
                selected_frequency_change)

        # Special handling for "didn't visit before" responses
        if selected_frequency_change in didnt_visit_options:
            # Set a consistent value for noticed_changes for data integrity
            _user_data()[user_id]['noticed_changes'] = selected_frequency_change

        # Determine next question based on modification state
        if _user_data()[user_id].get('modifying'):
            if selected_frequency_change in didnt_visit_options:
                # Skip noticed_changes and go to final confirmation
                _user_data()[user_id].pop('modifying')
                _user_data()[user_id].pop('modifying_field', None)
                ask_final_confirmation(chat_id, user_id, language)
            else:
                # If noticed_changes not already answered or we're directly
                # modifying frequency_change, proceed to ask it.
                ask_noticed_changes(chat_id, user_id, language)
        else:
            # Normal flow if not modifying
            if selected_frequency_change in didnt_visit_options:
                # Skip to wishlist question
                ask_wishlist(chat_id, user_id, language)
            else:
                ask_noticed_changes(chat_id, user_id, language)
    except Exception as e:
        logging.exception(f"Error in handle_frequency_change_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))




# Noticed changes and changes details handlers
def ask_noticed_changes(chat_id, user_id, language):
    """
    Asks if the user has noticed any changes since the full-scale invasion.
    """
    try:
        # Reset noticed_changes data
        _user_data()[user_id]['noticed_changes'] = ''
        _user_data()[user_id]['current_question'] = 'noticed_changes'

        options = messages[language]['options']['noticed_changes']
        inline_kb = types.InlineKeyboardMarkup(row_width=1)

        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"noticed_changes_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)

        # Use the question text directly
        question_text = messages[language]['changes_question']

        bot.send_message(
            chat_id,
            question_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_noticed_changes: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('noticed_changes_'))
def handle_noticed_changes_selection(call):
    """
    Handles user selection for noticed changes question.
    """
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']

        options = messages[language]['options']['noticed_changes']
        try:
            idx = callback_index(call.data, "noticed_changes", options)
        except (ValueError, IndexError):
            safe_answer_callback(
                call, messages[language].get(
                    'invalid_selection', "Invalid selection."))
            return

        selected_change = options[idx]

        # Store temporarily, don't commit until confirmed
        _user_data()[user_id]['temp_noticed_changes'] = selected_change

        # Update keyboard to show selection and add Confirm button
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(options):
            # Mark the selected option
            text = f"✅ {option}" if i == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"noticed_changes_{i}"))

        # Add Confirm/Done button
        done_text = messages[language]['done_button']
        inline_kb.add(
            types.InlineKeyboardButton(
                text=done_text,
                callback_data="confirm_noticed_changes"))

        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb
            )
        except telebot.apihelper.ApiTelegramException as e:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(e):
                logging.exception(
                    f"Error in handle_noticed_changes_selection: {e}")

        # Replace direct call with safe_answer_callback
        safe_answer_callback(
            call, f"{messages[language]['selected']} {selected_change}")
    except Exception as e:
        logging.exception(f"Error in handle_noticed_changes_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data ==
                            "confirm_noticed_changes")
def confirm_noticed_changes(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        anon_id = get_anonymous_id(user_id)

        # Transfer from temp storage to actual storage
        if 'temp_noticed_changes' in _user_data()[user_id]:
            selected_change = _user_data()[user_id]['temp_noticed_changes']
            previous_change = _user_data()[user_id].get('noticed_changes', '')

            # Log if it's a modification
            if _user_data()[user_id].get(
                    'modifying') and previous_change != selected_change:
                flow_logger.info(
                    f"User {anon_id}: Modified noticed changes from '{previous_change}' to '{selected_change}'")

            # Save the new selection
            _user_data()[user_id]['noticed_changes'] = selected_change
            _user_profiles().setdefault(
                user_id, {})['noticed_changes'] = selected_change
            _user_data()[user_id].pop('temp_noticed_changes')

            # Remove current_question marker
            _user_data()[user_id].pop('current_question', None)

            # Clear dependent fields if appropriate
            if previous_change != selected_change:
                cleared_fields = clear_dependent_fields(
                    user_id, 'noticed_changes', previous_change, selected_change)
                if cleared_fields:
                    flow_logger.info(
                        f"User {anon_id}: Cleared fields due to noticed_changes change: {cleared_fields}")

            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, "Response confirmed" if language == 'en' else "Відповідь підтверджено")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Show confirmed response
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_change)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if this option requires change details
            detail_requiring_options = [
                "Yes, positive changes",
                "Yes, negative changes",
                "Так, позитивні зміни",
                "Так, негативні зміни"]

            if selected_change in detail_requiring_options:
                flow_logger.info(
                    f"User {anon_id}: Selected positive/negative changes, asking for details")
                ask_changes_detail(chat_id, user_id, language)
            else:
                if _user_data()[user_id].get('modifying'):
                    _user_data()[user_id].pop('modifying')
                    _user_data()[user_id].pop('modifying_field', None)
                    flow_logger.info(
                        f"User {anon_id}: No notable changes while modifying, returning to final confirmation")
                    ask_final_confirmation(chat_id, user_id, language)
                else:
                    # Skip directly to wishlist before socioeconomic questions
                    flow_logger.info(
                        f"User {anon_id}: No notable changes, skipping to wishlist")
                    ask_wishlist(chat_id, user_id, language)
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_noticed_changes: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def ask_changes_detail(chat_id, user_id, language):
    """
    Asks for details about the changes noticed since the invasion.
    Fourth and final question in the dependent chain.
    Only asked if user reported positive or negative changes.

    Args:
        chat_id (int): Telegram chat ID
        user_id (int): User identifier
        language (str): User's language preference
    """
    try:
        anon_id = get_anonymous_id(user_id)
        flow_logger.info(f"User {anon_id}: Asking changes_detail question")

        _user_data()[user_id]['changes_detail'] = []
        _user_data()[user_id]['custom_changes'] = []
        _user_data()[user_id]['awaiting_multiple_select'] = 'changes_detail'

        # Remove the 'Other' option
        options = messages[language]['options']['changes_detail'][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)

        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"changes_detail_{idx}")
            for idx, option in enumerate(options)
        ]
        # Add Done button by default for better UX with free text input
        done_button = types.InlineKeyboardButton(
            text=messages[language]['done_button'],
            callback_data="changes_detail_done")
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        instruction_text = (
            f"{messages[language]['changes_detail_question']}\n\n"
            f"{'You can also type additional changes here as a text message. ' if language=='en' else 'Ви також можете ввести додаткові зміни як текстове повідомлення. '}"
            f"{'When finished, press Done.' if language=='en' else 'Коли закінчите, натисніть Готово.'}")

        bot.send_message(
            chat_id,
            instruction_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_changes_detail: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('changes_detail_'))
def handle_changes_detail_selection(call):
    """
    Handles user selections for changes detail question.
    Multiple selections are allowed for this question.

    Flow logic:
    1. When "Done" is pressed and modifying: Return to final confirmation
    2. When "Done" is pressed and first time: Proceed to wishlist
    3. Otherwise toggle selection of options
    """
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        anon_id = get_anonymous_id(user_id)

        # Remove the 'Other' option
        options = messages[language]['options']['changes_detail'][:-1]
        data = callback_suffix(call.data, "changes_detail")

        if data == 'done':
            if not _user_data()[user_id]['changes_detail'] and not _user_data()[user_id].get(
                    'custom_changes', []):
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call,
                    messages[language].get(
                        'please_select_at_least_one',
                        "Please select at least one option or type your own."))
                return

            # Remove the inline keyboard
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None
            )

            # Combine selected options and custom inputs
            all_changes = _user_data()[user_id]['changes_detail'] + \
                _user_data()[user_id].get('custom_changes', [])
            changes = '; '.join(escape_html(change) for change in all_changes)

            # Log the final selection with anonymous ID
            flow_logger.info(
                f"User {anon_id}: Completed changes_detail with selections: {all_changes}")

            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{changes}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select
            _user_data()[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if we're in modification mode
            if _user_data()[user_id].get('modifying'):
                _user_data()[user_id].pop('modifying')
                _user_data()[user_id].pop('modifying_field', None)
                flow_logger.info(
                    f"User {anon_id}: In modification flow, returning to final confirmation")
                ask_final_confirmation(chat_id, user_id, language)
            else:
                # Proceed to wishlist question before socioeconomic questions
                flow_logger.info(
                    f"User {anon_id}: Proceeding to wishlist question")
                ask_wishlist(chat_id, user_id, language)
        else:
            try:
                idx = callback_index(call.data, "changes_detail", options)
            except (ValueError, IndexError):
                safe_answer_callback(
                    call, messages[language].get(
                        'invalid_selection', "Invalid selection."))
                return

            selected_option = options[idx]

            # Toggle selection
            if selected_option in _user_data()[user_id]['changes_detail']:
                _user_data()[user_id]['changes_detail'].remove(selected_option)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['unselected']} {selected_option}")
                flow_logger.info(
                    f"User {anon_id}: Unselected changes_detail option: {selected_option}")
            else:
                _user_data()[user_id]['changes_detail'].append(selected_option)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['selected']} {selected_option}")
                flow_logger.info(
                    f"User {anon_id}: Selected changes_detail option: {selected_option}")

            update_changes_detail_selection_keyboard(
                call.message, user_id, language)
    except Exception as e:
        logging.exception(f"Error in handle_changes_detail_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def update_changes_detail_selection_keyboard(message, user_id, language):
    """
    Updates the keyboard for changes detail selection to reflect current choices.

    Args:
        message (telebot.types.Message): The message containing the keyboard
        user_id (int): User identifier
        language (str): User's language preference
    """
    try:
        # Remove the 'Other' option
        options = messages[language]['options']['changes_detail'][:-1]
        selected_options = _user_data()[user_id]['changes_detail']
        custom_changes = _user_data()[user_id].get('custom_changes', [])

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = []
        for idx, option in enumerate(options):
            if option in selected_options:
                button_text = f"✅ {option}"
            else:
                button_text = option
            callback_data = f"changes_detail_{idx}"
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data))

        # Only add the Done button if at least one selection has been made
        if selected_options or custom_changes:
            done_button = types.InlineKeyboardButton(
                text=messages[language]['done_button'],
                callback_data="changes_detail_done")
            inline_kb.add(*buttons)
            inline_kb.add(done_button)
        else:
            inline_kb.add(*buttons)

        try:
            bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=inline_kb)
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e):
                # For other exceptions, log and notify the user
                logging.exception(
                    f"Error in update_changes_detail_selection_keyboard: {e}")
    except Exception as e:
        logging.exception(
            f"Error in update_changes_detail_selection_keyboard: {e}")
        bot.send_message(
            message.chat.id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))



# Wishlist handler modifications
def ask_wishlist(chat_id, user_id, language):
    """
    Asks the user about desired improvements to the place.
    This question follows after the dependent question chain.
    """
    try:
        anon_id = get_anonymous_id(user_id)
        flow_logger.info(f"User {anon_id}: Asking wishlist question")

        # Clear old values if any
        _user_data()[user_id]['wishlist'] = []
        _user_data()[user_id]['custom_wishlist'] = []
        _user_data()[user_id]['awaiting_multiple_select'] = 'wishlist'

        # Fixed: Include all options except the second-to-last one (which is
        # "Other")
        all_options = messages[language]['options']['wishlist']
        # Get all options except the last one (Other)
        options = all_options[:-1]

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"wishlist_{idx}") for idx,
            option in enumerate(options)]
        # Add Done button by default for better UX with free text input
        done_button = types.InlineKeyboardButton(
            text=messages[language]['done_button'],
            callback_data="wishlist_done")
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        instruction_text = (
            f"{messages[language]['wishlist_question']}\n\n"
            f"{'You can also type your own suggestion as a text message. ' if language=='en' else 'Ви також можете ввести власний варіант у полі введення тексту. '}"
            f"{'When finished, press Done.' if language=='en' else 'Коли закінчите, натисніть Готово.'}")

        bot.send_message(chat_id, instruction_text, reply_markup=inline_kb)
    except Exception as e:
        logging.exception(f"Error in ask_wishlist: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data.startswith('wishlist_'))
def handle_wishlist_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        data = callback_suffix(call.data, "wishlist")

        # Use the same options list as in ask_wishlist
        all_options = messages[language]['options']['wishlist']
        # Get all options except the last one (Other)
        options = all_options[:-1]

        if data == 'done':
            if not _user_data()[user_id]['wishlist'] and not _user_data()[user_id].get(
                    'custom_wishlist', []):
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call,
                    messages[language].get(
                        'please_select_at_least_one',
                        "Please select at least one option or type your own."))
                return

            # Remove the inline keyboard
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Combine selected options and custom inputs
            all_wishlist = _user_data()[user_id]['wishlist'] + \
                _user_data()[user_id].get('custom_wishlist', [])
            selected = '; '.join(all_wishlist)
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected)}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select
            _user_data()[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            if _user_data()[user_id].get('modifying'):
                _user_data()[user_id].pop('modifying')
                ask_final_confirmation(chat_id, user_id, language)
            else:
                # Proceed to socioeconomic questions
                ask_age(chat_id, user_id, language)
        else:
            try:
                idx = callback_index(call.data, "wishlist", options)
            except (ValueError, IndexError):
                safe_answer_callback(
                    call, messages[language]['invalid_selection'])
                return

            choice = options[idx]

            # Toggle selection
            if choice in _user_data()[user_id]['wishlist']:
                _user_data()[user_id]['wishlist'].remove(choice)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['unselected']} {choice}")
            else:
                _user_data()[user_id]['wishlist'].append(choice)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['selected']} {choice}")

            update_wishlist_keyboard(call.message, user_id, language, options)
    except Exception as e:
        logging.exception(f"Error in handle_wishlist_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def update_wishlist_keyboard(message, user_id, language, options):
    try:
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        selected_options = _user_data()[user_id]['wishlist']
        custom_wishlist = _user_data()[user_id].get('custom_wishlist', [])

        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option in selected_options else option
            callback_data = f"wishlist_{idx}"
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data))

        # Only add the Done button if at least one selection has been made
        if selected_options or custom_wishlist:
            done_button = types.InlineKeyboardButton(
                text=messages[language]['done_button'],
                callback_data="wishlist_done")
            inline_kb.add(*buttons)
            inline_kb.add(done_button)
        else:
            inline_kb.add(*buttons)

        try:
            bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=inline_kb)
        except telebot.apihelper.ApiTelegramException as e:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(e):
                logging.exception(f"Error in update_wishlist_keyboard: {e}")
    except Exception as e:
        logging.exception(f"Error in update_wishlist_keyboard: {e}")



# Socioeconomic questions
def ask_age(chat_id, user_id, language):
    try:
        if not _user_data()[user_id].get('modifying'):
            if user_id in _user_profiles() and 'age' in _user_profiles()[user_id]:
                _user_data()[user_id]['age'] = _user_profiles()[user_id]['age']
                ask_gender(chat_id, user_id, language)
                return

        # Single-select question, set current_question
        _user_data()[user_id]['current_question'] = 'age'
        options = messages[language]['options']['age']
        inline_kb = create_inline_keyboard(options, 'age', single_select=True)

        # Use the question text directly
        question_text = messages[language]['age_question']

        bot.send_message(
            chat_id,
            question_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_age: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


@bot.callback_query_handler(func=lambda call: call.data.startswith('age_'))
def handle_age_selection(call):
    try:
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
                language = _user_data()[user_id]['language']
            else:
                # Cannot proceed without language
                bot.answer_callback_query(
                    call.id, "Please start again with /start")
                bot.send_message(
                    chat_id,
                    "Session expired. Please use /start to begin.\nСесія закінчилася. Будь ласка, використайте /start для початку.")
                return
        else:
            language = _user_data()[user_id]['language']

        options = messages[language]['options']['age']
        try:
            idx = callback_index(call.data, "age", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language].get(
                    'invalid_selection', "Invalid selection."))
            return

        selected_age = options[idx]

        # Store temporarily, don't commit until confirmed
        _user_data()[user_id]['temp_age'] = selected_age

        # Update keyboard to show selection and add Confirm button
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(options):
            # Mark the selected option
            text = f"✅ {option}" if i == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"age_{i}"))

        # Add Confirm/Done button
        done_text = messages[language]['done_button']
        inline_kb.add(
            types.InlineKeyboardButton(
                text=done_text,
                callback_data="confirm_age"))

        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb
            )
        except telebot.apihelper.ApiTelegramException as e:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(e):
                logging.exception(f"Error in handle_age_selection: {e}")

        # Notify user of selection (but not confirmation yet)
        bot.answer_callback_query(
            call.id, f"{messages[language]['selected']} {selected_age}")
    except Exception as e:
        logging.exception(f"Error in handle_age_selection: {e}")
        try:
            # Safely get language with a fallback
            language = _user_data().get(user_id, {}).get('language', 'en')
            error_msg = messages[language].get(
                'error_occurred', "An error occurred. Please try again later.")
        except Exception:
            # Ultimate fallback if everything else fails
            error_msg = "An error occurred. Please try again later. / Виникла помилка. Будь ласка, спробуйте пізніше."

        try:
            bot.send_message(chat_id, error_msg)
        except Exception:
            logging.critical("Failed to send error message to user")


@bot.callback_query_handler(func=lambda call: call.data == "confirm_age")
def confirm_age(call):
    try:
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
                language = _user_data()[user_id]['language']
            else:
                # Cannot proceed without language
                bot.answer_callback_query(
                    call.id, "Please start again with /start")
                bot.send_message(
                    chat_id,
                    "Session expired. Please use /start to begin.\nСесія закінчилася. Будь ласка, використайте /start для початку.")
                return
        else:
            language = _user_data()[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_age' in _user_data()[user_id]:
            selected_age = _user_data()[user_id]['temp_age']
            _user_data()[user_id]['age'] = selected_age
            _user_profiles().setdefault(user_id, {})['age'] = selected_age
            _user_data()[user_id].pop('temp_age')

            # Remove current_question marker
            _user_data()[user_id].pop('current_question', None)

            # Confirm to user
            bot.answer_callback_query(
                call.id, "Response confirmed" if language == 'en' else "Відповідь підтверджено")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Show confirmed response
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_age)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            ask_gender(chat_id, user_id, language)
        else:
            bot.answer_callback_query(
                call.id,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_age: {e}")
        try:
            # Safely get language with a fallback
            language = _user_data().get(user_id, {}).get('language', 'en')
            error_msg = messages[language].get(
                'error_occurred', "An error occurred. Please try again later.")
        except Exception:
            # Ultimate fallback if everything else fails
            error_msg = "An error occurred. Please try again later. / Виникла помилка. Будь ласка, спробуйте пізніше."

        try:
            bot.send_message(chat_id, error_msg)
        except Exception:
            logging.critical("Failed to send error message to user")


def ask_gender(chat_id, user_id, language):
    try:
        if not _user_data()[user_id].get('modifying'):
            if user_id in _user_profiles() and 'gender' in _user_profiles()[user_id]:
                _user_data()[user_id]['gender'] = _user_profiles()[user_id]['gender']
                ask_occupation(chat_id, user_id, language)
                return

        _user_data()[user_id]['current_question'] = 'gender'
        options = messages[language]['options']['gender']
        inline_kb = create_inline_keyboard(
            options, 'gender', single_select=True)

        # Use the question text directly
        question_text = messages[language]['gender_question']

        bot.send_message(
            chat_id,
            question_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_gender: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


@bot.callback_query_handler(func=lambda call: call.data.startswith('gender_'))
def handle_gender_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        options = messages[language]['options']['gender']
        try:
            idx = callback_index(call.data, "gender", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
            return

        selected_gender = options[idx]

        # Store temporarily, don't commit until confirmed
        _user_data()[user_id]['temp_gender'] = selected_gender

        # Update keyboard to show selection and add Confirm button
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(options):
            # Mark the selected option
            text = f"✅ {option}" if i == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text, callback_data=f"gender_{i}"))

        # Add Confirm/Done button
        done_text = messages[language]['done_button']
        inline_kb.add(
            types.InlineKeyboardButton(
                text=done_text,
                callback_data="confirm_gender"))

        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb
            )
        except telebot.apihelper.ApiTelegramException as e:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(e):
                logging.exception(f"Error in handle_gender_selection: {e}")

        # Notify user of selection (but not confirmation yet)
        bot.answer_callback_query(
            call.id, f"{messages[language]['selected']} {selected_gender}")
    except Exception as e:
        logging.exception(f"Error in handle_gender_selection: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


@bot.callback_query_handler(func=lambda call: call.data == "confirm_gender")
def confirm_gender(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_gender' in _user_data()[user_id]:
            selected_gender = _user_data()[user_id]['temp_gender']
            _user_data()[user_id]['gender'] = selected_gender
            _user_profiles().setdefault(user_id, {})['gender'] = selected_gender
            _user_data()[user_id].pop('temp_gender')

            # Remove current_question marker
            _user_data()[user_id].pop('current_question', None)

            # Confirm to user
            bot.answer_callback_query(
                call.id, "Response confirmed" if language == 'en' else "Відповідь підтверджено")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Show confirmed response
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_gender)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            if _user_data()[user_id].get('modifying'):
                field_modified = _user_data()[user_id].get('modifying_field')
                _user_data()[user_id].pop('modifying', None)
                _user_data()[user_id].pop('modifying_field', None)

                if field_modified != 'description':
                    ask_final_confirmation(chat_id, user_id, language)
                else:
                    ask_description(chat_id, user_id, language)
            else:
                ask_occupation(chat_id, user_id, language)
        else:
            bot.answer_callback_query(
                call.id,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_gender: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


def ask_occupation(chat_id, user_id, language):
    try:
        if not _user_data()[user_id].get('modifying'):
            if user_id in _user_profiles() and 'occupation' in _user_profiles()[user_id]:
                _user_data()[user_id]['occupation'] = _user_profiles()[user_id]['occupation']
                ask_income(chat_id, user_id, language)
                return

        _user_data()[user_id]['current_question'] = 'occupation'
        options = messages[language]['options']['occupation']
        inline_kb = create_inline_keyboard(
            options, 'occupation', single_select=True)

        # Use the question text directly
        question_text = messages[language]['occupation_question']

        bot.send_message(
            chat_id,
            question_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_occupation: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


@bot.callback_query_handler(func=lambda call: call.data.startswith('occupation_'))
def handle_occupation_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        options = messages[language]['options']['occupation']
        try:
            idx = callback_index(call.data, "occupation", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
            return

        selected_occupation = options[idx]

        # Store temporarily, don't commit until confirmed
        _user_data()[user_id]['temp_occupation'] = selected_occupation

        # Update keyboard to show selection and add Confirm button
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(options):
            # Mark the selected option
            text = f"✅ {option}" if i == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"occupation_{i}"))

        # Add Confirm/Done button
        done_text = messages[language]['done_button']
        inline_kb.add(
            types.InlineKeyboardButton(
                text=done_text,
                callback_data="confirm_occupation"))

        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb
            )
        except telebot.apihelper.ApiTelegramException as e:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(e):
                logging.exception(f"Error in handle_occupation_selection: {e}")

        # Notify user of selection (but not confirmation yet)
        bot.answer_callback_query(
            call.id, f"{messages[language]['selected']} {selected_occupation}")
    except Exception as e:
        logging.exception(f"Error in handle_occupation_selection: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


@bot.callback_query_handler(func=lambda call: call.data ==
                            "confirm_occupation")
def confirm_occupation(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_occupation' in _user_data()[user_id]:
            selected_occupation = _user_data()[user_id]['temp_occupation']
            _user_data()[user_id]['occupation'] = selected_occupation
            _user_profiles().setdefault(
                user_id, {})['occupation'] = selected_occupation
            _user_data()[user_id].pop('temp_occupation')

            # Remove current_question marker
            _user_data()[user_id].pop('current_question', None)

            # Confirm to user
            bot.answer_callback_query(
                call.id, "Response confirmed" if language == 'en' else "Відповідь підтверджено")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Show confirmed response
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_occupation)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            if _user_data()[user_id].get('modifying'):
                field_modified = _user_data()[user_id].get('modifying_field')
                _user_data()[user_id].pop('modifying')
                _user_data()[user_id].pop('modifying_field', None)

                if field_modified != 'description':
                    ask_final_confirmation(chat_id, user_id, language)
                else:
                    ask_description(chat_id, user_id, language)
            else:
                ask_income(chat_id, user_id, language)
        else:
            bot.answer_callback_query(
                call.id,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_occupation: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])



# Income and Kremenchuk handlers
def ask_income(chat_id, user_id, language):
    try:
        if not _user_data()[user_id].get('modifying'):
            if user_id in _user_profiles() and 'income' in _user_profiles()[user_id]:
                _user_data()[user_id]['income'] = _user_profiles()[user_id]['income']
                # Always check if kremenchuk is already stored in _user_profiles()
                if 'kremenchuk' in _user_profiles()[user_id]:
                    _user_data()[user_id]['kremenchuk'] = _user_profiles()[user_id]['kremenchuk']
                    # Skip to description directly
                    ask_description(chat_id, user_id, language)
                    return
                else:
                    # Ask kremenchuk only once as part of socioeconomic
                    # questions
                    ask_kremenchuk(chat_id, user_id, language)
                    return

        _user_data()[user_id]['current_question'] = 'income'
        options = messages[language]['options']['income']
        inline_kb = create_inline_keyboard(
            options, 'income', single_select=True)

        # Use the question text directly
        question_text = messages[language]['income_question']

        bot.send_message(
            chat_id,
            question_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_income: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data.startswith('income_'))
def handle_income_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        options = messages[language]['options']['income']
        try:
            idx = callback_index(call.data, "income", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
            return

        selected_income = options[idx]

        # Store temporarily, don't commit until confirmed
        _user_data()[user_id]['temp_income'] = selected_income

        # Update keyboard to show selection and add Confirm button
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(options):
            # Mark the selected option
            text = f"✅ {option}" if i == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text, callback_data=f"income_{i}"))

        # Add Confirm/Done button
        done_text = messages[language]['done_button']
        inline_kb.add(
            types.InlineKeyboardButton(
                text=done_text,
                callback_data="confirm_income"))

        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb
            )
        except telebot.apihelper.ApiTelegramException as e:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(e):
                logging.exception(f"Error in handle_income_selection: {e}")

        # Notify user of selection (but not confirmation yet)
        bot.answer_callback_query(
            call.id, f"{messages[language]['selected']} {selected_income}")
    except Exception as e:
        logging.exception(f"Error in handle_income_selection: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


@bot.callback_query_handler(func=lambda call: call.data == "confirm_income")
def confirm_income(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_income' in _user_data()[user_id]:
            selected_income = _user_data()[user_id]['temp_income']
            _user_data()[user_id]['income'] = selected_income
            _user_profiles().setdefault(user_id, {})['income'] = selected_income
            _user_data()[user_id].pop('temp_income')

            # Remove current_question marker
            _user_data()[user_id].pop('current_question', None)

            # Confirm to user
            bot.answer_callback_query(
                call.id, "Response confirmed" if language == 'en' else "Відповідь підтверджено")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Show confirmed response
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_income)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            if _user_data()[user_id].get('modifying'):
                field_modified = _user_data()[user_id].get('modifying_field')
                _user_data()[user_id].pop('modifying')
                _user_data()[user_id].pop('modifying_field', None)

                if field_modified != 'description':
                    ask_final_confirmation(chat_id, user_id, language)
                    return
                else:
                    ask_description(chat_id, user_id, language)
            else:
                # Check if kremenchuk has already been asked once
                if user_id in _user_profiles() and 'kremenchuk' in _user_profiles()[user_id]:
                    # If already asked once, just use the stored value and go
                    # to description
                    _user_data()[user_id]['kremenchuk'] = _user_profiles()[user_id]['kremenchuk']
                    ask_description(chat_id, user_id, language)
                else:
                    # Ask kremenchuk only once as part of socioeconomic
                    # questions
                    ask_kremenchuk(chat_id, user_id, language)
        else:
            bot.answer_callback_query(
                call.id,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_income: {e}")
        bot.send_message(chat_id, messages[language]['error_occurred'])


# Kremenchuk handler modifications
def ask_kremenchuk(chat_id, user_id, language):
    try:
        _user_data()[user_id]['kremenchuk'] = ''
        _user_data()[user_id]['custom_kremenchuk'] = []
        _user_data()[user_id]['awaiting_multiple_select'] = 'kremenchuk'

        # Remove the 'Other' option but keep "Prefer not to disclose"
        options = messages[language]['options']['kremenchuk'][:-
                                                              2] + messages[language]['options']['kremenchuk'][-1:]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)

        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"kremenchuk_{idx}")
            for idx, option in enumerate(options)
        ]
        # Add Done button by default for better UX with free text input
        done_button = types.InlineKeyboardButton(
            text=messages[language]['done_button'],
            callback_data="kremenchuk_done")
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        instruction_text = (
            f"{messages[language]['kremenchuk_question']}\n\n"
            f"{'You can also type your own response as a text message. ' if language=='en' else 'Ви також можете ввести власний варіант у полі введення тексту. '}"
            f"{'When finished, press Done.' if language=='en' else 'Коли закінчите, натисніть Готово.'}")

        bot.send_message(
            chat_id,
            instruction_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_kremenchuk: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data.startswith('kremenchuk_'))
def handle_kremenchuk_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = _user_data()[user_id]['language']
        data = callback_suffix(call.data, "kremenchuk")
        options = messages[language]['options']['kremenchuk'][:- \
            2] + messages[language]['options']['kremenchuk'][-1:]

        if data == 'done':
            if not _user_data()[user_id]['kremenchuk'] and not _user_data()[user_id].get(
                    'custom_kremenchuk', []):
                safe_answer_callback(
                    call,
                    messages[language].get(
                        'please_select_at_least_one',
                        "Please select at least one option or type your own."))
                return

            # Remove the inline keyboard
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Combine kremenchuk and custom_kremenchuk for display
            kremenchuk_value = _user_data()[user_id]['kremenchuk']
            custom_values = _user_data()[user_id].get('custom_kremenchuk', [])

            all_values = []
            if kremenchuk_value:
                all_values.append(kremenchuk_value)
            all_values.extend(custom_values)

            selected_text = '; '.join(all_values)

            # Save to _user_profiles()
            if kremenchuk_value:
                _user_profiles().setdefault(
                    user_id, {})['kremenchuk'] = kremenchuk_value

            # Show user's selections
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_text)}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select state
            _user_data()[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if we're in modifying mode
            if _user_data()[user_id].get('modifying'):
                _user_data()[user_id].pop('modifying')
                _user_data()[user_id].pop('modifying_field', None)
                ask_final_confirmation(chat_id, user_id, language)
            else:
                # Move on to description
                ask_description(chat_id, user_id, language)

        else:
            try:
                idx = callback_index(call.data, "kremenchuk", options)
            except (ValueError, IndexError):
                safe_answer_callback(
                    call, messages[language].get(
                        'invalid_selection', "Invalid selection."))
                return

            selected_kremenchuk = options[idx]

            # Set the selection
            _user_data()[user_id]['kremenchuk'] = selected_kremenchuk

            safe_answer_callback(
                call, f"{messages[language]['selected']} {selected_kremenchuk}")

            # Update the keyboard to show selection
            update_kremenchuk_keyboard(call.message, user_id, language, options)
    except Exception as e:
        logging.exception(f"Error in handle_kremenchuk_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def update_kremenchuk_keyboard(message, user_id, language, options):
    try:
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        selected_option = _user_data()[user_id].get('kremenchuk', '')
        custom_kremenchuk = _user_data()[user_id].get('custom_kremenchuk', [])

        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option == selected_option else option
            callback_data = f"kremenchuk_{idx}"
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data))

        # Only add the Done button if at least one selection has been made
        if selected_option or custom_kremenchuk:
            done_button = types.InlineKeyboardButton(
                text=messages[language]['done_button'],
                callback_data="kremenchuk_done")
            inline_kb.add(*buttons)
            inline_kb.add(done_button)
        else:
            inline_kb.add(*buttons)

        try:
            bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=inline_kb)
        except telebot.apihelper.ApiTelegramException as e:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(e):
                logging.exception(f"Error in update_kremenchuk_keyboard: {e}")
    except Exception as e:
        logging.exception(f"Error in update_kremenchuk_keyboard: {e}")



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


@bot.callback_query_handler(func=lambda call: call.data == 'description_skip')
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
def ask_final_confirmation(chat_id, user_id, language):
    """
    Shows a summary of all responses and asks for confirmation.
    This is the convergence point after all modifications.
    """
    try:
        # Ensure kremenchuk is loaded from profiles if available
        if 'kremenchuk' not in _user_data()[user_id] and user_id in _user_profiles() and 'kremenchuk' in _user_profiles()[user_id]:
            _user_data()[user_id]['kremenchuk'] = _user_profiles()[user_id]['kremenchuk']

        # Display a header message
        header_message = (
            "Here's a summary of your responses. Please review them carefully:" if language == 'en' else
            "Ось підсумок ваших відповідей. Будь ласка, уважно перегляньте їх:"
        )
        bot.send_message(chat_id, header_message)

        # Add a small delay for better UX
        time.sleep(0.5)

        # Display the user's responses
        responses_text = get_responses_text(user_id, language)
        bot.send_message(chat_id, responses_text, parse_mode='HTML')

        # Add another small delay for better UX
        time.sleep(0.5)

        # Ask if the user wants to modify any responses
        options = [messages[language]['modify_responses'],
                   messages[language]['confirm_submission']]
        inline_kb = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"final_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)

        confirmation_text = (
            "Is this information correct? You can modify any response or confirm submission." if language == 'en' else
            "Чи правильна ця інформація? Ви можете змінити будь-яку відповідь або підтвердити подання."
        )

        bot.send_message(
            chat_id,
            confirmation_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_final_confirmation: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def get_responses_text(user_id, language):
    try:
        responses = _user_data()[user_id]
        label_mapping = messages[language]['labels']

        # Ensure visitor_type and duration_visit labels exist
        if 'visitor_type' not in label_mapping:
            label_mapping['visitor_type'] = "Type of visitors" if language == 'en' else "Тип відвідувачів"
        if 'duration_visit' not in label_mapping:
            label_mapping['duration_visit'] = "Duration of visit" if language == 'en' else "Тривалість відвідування"

        # Remove frequency_change from field_order
        field_order = [
            'location',
            'purpose_visit',
            'enjoyment',
            'visitor_type',
            'duration_visit',
            'accessibility',
            'regularity',
            'noticed_changes',
            'changes_detail',
            'wishlist',
            'kremenchuk',
            'description',
            'age',
            'gender',
            'occupation',
            'income'
        ]

        latitude_label = "Latitude" if language == 'en' else "Широта"
        longitude_label = "Longitude" if language == 'en' else "Довгота"
        skipped_text = "Skipped" if language == 'en' else "Пропущено"
        voice_submitted_text = "Voice message submitted." if language == 'en' else "Голосове повідомлення надіслано."

        lines = []

        for field in field_order:
            if field == 'location' and 'location' in responses:
                loc = responses['location']
                loc_label = label_mapping.get(
                    'location', 'Location' if language == 'en' else 'Локація')
                if loc.get('venue_title'):
                    lines.append(
                        f"<b>{loc_label}:</b> {escape_html(loc['venue_title'])}, {escape_html(loc['venue_address'])}")
                else:
                    lat = loc.get('latitude', '')
                    lon = loc.get('longitude', '')
                    lines.append(
                        f"<b>{loc_label}:</b> {latitude_label} {lat}, {longitude_label} {lon}")

            elif field == 'purpose_visit' and 'purpose_visit' in responses:
                # Merge custom_purposes if available
                predefined = responses['purpose_visit'] if isinstance(
                    responses['purpose_visit'], list) else [responses['purpose_visit']]
                custom = responses.get('custom_purposes', [])
                all_purposes = predefined + custom
                purposes = '; '.join(all_purposes)
                label = label_mapping.get(
                    'purpose_visit',
                    'Purpose of visit' if language == 'en' else 'Мета візиту')
                lines.append(f"<b>{label}:</b> {escape_html(purposes)}")

            elif field == 'visitor_type' and 'visitor_type' in responses:
                # Merge custom_visitor_types if available
                predefined = responses['visitor_type'] if isinstance(
                    responses['visitor_type'], list) else [responses['visitor_type']]
                custom = responses.get('custom_visitor_types', [])
                all_vtypes = predefined + custom
                vtypes = '; '.join(all_vtypes)
                vlabel = label_mapping.get(
                    'visitor_type', 'Type of visitors' if language == 'en' else 'Тип відвідувачів')
                lines.append(f"<b>{vlabel}:</b> {escape_html(vtypes)}")

            elif field == 'accessibility' and 'accessibility' in responses:
                # Merge custom_accessibility
                predefined_acc = responses['accessibility'] if isinstance(responses['accessibility'], list) else (
                    [responses['accessibility']] if responses['accessibility'] else [])
                custom_acc = responses.get('custom_accessibility', [])
                all_acc = predefined_acc + custom_acc
                acc = '; '.join(all_acc)
                alabel = label_mapping.get(
                    'accessibility',
                    'Accessibility' if language == 'en' else 'Доступність')
                lines.append(f"<b>{alabel}:</b> {escape_html(acc)}")

            elif field == 'changes_detail' and 'changes_detail' in responses:
                # Merge custom_changes
                predefined_cd = responses['changes_detail'] if isinstance(
                    responses['changes_detail'], list) else [responses['changes_detail']]
                custom_cd = responses.get('custom_changes', [])
                all_cd = predefined_cd + custom_cd
                changes = '; '.join(all_cd)
                c_label = label_mapping.get(
                    'changes_detail',
                    'Changes detail' if language == 'en' else 'Деталі змін')
                lines.append(f"<b>{c_label}:</b> {escape_html(changes)}")

            elif field == 'wishlist' and 'wishlist' in responses:
                # Merge custom_wishlist
                predefined_wl = responses['wishlist'] if isinstance(responses['wishlist'], list) else (
                    [responses['wishlist']] if responses['wishlist'] else [])
                custom_wl = responses.get('custom_wishlist', [])
                all_wl = predefined_wl + custom_wl
                wishlist = '; '.join(all_wl)
                w_label = label_mapping.get(
                    'wishlist',
                    'Improvements wished' if language == 'en' else 'Побажання покращень')
                lines.append(f"<b>{w_label}:</b> {escape_html(wishlist)}")

            elif field == 'kremenchuk' and ('kremenchuk' in responses or 'custom_kremenchuk' in responses):
                # Merge kremenchuk and custom_kremenchuk
                kremenchuk_base = responses.get('kremenchuk', '')
                custom_kremenchuk = responses.get('custom_kremenchuk', [])

                if kremenchuk_base or custom_kremenchuk:
                    all_kremenchuk = []
                    if kremenchuk_base:
                        all_kremenchuk.append(kremenchuk_base)
                    all_kremenchuk.extend(custom_kremenchuk)
                    kremenchuk_text = '; '.join(all_kremenchuk)

                    k_label = label_mapping.get(
                        'kremenchuk',
                        'Time living in Kremenchuk' if language == 'en' else 'Час проживання в Кременчуці')
                    lines.append(
                        f"<b>{k_label}:</b> {escape_html(kremenchuk_text)}")

            elif field == 'description':
                d_label = label_mapping.get(
                    'description', 'Description' if language == 'en' else 'Опис')
                description_text = responses.get('description', '')
                voice_submitted = responses.get('voice_submitted', '')
                description_done = responses.get('description_done', False)

                if voice_submitted:
                    lines.append(f"<b>{d_label}:</b> {voice_submitted_text}")
                elif description_text.strip():
                    lines.append(
                        f"<b>{d_label}:</b> {escape_html(description_text)}")
                else:
                    lines.append(f"<b>{d_label}:</b> {skipped_text}")

            else:
                if field in responses:
                    val = responses[field]
                    flabel = label_mapping.get(
                        field, field.capitalize() if language == 'en' else field.capitalize())
                    if isinstance(val, list):
                        val = '; '.join(val)
                    if val and val.strip():
                        lines.append(f"<b>{flabel}:</b> {escape_html(val)}")
                    else:
                        lines.append(f"<b>{flabel}:</b> ")

        return '\n'.join(lines)

    except Exception as e:
        logging.exception(f"Error in get_responses_text: {e}")
        return "Error retrieving responses."


@bot.callback_query_handler(func=lambda call: call.data.startswith('final_'))
def handle_final_confirmation_choice(call):
    """
    Handles user's decision to confirm or modify their responses.
    """
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        update_activity_timestamp(user_id)

        anon_id = get_anonymous_id(user_id)

        # Ensure language is set
        if user_id not in _user_data() or 'language' not in _user_data()[user_id]:
            if user_id in _user_profiles() and 'language' in _user_profiles()[user_id]:
                _user_data()[user_id]['language'] = _user_profiles()[user_id]['language']
            else:
                bot.send_message(
                    chat_id,
                    "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
                return

        language = _user_data()[user_id]['language']
        choice = callback_suffix(call.data, "final")

        if choice == '0':  # Modify Responses
            # Keep this log as it's modification-related
            flow_logger.info(f"User {anon_id}: Starting modification process")
            # Replace direct call with safe_answer_callback
            safe_answer_callback(call, messages[language]['modify_responses'])
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)
            ask_which_responses_to_modify(chat_id, user_id, language)
        elif choice == '1':  # Confirm Submission
            # Remove logging for normal confirmation flow
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, messages[language]['confirm_submission'])
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Save data
            save_data_and_restart(
                chat_id, user_id, language, restart_survey=False)

            # After saving data, directly ask if user wants to continue or stop
            ask_continue_or_stop(chat_id, user_id, language)

        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, messages[language].get(
                    'invalid_selection', "Invalid selection."))
    except Exception as e:
        logging.exception(f"Error in handle_final_confirmation_choice: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def ask_which_responses_to_modify(chat_id, user_id, language):
    try:
        # Fixed order of fields as used in get_responses_text (without
        # frequency_change)
        field_order = [
            'location',
            'purpose_visit',
            'enjoyment',
            'visitor_type',
            'duration_visit',
            'accessibility',
            'regularity',
            'noticed_changes',
            'changes_detail',
            'wishlist',
            'kremenchuk',
            'description',
            'age',
            'gender',
            'occupation',
            'income'
        ]

        label_mapping = messages[language]['labels']

        # Combine _user_data() and _user_profiles() for existing fields
        combined_data = {
            **_user_profiles().get(user_id, {}), **_user_data()[user_id]}

        # We do not exclude description now so that it will always appear
        # If you still do not want to modify location, keep this. Otherwise
        # remove.
        fields_to_exclude = ['location']

        field_mapping = {}

        for field in field_order:
            if field not in fields_to_exclude:
                # Even if description was skipped, it should appear for modification
                # Check if the field is meaningful: it either exists or we always want it accessible
                # For fields that always appear (like description), we include
                # them regardless of presence.
                if field == 'description':
                    field_mapping[field] = label_mapping.get(
                        field, 'Description' if language == 'en' else 'Опис')
                else:
                    if field in combined_data or field in _user_data()[user_id]:
                        field_mapping[field] = label_mapping.get(
                            field, field.capitalize())
                    else:
                        # For conditional fields: if they do not exist at all, they might not be modifiable
                        # But in this case, we want them if at least once visited
                        # If you want all fields shown even if empty, you can
                        # remove this check
                        if field in label_mapping:
                            field_mapping[field] = label_mapping[field]

        _user_data()[user_id]['field_mapping'] = field_mapping

        # Log which fields are offered for modification with anonymized ID
        anon_id = get_anonymous_id(user_id)
        flow_logger.info(
            f"User {anon_id}: Offered these fields for modification: {list(field_mapping.keys())}")

        # Track dependency chain fields being offered
        dependency_fields = ['regularity', 'noticed_changes', 'changes_detail']
        offered_dependencies = [
            f for f in dependency_fields if f in field_mapping]
        if offered_dependencies:
            dependency_values = {
                f: _user_data()[user_id].get(
                    f, 'not set') for f in offered_dependencies}
            flow_logger.info(
                f"User {anon_id}: Current dependency chain values: {dependency_values}")

        # Create inline keyboard with options
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(text=label, callback_data=f"modify_{field}")
            for field, label in field_mapping.items()
        ]
        done_button = types.InlineKeyboardButton(
            text=messages[language]['done_button'],
            callback_data="modification_done")
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        bot.send_message(
            chat_id,
            messages[language]['select_questions_to_modify'],
            reply_markup=inline_kb
        )

    except Exception as e:
        logging.exception(f"Error in ask_which_responses_to_modify: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


@bot.callback_query_handler(func=lambda call: call.data.startswith(
    'modify_') or call.data == 'modification_done')
def handle_modification_selection_callback(call):
    handle_modification_selection(call)


def handle_modification_selection(call):
    """
    Handles user selection of which question to modify.
    This is the entry point for the modification flow.
    """
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        update_activity_timestamp(user_id)

        language = _user_data()[user_id]['language']
        anon_id = get_anonymous_id(user_id)

        if call.data == 'modification_done':
            # User finished selecting fields to modify
            flow_logger.info(
                f"User {anon_id}: Completed modifications, returning to final confirmation")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)
            ask_final_confirmation(chat_id, user_id, language)
        else:
            # User selected a specific field to modify
            field = callback_suffix(call.data, "modify")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Set modifying state
            _user_data()[user_id]['modifying'] = True
            _user_data()[user_id]['modifying_field'] = field

            # Log the field being modified
            flow_logger.info(f"User {anon_id}: Modifying field: {field}")

            # Define field relationships for documentation
            field_dependencies = get_question_dependencies()

            # Log if modifying a field with dependencies
            if field in field_dependencies:
                dependent_fields = field_dependencies[field]
                # Log current values of the field and its dependents
                current_values = {
                    f: _user_data()[user_id].get(
                        f,
                        'not set') for f in [field] +
                    dependent_fields if f in _user_data()[user_id]}
                flow_logger.info(
                    f"User {anon_id}: Field {field} has dependencies: {dependent_fields}. Current values: {current_values}")

            # Redirect to the appropriate question handler based on field
            if field == 'enjoyment':
                ask_enjoyment(chat_id, user_id, language)
            elif field == 'purpose_visit':
                ask_purpose_visit(chat_id, user_id, language)
            elif field == 'regularity':
                ask_regularity(chat_id, user_id, language)
            elif field == 'accessibility':
                ask_accessibility(chat_id, user_id, language)
            elif field == 'noticed_changes':
                ask_noticed_changes(chat_id, user_id, language)
            elif field == 'changes_detail':
                ask_changes_detail(chat_id, user_id, language)
            elif field == 'wishlist':
                ask_wishlist(chat_id, user_id, language)
            elif field == 'kremenchuk':
                ask_kremenchuk(chat_id, user_id, language)
            elif field == 'age':
                ask_age(chat_id, user_id, language)
            elif field == 'gender':
                ask_gender(chat_id, user_id, language)
            elif field == 'occupation':
                ask_occupation(chat_id, user_id, language)
            elif field == 'income':
                ask_income(chat_id, user_id, language)
            elif field == 'description':
                ask_description(chat_id, user_id, language)
            elif field == 'visitor_type':
                ask_visitor_type(chat_id, user_id, language)
            elif field == 'duration_visit':
                ask_duration(chat_id, user_id, language)
            else:
                bot.send_message(
                    chat_id, messages[language].get(
                        'invalid_selection', "Invalid selection."))
                flow_logger.warning(
                    f"User {anon_id}: Attempted to modify invalid field: {field}")
    except Exception as e:
        logging.exception(f"Error in handle_modification_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))

# Helper functions for anonymization and dependency management


def get_anonymous_id(user_id):
    """
    Get an anonymized identifier for a user.
    Uses nickname exclusively for anonymization.

    Args:
        user_id (int): The user's Telegram ID

    Returns:
        str: Anonymized nickname for logging
    """
    # Always use the nickname if available in _user_data()
    if user_id in _user_data() and 'nickname' in _user_data()[user_id]:
        return _user_data()[user_id]['nickname']

    # If not in _user_data(), check if we can retrieve it from the database
    user_hash = get_user_hash(user_id)
    nickname = get_user_nickname(user_hash)

    if nickname:
        # Store it in _user_data() for future use
        if user_id not in _user_data():
            _user_data()[user_id] = {}
        _user_data()[user_id]['nickname'] = nickname
        return nickname

    # If no nickname exists yet, generate one, save it, and return it
    nickname = generate_unique_nickname()
    save_user_nickname(user_hash, nickname)
    if user_id not in _user_data():
        _user_data()[user_id] = {}
    _user_data()[user_id]['nickname'] = nickname
    return nickname


def get_question_dependencies():
    """
    Returns a dictionary mapping questions to their dependent questions.
    This makes the dependency relationships explicit and centralized.

    Returns:
        dict: Mapping of questions to lists of dependent questions
    """
    return {
        'regularity': ['noticed_changes', 'changes_detail'],
        'noticed_changes': ['changes_detail'],
    }


def requires_follow_up(regularity_response):
    """
    Determines if a regularity response requires noticed_changes follow-up question.

    Args:
        regularity_response (str): The user's response to regularity question

    Returns:
        bool: True if follow-up questions are needed, False otherwise
    """
    if not regularity_response:
        return False

    # Skip options don't require follow-up
    skip_options_en = [
        "One-time visit",
        "Visited before 2022 but not anymore",
        "Prefer not to disclose"
    ]
    skip_options_uk = [
        "Разове відвідування",
        "Відвідував(-ла) до 2022 р., але не зараз",
        "Надаю перевагу не вказувати"
    ]

    # Check if regularity exactly matches any skip options
    for option in skip_options_en + skip_options_uk:
        if option in regularity_response:
            return False

    # If no skip patterns found, follow-up is required
    return True


def skips_changes_questions(frequency_response):
    """
    Determines if a frequency change response should skip the noticed changes question.

    Args:
        frequency_response (str): The user's response to frequency change question

    Returns:
        bool: True if noticed_changes should be skipped, False otherwise
    """
    if not frequency_response:
        return False

    # Didn't visit before invasion responses skip the noticed changes question
    en_skip = ["I didn't visit this place before the invasion"]
    uk_skip = ["Не відвідував(ла) це місце до вторгнення"]

    return (frequency_response in en_skip) or (frequency_response in uk_skip)


def requires_changes_detail(changes_response):
    """
    Determines if a noticed changes response requires detail follow-up.

    Args:
        changes_response (str): The user's response to noticed changes question

    Returns:
        bool: True if detail questions are needed, False otherwise
    """
    if not changes_response:
        return False

    # Positive or negative changes require details
    en_requires = ["Yes, positive changes", "Yes, negative changes"]
    uk_requires = ["Так, позитивні зміни", "Так, негативні зміни"]

    return (
        changes_response in en_requires) or (
        changes_response in uk_requires)


def clear_dependent_fields(user_id, field, old_value, new_value):
    """
    Clears fields that depend on a changed answer when appropriate.
    Only clears dependent fields if the change would invalidate them.
    """
    dependencies = get_question_dependencies()
    cleared_fields = []
    anon_id = get_anonymous_id(user_id)

    # Only process for fields that have dependencies
    if field not in dependencies:
        return cleared_fields

    # Store values before clearing for logging
    fields_to_check = dependencies[field]
    current_values = {f: _user_data()[user_id].get(
        f, 'not set') for f in fields_to_check if f in _user_data()[user_id]}

    # Handle regularity changes
    if field == 'regularity':
        # Define patterns that should clear follow-up questions
        should_clear_patterns = [
            "One-time visit",
            "Разове відвідування",
            "Visited before 2022 but not anymore",
            "Відвідував(-ла) до 2022 р., але не зараз",
            "Prefer not to disclose",
            "Надаю перевагу не вказувати"]

        # Check if the new value is one that should clear dependencies
        should_clear = any(
            pattern in new_value for pattern in should_clear_patterns)

        # If new value should clear dependencies, proceed regardless of old
        # value
        if should_clear:
            flow_logger.info(
                f"User {anon_id}: Clearing dependent fields because regularity changed to '{new_value}'")
            for dep_field in dependencies[field]:
                if dep_field in _user_data()[user_id]:
                    _user_data()[user_id].pop(dep_field, None)
                    cleared_fields.append(dep_field)

                    # If changes_detail is cleared, also clear custom_changes
                    # if present
                    if dep_field == 'changes_detail' and 'custom_changes' in _user_data()[user_id]:
                        _user_data()[user_id].pop('custom_changes', None)
                        cleared_fields.append('custom_changes')

    # Handle noticed_changes changes
    elif field == 'noticed_changes':
        # Define patterns that require detailed changes
        requires_detail_patterns = [
            "Yes, positive changes", "Yes, negative changes",
            "Так, позитивні зміни", "Так, негативні зміни"
        ]

        # Check if old value required details but new value doesn't
        old_requires_detail = any(
            pattern in old_value for pattern in requires_detail_patterns)
        new_requires_detail = any(
            pattern in new_value for pattern in requires_detail_patterns)

        # Clear details if no longer requiring them
        if old_requires_detail and not new_requires_detail:
            if 'changes_detail' in _user_data()[user_id]:
                _user_data()[user_id].pop('changes_detail', None)
                cleared_fields.append('changes_detail')

                # Also clear custom_changes if present
                if 'custom_changes' in _user_data()[user_id]:
                    _user_data()[user_id].pop('custom_changes', None)
                    cleared_fields.append('custom_changes')

    # Only log what was cleared with values if something was actually cleared
    if cleared_fields:
        # Only log when in modification mode or fields are actually cleared
        flow_logger.info(
            f"User {anon_id}: Fields cleared due to modification: {field} changed from '{old_value}' to '{new_value}'")
        flow_logger.info(
            f"User {anon_id}: Cleared fields: {cleared_fields} with previous values: {current_values}")

    return cleared_fields


# Continue or stop handlers
def ask_continue_or_stop(chat_id, user_id, language):
    try:
        options = messages[language]['continue_options']
        inline_kb = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"continue_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)

        nickname = _user_data()[user_id]['nickname']

        # Make the thank you message more prominent
        thank_you_msg = f"<b>{messages[language]['thank_you']}</b>"
        bot.send_message(chat_id, thank_you_msg, parse_mode='HTML')

        # Add a small delay for better UX flow
        time.sleep(0.8)

        # Then ask if they want to continue
        continue_msg = messages[language]['continue_question'].format(
            nickname=f'<b>{escape_html(nickname)}</b>')
        bot.send_message(
            chat_id,
            continue_msg,
            reply_markup=inline_kb,
            parse_mode='HTML'
        )
    except Exception as e:
        logging.exception(f"Error in ask_continue_or_stop: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('continue_'))
def handle_continue_or_stop_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        update_activity_timestamp(user_id)

        # Ensure the user has selected a language
        if user_id not in _user_data() or 'language' not in _user_data()[user_id]:
            if user_id in _user_profiles() and 'language' in _user_profiles()[user_id]:
                _user_data()[user_id] = {
                    'language': _user_profiles()[user_id]['language']}
            else:
                bot.send_message(
                    chat_id,
                    "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
                return

        language = _user_data()[user_id]['language']
        options = messages[language]['continue_options']
        data = callback_suffix(call.data, "continue")

        if data == '0':  # Continue
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, f"{messages[language]['selected']} {options[0]}")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)
            save_data_and_restart(
                chat_id, user_id, language, restart_survey=False)

            send_next_step_prompt(
                chat_id,
                messages[language]['send_location'],
                handle_location_step)

        elif data == '1':  # Stop
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, f"{messages[language]['selected']} {options[1]}")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Create InlineKeyboard with 'Restart' button
            inline_kb = types.InlineKeyboardMarkup()
            restart_button = types.InlineKeyboardButton(
                text=messages[language]['restart_button'], callback_data='restart')
            inline_kb.add(restart_button)

            # Send 'consent_denied' message with 'Restart' button
            bot.send_message(
                chat_id,
                messages[language]['consent_denied'],
                reply_markup=inline_kb,
                parse_mode='HTML'  # Assuming you want to parse HTML here
            )

            save_data_and_restart(
                chat_id, user_id, language, restart_survey=False)
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, messages[language].get(
                    'invalid_selection', "Invalid selection."))
    except Exception as e:
        logging.exception(f"Error in handle_continue_or_stop_selection: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


@bot.message_handler(func=lambda m: True, content_types=['text'])
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

# Updated save_data_and_restart function with better error handling for concurrent use
def save_data_and_restart(chat_id, user_id, language, restart_survey=False):
    try:
        ctx = _ctx()
        user_profile_copy = ctx.sessions.profile_snapshot(user_id)
        user_consent = user_profile_copy.get('consent', False)

        if not user_consent:
            flow_logger.info("Consent denied; skipping response row insert")
            clear_message_ids(user_id)
            if restart_survey:
                send_welcome(
                    chat_id=chat_id,
                    user_id=user_id,
                    start_param='restart')
            return True

        def nickname_provider():
            user_hash = get_user_hash(user_id)
            nickname = get_user_nickname(user_hash)
            if not nickname:
                nickname = generate_unique_nickname()
                save_user_nickname(user_hash, nickname)
            return nickname

        try:
            save_response(
                ctx,
                user_id,
                language,
                nickname_provider=nickname_provider,
            )
        except EncryptionUnavailableError:
            flow_logger.error("Encryption not initialized. Cannot save data securely.")
            safe_send_message(
                chat_id,
                "A security error occurred. Your data could not be saved securely. Please contact support." 
                if language == 'en' else 
                "Сталася помилка безпеки. Ваші дані не могли бути збережені надійно. Зверніться до служби підтримки."
            )
            return False
        except DatabaseSaveError:
            safe_send_message(
                chat_id,
                "A database error occurred. Your data could not be saved. Please try again later."
                if language == 'en' else
                "Сталася помилка бази даних. Ваші дані не могли бути збережені. Будь ласка, спробуйте пізніше."
            )
            return False

        # Clear current experience data using thread-safe method
        with _session_lock():
            if user_id in _user_data():
                experience_keys = [
                    'location', 'enjoyment', 'purpose_visit', 'regularity',
                    'noticed_changes', 'changes_detail', 'wishlist', 'kremenchuk',
                    'description', 'voice_submitted', 'visitor_type', 'duration_visit',
                    'accessibility', 'description_done'  # Added description_done to the list
                ]
                for key in experience_keys:
                    _user_data()[user_id].pop(key, None)

        # Clear tracked message IDs
        clear_message_ids(user_id)

        if restart_survey:
            send_welcome(
                chat_id=chat_id,
                user_id=user_id,
                start_param='restart')
            
        return True

    except Exception as e:
        error_msg = f"Error in save_data_and_restart: {e}"
        logging.exception(error_msg)
        flow_logger.error(error_msg)
        safe_send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred while saving your data. Please try again later.")
        )
        return False

if __name__ == '__main__':
    run()
