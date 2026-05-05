#!/usr/bin/env python
# coding: utf-8



"""Runtime Telegram bot implementation.

This module intentionally preserves the legacy survey behavior while moving
startup work behind `configure_runtime()` and `run()`.
"""

# Imports and configuration
import copy
import os
import logging
import time
import datetime
import threading
import sqlite3
import random
from pathlib import Path

import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException

from .messages import messages
from .pseudonym import hash_user_id
from . import runtime as runtime_module
from .runtime import flow_logger
from .storage import initialize_database as initialize_storage_database
from .telegram_io import (
    callback_index,
    callback_suffix,
    clear_message_ids,
    edit_keyboard,
    escape_html,
    get_message_id,
    handle_callback_error,
    hide_keyboard,
    redacted_coordinate,
    safe_answer_callback,
    safe_send_message,
    send_keyboard_message,
    send_next_step_prompt,
    telegram_retry_after,
)
from .voice import new_voice_filename, safe_nickname_directory


# Configure storage directories
token = runtime_module.token
local_storage_dir = runtime_module.local_storage_dir
voice_files_dir = runtime_module.voice_files_dir
user_hash_salt = runtime_module.user_hash_salt
voice_retention_days = runtime_module.voice_retention_days
cleanup_interval_seconds = runtime_module.cleanup_interval_seconds


# Initialize bot
bot = runtime_module.bot
bot_username = runtime_module.bot_username

# State variables
user_data = {}
user_profiles = {}
# Add at the top with other global variables
user_data_lock = threading.RLock()  # Reentrant lock for all in-memory user session data
user_profiles_lock = user_data_lock  # Keep a single lock for user_data and user_profiles.


# Database setup
db_file = runtime_module.db_file


# Near the top where encryption is initialized
# Replace the current code with:

# Encryption setup
fernet = runtime_module.fernet  # Initialize global variable


# TODO(phase-2): remove when bot.py globals migrate to AppContext.
def _sync_runtime_globals():
    """Mirror runtime module globals used by legacy handler code."""

    global token
    global local_storage_dir
    global voice_files_dir
    global db_file
    global fernet
    global bot
    global bot_username
    global user_hash_salt
    global voice_retention_days
    global cleanup_interval_seconds

    token = runtime_module.token
    local_storage_dir = runtime_module.local_storage_dir
    voice_files_dir = runtime_module.voice_files_dir
    db_file = runtime_module.db_file
    fernet = runtime_module.fernet
    bot = runtime_module.bot
    bot_username = runtime_module.bot_username
    user_hash_salt = runtime_module.user_hash_salt
    voice_retention_days = runtime_module.voice_retention_days
    cleanup_interval_seconds = runtime_module.cleanup_interval_seconds


def configure_runtime(config):
    """Configure global legacy runtime objects for one bot process."""

    configured_bot = runtime_module.configure_runtime(
        config,
        cleanup_stale_sessions=cleanup_stale_sessions,
        safe_get_language=safe_get_language,
        clear_callback_state=clear_callback_state,
    )
    _sync_runtime_globals()
    return configured_bot


def run(config=None):
    """Run the Telegram bot."""

    return runtime_module.run(
        config,
        initialize_database=initialize_database,
        recover_user_sessions=recover_user_sessions,
        cleanup_stale_sessions=cleanup_stale_sessions,
        safe_get_language=safe_get_language,
        clear_callback_state=clear_callback_state,
        after_configure=_sync_runtime_globals,
    )


def get_user_hash(user_id):
    return hash_user_id(user_id, user_hash_salt)


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
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
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
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
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
    """Thread-safe access to user_data."""
    try:
        with user_data_lock:
            if user_id not in user_data:
                user_data[user_id] = {}
            if key is None:
                return user_data[user_id]
            return user_data[user_id].get(key, default)
    except Exception as e:
        flow_logger.error(f"Error in get_user_data: {e}")
        if key is None:
            return {}
        return default

def set_user_data(user_id, key, value):
    """Thread-safe setting of user_data values."""
    try:
        with user_data_lock:
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id][key] = value
        return True
    except Exception as e:
        flow_logger.error(f"Error in set_user_data: {e}")
        return False

def remove_user_data(user_id, key):
    """Thread-safe removal of user_data keys."""
    try:
        with user_data_lock:
            if user_id in user_data and key in user_data[user_id]:
                return user_data[user_id].pop(key)
        return None
    except Exception as e:
        flow_logger.error(f"Error in remove_user_data: {e}")
        return None

def get_user_profile(user_id, key=None, default=None):
    """Thread-safe access to user_profiles."""
    try:
        with user_profiles_lock:
            if user_id not in user_profiles:
                user_profiles[user_id] = {}
            if key is None:
                return user_profiles[user_id]
            return user_profiles[user_id].get(key, default)
    except Exception as e:
        flow_logger.error(f"Error in get_user_profile: {e}")
        if key is None:
            return {}
        return default

def set_user_profile(user_id, key, value):
    """Thread-safe setting of user_profiles values."""
    try:
        with user_profiles_lock:
            if user_id not in user_profiles:
                user_profiles[user_id] = {}
            user_profiles[user_id][key] = value
        return True
    except Exception as e:
        flow_logger.error(f"Error in set_user_profile: {e}")
        return False


def save_user_nickname(user_hash, nickname):
    month_year = datetime.datetime.now().strftime('%Y-%m')
    with sqlite3.connect(db_file, check_same_thread=False) as conn:
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
        # Try user_data first
        if user_id in user_data and 'language' in user_data[user_id]:
            return user_data[user_id]['language']

        # Try user_profiles next
        if user_id in user_profiles and 'language' in user_profiles[user_id]:
            return user_profiles[user_id]['language']

        # Default fallback
        return 'en'
    except Exception:
        # Ultimate fallback
        return 'en'


def clear_callback_state(user_id):
    """Clear transient callback state for a user after a handler error."""

    with user_data_lock:
        if user_id in user_data:
            keys_to_remove = []
            for key in user_data[user_id]:
                if (key.startswith('temp_') or
                    key == 'awaiting_multiple_select' or
                    key == 'current_question' or
                    key == 'modifying' or
                    key == 'modifying_field'):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                user_data[user_id].pop(key, None)


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

    # Ensure user exists in user_data and has language
    if user_id not in user_data or 'language' not in user_data[user_id]:
        # Try to get language from user_profiles
        if user_id in user_profiles and 'language' in user_profiles[user_id]:
            # Initialize user data if needed
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['language'] = user_profiles[user_id]['language']
            return True, user_data[user_id]['language']
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
        return True, user_data[user_id]['language']


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

        # Get a snapshot of current user_data to avoid modification during
        # iteration
        with user_data_lock:
            users_to_recover = list(user_data.keys())
        recovered_count = 0

        for user_id in users_to_recover:
            try:
                # Ensure basic data structures exist
                with user_data_lock:
                    session = user_data.get(user_id, {})
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
        with user_data_lock:
            user_items = list(user_data.items())

        for user_id, data in user_items:
            last_activity = data.get('last_activity_time', 0)
            if last_activity < cutoff_time:
                users_to_remove.append(user_id)

        # Then remove them
        for user_id in users_to_remove:
            try:
                with user_data_lock:
                    user_data.pop(user_id, None)
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
    with user_data_lock:
        if user_id in user_data:
            user_data[user_id]['last_activity_time'] = time.time()
        else:
            # If user doesn't exist in user_data, initialize it
            user_data[user_id] = {'last_activity_time': time.time()}


# Database functions
def initialize_database():
    try:
        initialize_storage_database(Path(db_file))
        flow_logger.info("Database initialized successfully")
    except Exception as e:
        logging.exception(f"Error initializing responses database: {e}")
        raise e

# Start and restart handlers
@bot.callback_query_handler(func=lambda call: call.data == 'restart')
def handle_restart(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        # Acknowledge the restart action
        bot.answer_callback_query(call.id, "Restarting the survey.")

        # Restart the survey by calling send_welcome with 'restart' parameter
        send_welcome(chat_id=chat_id, user_id=user_id, start_param='restart')
    except Exception as e:
        logging.exception(f"Error in handle_restart: {e}")
        bot.send_message(
            chat_id,
            "An error occurred while restarting. Please try again later.")


@bot.message_handler(commands=['start'])
def send_welcome(message=None, chat_id=None, user_id=None, start_param=None):
    try:
        if message:
            chat_id = message.chat.id
            user_id = message.from_user.id
            update_activity_timestamp(user_id)

            # Check if /start has parameters
            if message.text.startswith('/start '):
                start_param = message.text.split(' ', 1)[1]
            else:
                start_param = start_param
        elif chat_id and user_id:
            # start_param is already provided (e.g., 'restart')
            pass
        else:
            # Cannot proceed without chat_id and user_id
            return

        user_hash = get_user_hash(user_id)
        nickname = get_user_nickname(user_hash)
        if not nickname:
            nickname = generate_unique_nickname()
            save_user_nickname(user_hash, nickname)

        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]['nickname'] = nickname

        if start_param == 'restart':
            # Reset experience-related data but keep language and profile data
            keys_to_remove = [
                'location', 'enjoyment', 'purpose_visit', 'regularity',
                'frequency_change', 'noticed_changes', 'changes_detail',
                'wishlist', 'kremenchuk', 'accessibility', 'description',
                'voice_submitted'
            ]
            for key in keys_to_remove:
                user_data[user_id].pop(key, None)

        # Check if user has a language set
        if user_id in user_profiles and 'language' in user_profiles[user_id]:
            language = user_profiles[user_id]['language']
            user_data[user_id]['language'] = language

            # Check if consent is given
            if 'consent' in user_profiles[user_id]:
                if user_profiles[user_id]['consent'] is False:
                    # User previously disagreed, now restarting -> show consent
                    # given message with Continue button
                    user_profiles[user_id]['consent'] = True
                    consent_message = messages[language]['consent_given'].format(
                        nickname=f"<b>{escape_html(nickname)}</b>")
                    inline_kb = types.InlineKeyboardMarkup()
                    continue_text = "Continue" if language == 'en' else "Продовжити"
                    continue_button = types.InlineKeyboardButton(
                        continue_text, callback_data='post_consent_continue')
                    inline_kb.add(continue_button)
                    bot.send_message(
                        chat_id,
                        consent_message,
                        parse_mode='HTML',
                        reply_markup=inline_kb)
                    return
                else:
                    # consent true, show consent given message with Continue button as well
                    # This ensures consistency so user must press Continue
                    consent_message = messages[language]['consent_given'].format(
                        nickname=f"<b>{escape_html(nickname)}</b>")
                    inline_kb = types.InlineKeyboardMarkup()
                    continue_text = "Continue" if language == 'en' else "Продовжити"
                    continue_button = types.InlineKeyboardButton(
                        continue_text, callback_data='post_consent_continue')
                    inline_kb.add(continue_button)
                    bot.send_message(
                        chat_id,
                        consent_message,
                        parse_mode='HTML',
                        reply_markup=inline_kb)
                    return
            else:
                # No consent yet, ask for it
                options = messages[language]['consent_options']
                inline_kb = types.InlineKeyboardMarkup(row_width=2)
                buttons = [
                    types.InlineKeyboardButton(
                        text=opt,
                        callback_data=f"consent_{i}") for i,
                    opt in enumerate(options)]
                inline_kb.add(*buttons)
                bot.send_message(
                    chat_id,
                    messages[language]['project_intro'],
                    parse_mode='HTML',
                    reply_markup=inline_kb
                )
        else:
            # Ask language first
            inline_kb = types.InlineKeyboardMarkup(row_width=2)
            english_button = types.InlineKeyboardButton(
                'English', callback_data='language_en')
            ukrainian_button = types.InlineKeyboardButton(
                'Українська', callback_data='language_uk')
            inline_kb.add(english_button, ukrainian_button)

            bot.send_message(
                chat_id,
                messages['en']['welcome'] + "\n" + messages['uk']['welcome'],
                reply_markup=inline_kb
            )
    except Exception as e:
        logging.exception(f"Error in send_welcome: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")




# Language and consent handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith('language_'))
def handle_language_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        data = callback_suffix(call.data, "purpose")

        # Initialize user_data for this user if it doesn't exist
        if user_id not in user_data:
            user_data[user_id] = {}

        if data == 'en':
            user_data[user_id]['language'] = 'en'
        elif data == 'uk':
            user_data[user_id]['language'] = 'uk'
        else:
            # Invalid selection
            bot.answer_callback_query(call.id, "Invalid selection.")
            return

        # Rest of the function remains the same
        language = user_data[user_id]['language']
        # Acknowledge the selection
        bot.answer_callback_query(
            call.id, f"Language set to {language.upper()}.")

        # Remove the inline keyboard
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None)

        # Confirm language selection
        bot.send_message(chat_id, messages[language]['language_selected'])

        # Store language in user_profiles
        user_profiles.setdefault(user_id, {})['language'] = language

        # Check if user has already given consent
        if user_id in user_profiles and 'consent' in user_profiles[user_id]:
            # If consent is already given, skip the consent question
            if user_profiles[user_id]['consent']:
                # Create a cleaner transition
                time.sleep(0.5)  # Small delay for better UX
                # Send location request directly
                send_next_step_prompt(
                    chat_id,
                    messages[language]['send_location'],
                    handle_location_step)
            else:
                # User previously declined, ask again
                options = messages[language]['consent_options']
                inline_kb = types.InlineKeyboardMarkup(row_width=2)
                buttons = [
                    types.InlineKeyboardButton(text=option, callback_data=f"consent_{idx}")
                    for idx, option in enumerate(options)
                ]
                inline_kb.add(*buttons)
                bot.send_message(
                    chat_id,
                    messages[language]['project_intro'],
                    parse_mode='HTML',
                    reply_markup=inline_kb
                )
        else:
            # Send introductory message and request consent using
            # InlineKeyboard
            options = messages[language]['consent_options']
            inline_kb = types.InlineKeyboardMarkup(row_width=2)
            buttons = [
                types.InlineKeyboardButton(text=option, callback_data=f"consent_{idx}")
                for idx, option in enumerate(options)
            ]
            inline_kb.add(*buttons)
            bot.send_message(
                chat_id,
                messages[language]['project_intro'],
                parse_mode='HTML',
                reply_markup=inline_kb
            )
    except Exception as e:
        logging.exception(f"Error in handle_language_selection: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('consent_'))
def handle_consent(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        # Ensure language is available
        if user_id not in user_data or 'language' not in user_data[user_id]:
            if user_id in user_profiles and 'language' in user_profiles[user_id]:
                user_data[user_id]['language'] = user_profiles[user_id]['language']
            else:
                bot.send_message(
                    chat_id,
                    "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
                return

        language = user_data[user_id]['language']
        consent_options = messages[language]['consent_options']
        try:
            idx = callback_index(call.data, "consent", consent_options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
            return

        if 0 <= idx < len(consent_options):
            consent_response = consent_options[idx]
            # Remove inline keyboard
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            if consent_response == consent_options[0]:  # User agrees
                nickname = user_data[user_id]['nickname']
                consent_message = messages[language]['consent_given'].format(
                    nickname=f"<b>{escape_html(nickname)}</b>")
                user_profiles.setdefault(user_id, {})['consent'] = True

                # Show "Continue" button after consent given with a loading
                # indicator
                bot.answer_callback_query(
                    call.id,
                    "Thank you for agreeing to participate!" if language == 'en' else "Дякуємо за вашу згоду на участь!")

                # Show "Continue" button after consent given
                continue_text = "Continue" if language == 'en' else "Продовжити"
                inline_kb = types.InlineKeyboardMarkup()
                continue_button = types.InlineKeyboardButton(
                    continue_text, callback_data='post_consent_continue')
                inline_kb.add(continue_button)

                bot.send_message(
                    chat_id,
                    consent_message,
                    parse_mode='HTML',
                    reply_markup=inline_kb)

            elif consent_response == consent_options[1]:  # User does not agree
                user_profiles.setdefault(user_id, {})['consent'] = False
                inline_kb = types.InlineKeyboardMarkup()
                restart_button = types.InlineKeyboardButton(
                    text=messages[language]['restart_button'], callback_data='restart')
                inline_kb.add(restart_button)

                bot.answer_callback_query(
                    call.id,
                    "Thank you for your time." if language == 'en' else "Дякуємо за ваш час.")

                bot.send_message(
                    chat_id,
                    messages[language]['consent_denied'],
                    reply_markup=inline_kb
                )
            else:
                bot.answer_callback_query(
                    call.id, messages[language]['invalid_selection'])
        else:
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])

    except Exception as e:
        logging.exception(f"Error in handle_consent: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


@bot.callback_query_handler(func=lambda call: call.data ==
                            'post_consent_continue')
def handle_post_consent_continue(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']

        # Remove the inline keyboard
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None)

        # Now send the location prompt
        send_next_step_prompt(
            chat_id,
            messages[language]['send_location'],
            handle_location_step)
    except Exception as e:
        logging.exception(f"Error in handle_post_consent_continue: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")




def handle_location_step(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        update_activity_timestamp(user_id)

        # Ensure the user has selected a language
        language = None
        if user_id in user_data and 'language' in user_data[user_id]:
            language = user_data[user_id]['language']
        elif user_id in user_profiles and 'language' in user_profiles[user_id]:
            language = user_profiles[user_id]['language']
            # Initialize user_data if needed
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['language'] = language
        else:
            # Cannot proceed without language
            bot.send_message(
                chat_id,
                "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
            return

        # Hide keyboard after receiving message
        remove_keyboard = types.ReplyKeyboardRemove()

        if message.content_type == 'location':
            latitude = message.location.latitude
            longitude = message.location.longitude

            # Try to extract venue information if available in message (for
            # newer Telegram clients)
            venue_title = ''
            venue_address = ''

            # If the message has venue details (Telegram might send this for
            # dropped pins)
            if hasattr(message, 'venue') and message.venue:
                if hasattr(message.venue, 'title') and message.venue.title:
                    venue_title = message.venue.title
                if hasattr(message.venue, 'address') and message.venue.address:
                    venue_address = message.venue.address

            # Store all available location data
            user_data[user_id]['location'] = {
                'latitude': latitude,
                'longitude': longitude,
                'venue_title': venue_title,
                'venue_address': venue_address
            }

            # Debug log for coordinates
            flow_logger.info(
                "Coordinate location received - "
                f"lat~{redacted_coordinate(latitude)}, long~{redacted_coordinate(longitude)}")

            # Enhanced confirmation message with emoji and coordinate display
            if venue_title or venue_address:
                location_info = f"{venue_title}, {venue_address}" if venue_title and venue_address else (
                    venue_title or venue_address)
                location_received_msg = f"📍 {messages[language]['location_received']}: {location_info}"
            else:
                location_received_msg = f"📍 {messages[language]['location_received']}: {latitude}, {longitude}"

            bot.send_message(
                chat_id,
                location_received_msg,
                reply_markup=remove_keyboard)

            # Now ask for purpose of visit first
            ask_purpose_visit(chat_id, user_id, language)

        elif message.content_type == 'venue':
            # Venue contains more detailed location information
            latitude = message.venue.location.latitude
            longitude = message.venue.location.longitude
            venue_title = message.venue.title
            venue_address = message.venue.address

            user_data[user_id]['location'] = {
                'latitude': latitude,
                'longitude': longitude,
                'venue_title': venue_title,
                'venue_address': venue_address
            }

            # Debug log for venue location
            flow_logger.info(
                "Venue location received; title/address redacted")

            # Enhanced confirmation message with emoji and venue info
            location_received_msg = f"📍 {messages[language]['location_received']}: {venue_title}, {venue_address}"
            bot.send_message(
                chat_id,
                location_received_msg,
                reply_markup=remove_keyboard)

            # Now ask for purpose of visit
            ask_purpose_visit(chat_id, user_id, language)

        elif message.content_type == 'text':
            # Handle free text input for location
            location_text = message.text.strip()

            # Check if it's a command (like /start) and handle it appropriately
            if location_text.startswith('/'):
                if location_text.startswith('/start'):
                    send_welcome(message)
                    return
                else:
                    bot.register_next_step_handler_by_chat_id(
                        chat_id, handle_location_step)
                    bot.send_message(
                        chat_id, messages[language]['please_send_location'])
                    return

            flow_logger.info("Text location received; content redacted")

            # Store in location data with empty coordinates but populated
            # venue_address
            user_data[user_id]['location'] = {
                'latitude': '',  # Empty as exact coordinates are not provided
                'longitude': '',  # Empty as exact coordinates are not provided
                'venue_title': '',
                'venue_address': location_text  # Store the text input in venue_address
            }

            flow_logger.info("Text location stored in user_data; content redacted")

            # Confirmation message
            location_received_msg = f"📍 {messages[language]['location_received']}: {location_text}"
            bot.send_message(
                chat_id,
                location_received_msg,
                reply_markup=remove_keyboard)

            # Now ask for purpose of visit
            ask_purpose_visit(chat_id, user_id, language)

        else:
            send_next_step_prompt(
                chat_id,
                messages[language]['please_send_location'],
                handle_location_step)
    except Exception as e:
        logging.exception(f"Error in handle_location_step: {e}")
        try:
            language = "en"  # Default fallback
            if user_id in user_data and 'language' in user_data[user_id]:
                language = user_data[user_id]['language']
            error_msg = messages[language].get(
                'error_occurred', "An error occurred. Please try again later.")
            bot.reply_to(message, error_msg)
        except Exception:
            # Fallback if language is not accessible
            bot.reply_to(
                message,
                "An error occurred. Please try again later. / Виникла помилка. Будь ласка, спробуйте пізніше.")



# Purpose visit handler
# Updated ask_purpose_visit function
def ask_purpose_visit(chat_id, user_id, language):
    try:
        # Clear old values using thread-safe methods
        set_user_data(user_id, 'purpose_visit', [])
        set_user_data(user_id, 'custom_purposes', [])
        set_user_data(user_id, 'awaiting_multiple_select', 'purpose_visit')

        # Get all options except 'Other'
        options = messages[language]['options']['purpose_visit'][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)

        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"purpose_{idx}")
            for idx, option in enumerate(options)
        ]
        # Add Done button
        done_button = types.InlineKeyboardButton(
            text=messages[language]['done_button'],
            callback_data="purpose_done")
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        instruction_text = (
            f"{messages[language]['purpose_visit']}\n\n"
            f"{'You can also type your own activity as a text message. ' if language=='en' else 'Ви також можете ввести власний варіант у полі введення тексту. '}"
            f"{'When finished, press Done.' if language=='en' else 'Коли закінчите, натисніть Готово.'}")

        # Use our enhanced message sender that tracks the message ID
        send_keyboard_message(
            chat_id, 
            user_id, 
            instruction_text, 
            inline_kb, 
            "purpose_visit"
        )
    except Exception as e:
        logging.exception(f"Error in ask_purpose_visit: {e}")
        safe_send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


# Updated handle_purpose_selection function
@bot.callback_query_handler(func=lambda call: call.data.startswith('purpose_'))
def handle_purpose_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = get_user_data(user_id, 'language')
        data = callback_suffix(call.data, "purpose")

        if data == 'done':
            purpose_visit = get_user_data(user_id, 'purpose_visit', [])
            custom_purposes = get_user_data(user_id, 'custom_purposes', [])
            
            if not purpose_visit and not custom_purposes:
                safe_answer_callback(
                    call,
                    messages[language].get(
                        'please_select_at_least_one',
                        "Please select at least one option or type your own."))
                return

            # Remove the inline keyboard using our registry
            edit_keyboard(user_id, chat_id, "purpose_visit", None)

            # Combine selected options and custom inputs
            all_purposes = purpose_visit + custom_purposes

            # Acknowledge completion with a feedback message
            safe_answer_callback(
                call, "Selections saved" if language == 'en' else "Вибір збережено")

            # Echo user's selection
            purposes = '; '.join(escape_html(p) for p in all_purposes)
            safe_send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{purposes}</i>",
                parse_mode='HTML')

            # Clear the awaiting_multiple_select state
            remove_user_data(user_id, 'awaiting_multiple_select')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if we're in modifying mode
            if get_user_data(user_id, 'modifying'):
                remove_user_data(user_id, 'modifying')
                remove_user_data(user_id, 'modifying_field')
                ask_final_confirmation(chat_id, user_id, language)
            else:
                # After purpose selection is complete, ask enjoyment
                # Add a slight delay for better UX transition
                time.sleep(0.5)
                ask_enjoyment(chat_id, user_id, language)
        else:
            # Remove the 'Other' option
            options = messages[language]['options']['purpose_visit'][:-1]
            try:
                idx = callback_index(call.data, "purpose", options)
            except (ValueError, IndexError):
                safe_answer_callback(
                    call, messages[language].get(
                        'invalid_selection', "Invalid selection."))
                return

            selected_option = options[idx]
                
            # Get the current purposes using thread-safe access
            purpose_visit = get_user_data(user_id, 'purpose_visit', [])

            # Just toggle selection
            if selected_option in purpose_visit:
                purpose_visit.remove(selected_option)
                safe_answer_callback(
                    call, f"{messages[language]['unselected']} {selected_option}")
            else:
                purpose_visit.append(selected_option)
                safe_answer_callback(
                    call, f"{messages[language]['selected']} {selected_option}")
                
            # Save the updated list using thread-safe method
            set_user_data(user_id, 'purpose_visit', purpose_visit)

            update_purpose_selection_keyboard(
                call.message, user_id, language)
    except Exception as e:
        handle_callback_error(call, e, "handle_purpose_selection")


# Updated update_purpose_selection_keyboard function
def update_purpose_selection_keyboard(message, user_id, language):
    try:
        # Get data using thread-safe methods
        options = messages[language]['options']['purpose_visit'][:-1]
        selected_options = get_user_data(user_id, 'purpose_visit', [])
        custom_options = get_user_data(user_id, 'custom_purposes', [])

        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option in selected_options else option
            callback_data = f"purpose_{idx}"
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data))

        # Only add the Done button if there's at least one selection
        if selected_options or custom_options:
            done_button = types.InlineKeyboardButton(
                text=messages[language]['done_button'],
                callback_data="purpose_done")
            inline_kb.add(*buttons)
            inline_kb.add(done_button)
        else:
            inline_kb.add(*buttons)

        # Use our registry to get the right message ID
        message_id = get_message_id(user_id, "purpose_visit")
        if message_id:
            try:
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message_id,
                    reply_markup=inline_kb)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    logging.exception(
                        f"Error in update_purpose_selection_keyboard: {e}")
        else:
            # Fallback - use the provided message
            try:
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=inline_kb)
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    logging.exception(
                        f"Error in update_purpose_selection_keyboard: {e}")
    except Exception as e:
        logging.exception(f"Error in update_purpose_selection_keyboard: {e}")



# Enjoyment and visitor type handlers
def ask_enjoyment(chat_id, user_id, language, remove_keyboard=False):
    try:
        # Combine predefined and custom purposes
        predefined_purposes = user_data[user_id].get('purpose_visit', [])
        custom_purposes = user_data[user_id].get('custom_purposes', [])
        all_purposes = predefined_purposes + custom_purposes

        if all_purposes:
            joined_purposes = ', '.join(all_purposes)
            if language == 'en':
                enjoyment_text = f"How did you find your time spent at this place while engaging in: {joined_purposes}?"
            else:
                enjoyment_text = f"Як вам сподобався ваш час, проведений у цьому місці, займаючись: {joined_purposes}?"
        else:
            # If no purposes were selected or typed for some reason, fallback:
            enjoyment_text = messages[language]['enjoyment_question']

        # Set current_question to track that we are at the enjoyment step
        user_data[user_id]['current_question'] = 'enjoyment'

        options = messages[language]['enjoyment_options']
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = []
        for idx, option in enumerate(options):
            button = types.InlineKeyboardButton(
                text=option, callback_data=f"enjoyment_{idx}")
            buttons.append(button)
        inline_kb.add(*buttons)

        bot.send_message(
            chat_id,
            enjoyment_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_enjoyment: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('enjoyment_'))
def handle_enjoyment_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        if user_id not in user_data or 'language' not in user_data[user_id]:
            if user_id in user_profiles and 'language' in user_profiles[user_id]:
                user_data[user_id]['language'] = user_profiles[user_id]['language']
            else:
                bot.send_message(
                    chat_id,
                    "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
                return

        language = user_data[user_id]['language']
        options = messages[language]['enjoyment_options']
        try:
            idx = callback_index(call.data, "enjoyment", options)
        except (ValueError, IndexError):
            safe_answer_callback(call, messages[language]['invalid_rating'])
            return

        enjoyment = options[idx]

        # Store temporarily, don't commit until confirmed
        user_data[user_id]['temp_enjoyment'] = enjoyment

        # Update keyboard to show selection and add Confirm button
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(options):
            # Mark the selected option
            text = f"✅ {option}" if i == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"enjoyment_{i}"))

        # Add Confirm/Done button
        done_text = messages[language]['done_button']
        inline_kb.add(
            types.InlineKeyboardButton(
                text=done_text,
                callback_data="confirm_enjoyment"))

        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb
            )
        except telebot.apihelper.ApiTelegramException as api_error:
            # Ignore "message is not modified" error
            if "message is not modified" not in str(api_error):
                logging.exception(
                    f"Telegram API error in handle_enjoyment_selection: {api_error}")

        # Replace direct call with safe_answer_callback
        safe_answer_callback(
            call, f"{messages[language]['selected']} {enjoyment}")
    except Exception as e:
        logging.exception(f"Error in handle_enjoyment_selection: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


@bot.callback_query_handler(func=lambda call: call.data == "confirm_enjoyment")
def confirm_enjoyment(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_enjoyment' in user_data[user_id]:
            user_data[user_id]['enjoyment'] = user_data[user_id]['temp_enjoyment']
            user_data[user_id].pop('temp_enjoyment')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, "Response confirmed" if language == 'en' else "Відповідь підтверджено")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Show confirmed response
            enjoyment = user_data[user_id]['enjoyment']
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(enjoyment)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Continue with the next question
            if user_data[user_id].get('modifying'):
                user_data[user_id].pop('modifying', None)
                user_data[user_id].pop('modifying_field', None)
                ask_final_confirmation(chat_id, user_id, language)
            else:
                ask_visitor_type(chat_id, user_id, language)
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_enjoyment: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


# Visitor type handler modifications
def ask_visitor_type(chat_id, user_id, language):
    try:
        # Clear old values if any
        user_data[user_id]['visitor_type'] = []
        user_data[user_id]['custom_visitor_types'] = []
        user_data[user_id]['awaiting_multiple_select'] = 'visitor_type'

        # Remove the 'Other' option
        visitor_options = messages[language]['visitor_type_options'][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(
                text=o,
                callback_data=f"visitor_{i}") for i,
            o in enumerate(visitor_options)]
        # Add Done button by default for better UX with free text input
        done_button = types.InlineKeyboardButton(
            text=messages[language]['done_button'],
            callback_data="visitor_done")
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        instruction_text = (
            f"{messages[language]['visitor_type_question']}\n\n"
            f"{'You can also type your own suggestion as a text message. ' if language=='en' else 'Ви також можете ввести власний варіант у полі введення тексту. '}"
            f"{'When finished, press Done.' if language=='en' else 'Коли закінчите, натисніть Готово.'}")

        bot.send_message(chat_id, instruction_text, reply_markup=inline_kb)
    except Exception as e:
        logging.exception(f"Error in ask_visitor_type: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data.startswith('visitor_'))
def handle_visitor_type_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']
        data = callback_suffix(call.data, "visitor")

        # Remove the 'Other' option
        visitor_options = messages[language]['visitor_type_options'][:-1]

        if data == 'done':
            # User presses Done
            # Check if user selected or typed anything
            if not user_data[user_id]['visitor_type'] and not user_data[user_id].get(
                    'custom_visitor_types', []):
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
            all_visitor_types = user_data[user_id]['visitor_type'] + \
                user_data[user_id].get('custom_visitor_types', [])

            # Echo the user's selections
            selected = '; '.join(all_visitor_types)
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected)}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select
            user_data[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if we're in modifying mode
            if user_data[user_id].get('modifying'):
                user_data[user_id].pop('modifying')
                user_data[user_id].pop('modifying_field', None)
                ask_final_confirmation(chat_id, user_id, language)
            else:
                # Proceed directly to ask_duration
                ask_duration(chat_id, user_id, language)
        else:
            try:
                idx = callback_index(call.data, "visitor", visitor_options)
            except (ValueError, IndexError):
                safe_answer_callback(
                    call, messages[language]['invalid_selection'])
                return

            choice = visitor_options[idx]

            # Toggle selection
            if choice in user_data[user_id]['visitor_type']:
                user_data[user_id]['visitor_type'].remove(choice)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['unselected']} {choice}")
            else:
                user_data[user_id]['visitor_type'].append(choice)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['selected']} {choice}")

            update_visitor_type_keyboard(
                call.message, user_id, language, visitor_options)
    except Exception as e:
        logging.exception(f"Error in handle_visitor_type_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def update_visitor_type_keyboard(message, user_id, language, options):
    try:
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        selected_options = user_data[user_id]['visitor_type']
        custom_visitor_types = user_data[user_id].get(
            'custom_visitor_types', [])

        buttons = []
        for i, o in enumerate(options):
            prefix = "✅ " if o in selected_options else ""
            buttons.append(
                types.InlineKeyboardButton(
                    text=prefix + o,
                    callback_data=f"visitor_{i}"))

        # Only add the Done button if at least one selection has been made
        if selected_options or custom_visitor_types:
            done_button = types.InlineKeyboardButton(
                text=messages[language]['done_button'],
                callback_data="visitor_done")
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
                logging.exception(
                    f"Error in update_visitor_type_keyboard: {e}")
    except Exception as e:
        logging.exception(f"Error in update_visitor_type_keyboard: {e}")



# Duration and accessibility handlers
def ask_duration(chat_id, user_id, language):
    try:
        user_data[user_id]['duration_visit'] = ''
        user_data[user_id]['current_question'] = 'duration'

        duration_options = messages[language]['duration_options']
        inline_kb = types.InlineKeyboardMarkup(row_width=1)

        for i, option in enumerate(duration_options):
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=option,
                    callback_data=f"duration_{i}"))

        # Use the question text directly
        question_text = messages[language]['duration_question']

        bot.send_message(
            chat_id,
            question_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_duration: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('duration_'))
def handle_duration_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']

        duration_options = messages[language]['duration_options']
        try:
            idx = callback_index(call.data, "duration", duration_options)
        except (ValueError, IndexError):
            safe_answer_callback(call, messages[language]['invalid_selection'])
            return

        selected_duration = duration_options[idx]

        # Store temporarily, don't commit until confirmed
        user_data[user_id]['temp_duration_visit'] = selected_duration

        # Update keyboard to show selection and add Confirm button
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(duration_options):
            # Mark the selected option
            text = f"✅ {option}" if i == idx else option
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=f"duration_{i}"))

        # Add Confirm/Done button
        done_text = messages[language]['done_button']
        inline_kb.add(
            types.InlineKeyboardButton(
                text=done_text,
                callback_data="confirm_duration"))

        try:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=inline_kb
            )
        except telebot.apihelper.ApiTelegramException as api_error:
            # Ignore "message is not modified" error as it's normal when
            # selecting the same option
            if "message is not modified" not in str(api_error):
                raise api_error

        # Replace direct call with safe_answer_callback
        safe_answer_callback(
            call, f"{messages[language]['selected']} {selected_duration}")
    except Exception as e:
        logging.exception(f"Error in handle_duration_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data == "confirm_duration")
def confirm_duration(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_duration_visit' in user_data[user_id]:
            selected_duration = user_data[user_id]['temp_duration_visit']
            user_data[user_id]['duration_visit'] = selected_duration
            user_data[user_id].pop('temp_duration_visit')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

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
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_duration)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if we're in modifying mode
            if user_data[user_id].get('modifying'):
                user_data[user_id].pop('modifying')
                user_data[user_id].pop('modifying_field', None)
                ask_final_confirmation(chat_id, user_id, language)
            else:
                # Proceed to accessibility
                ask_accessibility(chat_id, user_id, language)
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_duration: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


# Accessibility handler modifications
def ask_accessibility(chat_id, user_id, language):
    try:
        # Clear old values if any
        user_data[user_id]['accessibility'] = []
        user_data[user_id]['custom_accessibility'] = []
        user_data[user_id]['awaiting_multiple_select'] = 'accessibility'

        # Remove the 'Other' option
        options = messages[language]['accessibility_options'][:-1]
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        buttons = [
            types.InlineKeyboardButton(
                text=option,
                callback_data=f"accessibility_{idx}") for idx,
            option in enumerate(options)]
        # Add Done button by default for better UX with free text input
        done_button = types.InlineKeyboardButton(
            text=messages[language]['done_button'],
            callback_data="accessibility_done")
        inline_kb.add(*buttons)
        inline_kb.add(done_button)

        instruction_text = (
            f"{messages[language]['accessibility_question']}\n\n"
            f"{('You can also type your own mode of travel as a text message. ' if language=='en' else 'Ви також можете ввести власний варіант у полі введення тексту. ')}"
            f"{('When finished, press Done.' if language=='en' else 'Коли закінчите, натисніть Готово.')}")

        bot.send_message(
            chat_id,
            instruction_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_accessibility: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(
    func=lambda call: call.data.startswith('accessibility_'))
@bot.callback_query_handler(
    func=lambda call: call.data.startswith('accessibility_'))
def handle_accessibility_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']

        data = callback_suffix(call.data, "accessibility")
        # Remove the 'Other' option
        options = messages[language]['accessibility_options'][:-1]

        if data == 'done':
            if not user_data[user_id]['accessibility'] and not user_data[user_id].get(
                    'custom_accessibility', []):
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

            # Combine predefined and custom inputs
            all_access = user_data[user_id]['accessibility'] + \
                user_data[user_id].get('custom_accessibility', [])
            selected = '; '.join(all_access)
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected)}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select
            user_data[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            if user_data[user_id].get('modifying'):
                user_data[user_id].pop('modifying')
                ask_final_confirmation(chat_id, user_id, language)
            else:
                ask_regularity(chat_id, user_id, language)
        else:
            # User selected/unselected an option
            idx = int(data)
            if 0 <= idx < len(options):
                choice = options[idx]

                # Toggle selection
                if choice in user_data[user_id]['accessibility']:
                    user_data[user_id]['accessibility'].remove(choice)
                    # Replace direct call with safe_answer_callback
                    safe_answer_callback(
                        call, f"{messages[language]['unselected']} {choice}")
                else:
                    user_data[user_id]['accessibility'].append(choice)
                    # Replace direct call with safe_answer_callback
                    safe_answer_callback(
                        call, f"{messages[language]['selected']} {choice}")

                update_accessibility_keyboard(
                    call.message, user_id, language, options)
            else:
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, messages[language]['invalid_selection'])
    except Exception as e:
        logging.exception(f"Error in handle_accessibility_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def update_accessibility_keyboard(message, user_id, language, options):
    # Show checkmarks for selected items
    try:
        inline_kb = types.InlineKeyboardMarkup(row_width=1)
        selected_options = user_data[user_id]['accessibility']
        custom_accessibility = user_data[user_id].get(
            'custom_accessibility', [])

        buttons = []
        for idx, option in enumerate(options):
            button_text = f"✅ {option}" if option in selected_options else option
            callback_data = f"accessibility_{idx}"
            buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=callback_data))

        # Only add the Done button if at least one selection has been made
        if selected_options or custom_accessibility:
            done_button = types.InlineKeyboardButton(
                text=messages[language]['done_button'],
                callback_data="accessibility_done")
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
                logging.exception(
                    f"Error in update_accessibility_keyboard: {e}")
    except Exception as e:
        logging.exception(f"Error in update_accessibility_keyboard: {e}")
        bot.send_message(
            message.chat.id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))



def ask_regularity(chat_id, user_id, language):
    """
    Asks the user about their visit regularity to the place.
    This is the first question in the dependent chain.
    """
    try:
        # Reset regularity data
        user_data[user_id]['regularity'] = ''
        user_data[user_id]['current_question'] = 'regularity'

        options = messages[language]['options']['regularity']
        inline_kb = types.InlineKeyboardMarkup(row_width=1)

        buttons = [
            types.InlineKeyboardButton(text=option, callback_data=f"regularity_{idx}")
            for idx, option in enumerate(options)
        ]
        inline_kb.add(*buttons)

        # Use the question text directly
        question_text = messages[language]['regularity_question']

        bot.send_message(
            chat_id,
            question_text,
            reply_markup=inline_kb
        )
    except Exception as e:
        logging.exception(f"Error in ask_regularity: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data.startswith('regularity_'))
def handle_regularity_selection(call):
    """
    Handles user selection for regularity question.
    This is a pivotal question that affects the flow of subsequent questions.
    """
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']

        options = messages[language]['options']['regularity']
        try:
            selected_idx = callback_index(call.data, "regularity", options)
        except (ValueError, IndexError):
            safe_answer_callback(
                call, messages[language].get(
                    'invalid_selection', "Invalid selection."))
            return

        if 0 <= selected_idx < len(options):
            selected_regularity = options[selected_idx]

            # Store temporarily, don't commit until confirmed
            user_data[user_id]['temp_regularity'] = selected_regularity

            # Update the keyboard to show selection and add Confirm button
            inline_kb = types.InlineKeyboardMarkup(row_width=1)
            for idx, option in enumerate(options):
                # Mark the selected option
                text = f"✅ {option}" if idx == selected_idx else option
                inline_kb.add(
                    types.InlineKeyboardButton(
                        text=text,
                        callback_data=f"regularity_{idx}"))

            # Add Confirm/Done button
            done_text = messages[language]['done_button']
            inline_kb.add(
                types.InlineKeyboardButton(
                    text=done_text,
                    callback_data="confirm_regularity"))

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
                        f"Error in handle_regularity_selection: {e}")

            # Notify user of selection (but not confirmation yet)
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, f"{messages[language]['selected']} {selected_regularity}")
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, messages[language].get(
                    'invalid_selection', "Invalid selection."))
    except Exception as e:
        logging.exception(f"Error in handle_regularity_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data ==
                            "confirm_regularity")
def confirm_regularity(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']
        anon_id = get_anonymous_id(user_id)

        # Transfer from temp storage to actual storage
        if 'temp_regularity' in user_data[user_id]:
            selected_regularity = user_data[user_id]['temp_regularity']
            previous_regularity = user_data[user_id].get('regularity', '')

            # Log regularity change
            if previous_regularity != selected_regularity:
                flow_logger.info(
                    f"User {anon_id}: Changed regularity from '{previous_regularity}' to '{selected_regularity}'")

            # Save the new selection
            user_data[user_id]['regularity'] = selected_regularity
            user_profiles.setdefault(
                user_id, {})['regularity'] = selected_regularity
            user_data[user_id].pop('temp_regularity')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

            # Clear dependent fields if appropriate - this is critical for
            # properly clearing dependencies
            if previous_regularity != selected_regularity:
                cleared_fields = clear_dependent_fields(
                    user_id, 'regularity', previous_regularity, selected_regularity)
                if cleared_fields:
                    flow_logger.info(
                        f"User {anon_id}: Cleared fields due to regularity change: {cleared_fields}")

            # Confirm to user
            safe_answer_callback(
                call, "Response confirmed" if language == 'en' else "Відповідь підтверджено")
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=None)

            # Show confirmed response
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_regularity)}</i>",
                parse_mode='HTML')

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Define skip patterns explicitly
            skip_to_wishlist_options = [
                "One-time visit", "Разове відвідування",
                "Visited before 2022 but not anymore",
                "Відвідував(-ла) до 2022 р., але не зараз",
                "Prefer not to disclose", "Надаю перевагу не вказувати"
            ]

            # Check if any skip pattern is found in the selected regularity
            should_skip = False
            for pattern in skip_to_wishlist_options:
                if pattern in selected_regularity:
                    should_skip = True
                    break

            # Handle next steps based on modification state and selection
            if user_data[user_id].get('modifying'):
                if not should_skip:
                    # Proceed to noticed_changes if follow-up is required
                    flow_logger.info(
                        f"User {anon_id}: In modification flow, proceeding to noticed_changes")
                    ask_noticed_changes(chat_id, user_id, language)
                else:
                    # No follow-ups needed, go to final confirmation
                    flow_logger.info(
                        f"User {anon_id}: In modification flow, skipping follow-ups, going to final confirmation")
                    user_data[user_id].pop('modifying')
                    user_data[user_id].pop('modifying_field', None)
                    ask_final_confirmation(chat_id, user_id, language)
            else:
                # Normal flow
                if should_skip:
                    # Skip directly to wishlist for one-time visits
                    flow_logger.info(
                        f"User {anon_id}: Skipping directly to wishlist")
                    ask_wishlist(chat_id, user_id, language)
                else:
                    # Regular multiple visit paths
                    flow_logger.info(
                        f"User {anon_id}: Regular visitor, proceeding to noticed_changes")
                    ask_noticed_changes(chat_id, user_id, language)
        else:
            safe_answer_callback(
                call,
                "Please select an option first" if language == 'en' else "Спочатку виберіть варіант")
    except Exception as e:
        logging.exception(f"Error in confirm_regularity: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


def ask_frequency_change(chat_id, user_id, language):
    """
    Asks if user's visit frequency has changed compared to previous years.
    Second question in the dependent chain, follows regularity.
    """
    try:
        # Remove flow logging for normal flow
        user_data[user_id]['frequency_change'] = ''
        user_data[user_id]['current_question'] = 'frequency_change'
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
        language = user_data[user_id]['language']
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
        previous_freq_change = user_data[user_id].get('frequency_change', '')

        # Only log if this is a modification
        if user_data[user_id].get(
                'modifying') and previous_freq_change != selected_frequency_change:
            flow_logger.info(
                f"User {anon_id}: Modified frequency_change from '{previous_freq_change}' to '{selected_frequency_change}'")

        # Save the new selection
        user_data[user_id]['frequency_change'] = selected_frequency_change

        # Remove current question marker
        user_data[user_id].pop('current_question', None)

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
            user_data[user_id]['noticed_changes'] = selected_frequency_change

        # Determine next question based on modification state
        if user_data[user_id].get('modifying'):
            if selected_frequency_change in didnt_visit_options:
                # Skip noticed_changes and go to final confirmation
                user_data[user_id].pop('modifying')
                user_data[user_id].pop('modifying_field', None)
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
        user_data[user_id]['noticed_changes'] = ''
        user_data[user_id]['current_question'] = 'noticed_changes'

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
        language = user_data[user_id]['language']

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
        user_data[user_id]['temp_noticed_changes'] = selected_change

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
        language = user_data[user_id]['language']
        anon_id = get_anonymous_id(user_id)

        # Transfer from temp storage to actual storage
        if 'temp_noticed_changes' in user_data[user_id]:
            selected_change = user_data[user_id]['temp_noticed_changes']
            previous_change = user_data[user_id].get('noticed_changes', '')

            # Log if it's a modification
            if user_data[user_id].get(
                    'modifying') and previous_change != selected_change:
                flow_logger.info(
                    f"User {anon_id}: Modified noticed changes from '{previous_change}' to '{selected_change}'")

            # Save the new selection
            user_data[user_id]['noticed_changes'] = selected_change
            user_profiles.setdefault(
                user_id, {})['noticed_changes'] = selected_change
            user_data[user_id].pop('temp_noticed_changes')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

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
                if user_data[user_id].get('modifying'):
                    user_data[user_id].pop('modifying')
                    user_data[user_id].pop('modifying_field', None)
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

        user_data[user_id]['changes_detail'] = []
        user_data[user_id]['custom_changes'] = []
        user_data[user_id]['awaiting_multiple_select'] = 'changes_detail'

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
        language = user_data[user_id]['language']
        anon_id = get_anonymous_id(user_id)

        # Remove the 'Other' option
        options = messages[language]['options']['changes_detail'][:-1]
        data = callback_suffix(call.data, "changes_detail")

        if data == 'done':
            if not user_data[user_id]['changes_detail'] and not user_data[user_id].get(
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
            all_changes = user_data[user_id]['changes_detail'] + \
                user_data[user_id].get('custom_changes', [])
            changes = '; '.join(escape_html(change) for change in all_changes)

            # Log the final selection with anonymous ID
            flow_logger.info(
                f"User {anon_id}: Completed changes_detail with selections: {all_changes}")

            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{changes}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select
            user_data[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if we're in modification mode
            if user_data[user_id].get('modifying'):
                user_data[user_id].pop('modifying')
                user_data[user_id].pop('modifying_field', None)
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
            if selected_option in user_data[user_id]['changes_detail']:
                user_data[user_id]['changes_detail'].remove(selected_option)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['unselected']} {selected_option}")
                flow_logger.info(
                    f"User {anon_id}: Unselected changes_detail option: {selected_option}")
            else:
                user_data[user_id]['changes_detail'].append(selected_option)
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
        selected_options = user_data[user_id]['changes_detail']
        custom_changes = user_data[user_id].get('custom_changes', [])

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
        user_data[user_id]['wishlist'] = []
        user_data[user_id]['custom_wishlist'] = []
        user_data[user_id]['awaiting_multiple_select'] = 'wishlist'

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
        language = user_data[user_id]['language']
        data = callback_suffix(call.data, "wishlist")

        # Use the same options list as in ask_wishlist
        all_options = messages[language]['options']['wishlist']
        # Get all options except the last one (Other)
        options = all_options[:-1]

        if data == 'done':
            if not user_data[user_id]['wishlist'] and not user_data[user_id].get(
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
            all_wishlist = user_data[user_id]['wishlist'] + \
                user_data[user_id].get('custom_wishlist', [])
            selected = '; '.join(all_wishlist)
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected)}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select
            user_data[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            if user_data[user_id].get('modifying'):
                user_data[user_id].pop('modifying')
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
            if choice in user_data[user_id]['wishlist']:
                user_data[user_id]['wishlist'].remove(choice)
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, f"{messages[language]['unselected']} {choice}")
            else:
                user_data[user_id]['wishlist'].append(choice)
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
        selected_options = user_data[user_id]['wishlist']
        custom_wishlist = user_data[user_id].get('custom_wishlist', [])

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
        if not user_data[user_id].get('modifying'):
            if user_id in user_profiles and 'age' in user_profiles[user_id]:
                user_data[user_id]['age'] = user_profiles[user_id]['age']
                ask_gender(chat_id, user_id, language)
                return

        # Single-select question, set current_question
        user_data[user_id]['current_question'] = 'age'
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

        # Ensure user exists in user_data and has language
        if user_id not in user_data or 'language' not in user_data[user_id]:
            # Try to get language from user_profiles
            if user_id in user_profiles and 'language' in user_profiles[user_id]:
                # Initialize user data if needed
                if user_id not in user_data:
                    user_data[user_id] = {}
                user_data[user_id]['language'] = user_profiles[user_id]['language']
                language = user_data[user_id]['language']
            else:
                # Cannot proceed without language
                bot.answer_callback_query(
                    call.id, "Please start again with /start")
                bot.send_message(
                    chat_id,
                    "Session expired. Please use /start to begin.\nСесія закінчилася. Будь ласка, використайте /start для початку.")
                return
        else:
            language = user_data[user_id]['language']

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
        user_data[user_id]['temp_age'] = selected_age

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
            language = user_data.get(user_id, {}).get('language', 'en')
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

        # Ensure user exists in user_data and has language
        if user_id not in user_data or 'language' not in user_data[user_id]:
            # Try to get language from user_profiles
            if user_id in user_profiles and 'language' in user_profiles[user_id]:
                # Initialize user data if needed
                if user_id not in user_data:
                    user_data[user_id] = {}
                user_data[user_id]['language'] = user_profiles[user_id]['language']
                language = user_data[user_id]['language']
            else:
                # Cannot proceed without language
                bot.answer_callback_query(
                    call.id, "Please start again with /start")
                bot.send_message(
                    chat_id,
                    "Session expired. Please use /start to begin.\nСесія закінчилася. Будь ласка, використайте /start для початку.")
                return
        else:
            language = user_data[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_age' in user_data[user_id]:
            selected_age = user_data[user_id]['temp_age']
            user_data[user_id]['age'] = selected_age
            user_profiles.setdefault(user_id, {})['age'] = selected_age
            user_data[user_id].pop('temp_age')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

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
            language = user_data.get(user_id, {}).get('language', 'en')
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
        if not user_data[user_id].get('modifying'):
            if user_id in user_profiles and 'gender' in user_profiles[user_id]:
                user_data[user_id]['gender'] = user_profiles[user_id]['gender']
                ask_occupation(chat_id, user_id, language)
                return

        user_data[user_id]['current_question'] = 'gender'
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
        language = user_data[user_id]['language']
        options = messages[language]['options']['gender']
        try:
            idx = callback_index(call.data, "gender", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
            return

        selected_gender = options[idx]

        # Store temporarily, don't commit until confirmed
        user_data[user_id]['temp_gender'] = selected_gender

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
        language = user_data[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_gender' in user_data[user_id]:
            selected_gender = user_data[user_id]['temp_gender']
            user_data[user_id]['gender'] = selected_gender
            user_profiles.setdefault(user_id, {})['gender'] = selected_gender
            user_data[user_id].pop('temp_gender')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

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

            if user_data[user_id].get('modifying'):
                field_modified = user_data[user_id].get('modifying_field')
                user_data[user_id].pop('modifying', None)
                user_data[user_id].pop('modifying_field', None)

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
        if not user_data[user_id].get('modifying'):
            if user_id in user_profiles and 'occupation' in user_profiles[user_id]:
                user_data[user_id]['occupation'] = user_profiles[user_id]['occupation']
                ask_income(chat_id, user_id, language)
                return

        user_data[user_id]['current_question'] = 'occupation'
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
        language = user_data[user_id]['language']
        options = messages[language]['options']['occupation']
        try:
            idx = callback_index(call.data, "occupation", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
            return

        selected_occupation = options[idx]

        # Store temporarily, don't commit until confirmed
        user_data[user_id]['temp_occupation'] = selected_occupation

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
        language = user_data[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_occupation' in user_data[user_id]:
            selected_occupation = user_data[user_id]['temp_occupation']
            user_data[user_id]['occupation'] = selected_occupation
            user_profiles.setdefault(
                user_id, {})['occupation'] = selected_occupation
            user_data[user_id].pop('temp_occupation')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

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

            if user_data[user_id].get('modifying'):
                field_modified = user_data[user_id].get('modifying_field')
                user_data[user_id].pop('modifying')
                user_data[user_id].pop('modifying_field', None)

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
        if not user_data[user_id].get('modifying'):
            if user_id in user_profiles and 'income' in user_profiles[user_id]:
                user_data[user_id]['income'] = user_profiles[user_id]['income']
                # Always check if kremenchuk is already stored in user_profiles
                if 'kremenchuk' in user_profiles[user_id]:
                    user_data[user_id]['kremenchuk'] = user_profiles[user_id]['kremenchuk']
                    # Skip to description directly
                    ask_description(chat_id, user_id, language)
                    return
                else:
                    # Ask kremenchuk only once as part of socioeconomic
                    # questions
                    ask_kremenchuk(chat_id, user_id, language)
                    return

        user_data[user_id]['current_question'] = 'income'
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
        language = user_data[user_id]['language']
        options = messages[language]['options']['income']
        try:
            idx = callback_index(call.data, "income", options)
        except (ValueError, IndexError):
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
            return

        selected_income = options[idx]

        # Store temporarily, don't commit until confirmed
        user_data[user_id]['temp_income'] = selected_income

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
        language = user_data[user_id]['language']

        # Transfer from temp storage to actual storage
        if 'temp_income' in user_data[user_id]:
            selected_income = user_data[user_id]['temp_income']
            user_data[user_id]['income'] = selected_income
            user_profiles.setdefault(user_id, {})['income'] = selected_income
            user_data[user_id].pop('temp_income')

            # Remove current_question marker
            user_data[user_id].pop('current_question', None)

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

            if user_data[user_id].get('modifying'):
                field_modified = user_data[user_id].get('modifying_field')
                user_data[user_id].pop('modifying')
                user_data[user_id].pop('modifying_field', None)

                if field_modified != 'description':
                    ask_final_confirmation(chat_id, user_id, language)
                    return
                else:
                    ask_description(chat_id, user_id, language)
            else:
                # Check if kremenchuk has already been asked once
                if user_id in user_profiles and 'kremenchuk' in user_profiles[user_id]:
                    # If already asked once, just use the stored value and go
                    # to description
                    user_data[user_id]['kremenchuk'] = user_profiles[user_id]['kremenchuk']
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
        user_data[user_id]['kremenchuk'] = ''
        user_data[user_id]['custom_kremenchuk'] = []
        user_data[user_id]['awaiting_multiple_select'] = 'kremenchuk'

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
        language = user_data[user_id]['language']
        data = callback_suffix(call.data, "kremenchuk")
        options = messages[language]['options']['kremenchuk'][:- \
            2] + messages[language]['options']['kremenchuk'][-1:]

        if data == 'done':
            if not user_data[user_id]['kremenchuk'] and not user_data[user_id].get(
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
            kremenchuk_value = user_data[user_id]['kremenchuk']
            custom_values = user_data[user_id].get('custom_kremenchuk', [])

            all_values = []
            if kremenchuk_value:
                all_values.append(kremenchuk_value)
            all_values.extend(custom_values)

            selected_text = '; '.join(all_values)

            # Save to user_profiles
            if kremenchuk_value:
                user_profiles.setdefault(
                    user_id, {})['kremenchuk'] = kremenchuk_value

            # Show user's selections
            bot.send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(selected_text)}</i>",
                parse_mode='HTML')

            # Clear awaiting_multiple_select state
            user_data[user_id].pop('awaiting_multiple_select', None)

            # Hide keyboard before moving to next question
            hide_keyboard(chat_id)

            # Check if we're in modifying mode
            if user_data[user_id].get('modifying'):
                user_data[user_id].pop('modifying')
                user_data[user_id].pop('modifying_field', None)
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
            user_data[user_id]['kremenchuk'] = selected_kremenchuk

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
        selected_option = user_data[user_id].get('kremenchuk', '')
        custom_kremenchuk = user_data[user_id].get('custom_kremenchuk', [])

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
    try:
        # Ensure kremenchuk is loaded from profiles if available
        if 'kremenchuk' not in user_data[user_id] and user_id in user_profiles and 'kremenchuk' in user_profiles[user_id]:
            user_data[user_id]['kremenchuk'] = user_profiles[user_id]['kremenchuk']

        # If we're not modifying 'description', and description_done is True,
        # skip this step
        if user_data[user_id].get('description_done') and not (
            user_data[user_id].get('modifying') and
            user_data[user_id].get('modifying_field') == 'description'
        ):
            # If the user has already provided or skipped description in a previous flow
            # and we're not currently modifying it, go directly to final
            # confirmation.
            ask_final_confirmation(chat_id, user_id, language)
            return

        # If modifying but not the description field, skip asking it again
        if user_data[user_id].get('modifying'):
            field_modified = user_data[user_id].get('modifying_field')
            if field_modified != 'description':
                ask_final_confirmation(chat_id, user_id, language)
                return

        # Otherwise, proceed to ask the description
        inline_kb = types.InlineKeyboardMarkup()
        skip_button = types.InlineKeyboardButton(
            text=messages[language]['skip_button'],
            callback_data='description_skip')
        inline_kb.add(skip_button)

        # Add more clear instructions on how to leave a voice message
        enhanced_instructions = messages[language]['add_description']
        if language == 'en':
            enhanced_instructions += "\n\n(To send a voice message, touch and hold the microphone icon in the message bar, speak, and then release.)"
        else:
            enhanced_instructions += "\n\n(Щоб надіслати голосове повідомлення, натисніть і утримуйте іконку мікрофона в рядку повідомлень, говоріть і потім відпустіть.)"

        send_next_step_prompt(
            chat_id,
            enhanced_instructions,
            handle_description,
            reply_markup=inline_kb)

    except Exception as e:
        logging.exception(f"Error in ask_description: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


@bot.callback_query_handler(func=lambda call: call.data == 'description_skip')
def handle_description_skip(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        language = user_data[user_id]['language']

        # Clear the next step handler
        bot.clear_step_handler_by_chat_id(chat_id)

        # Remove the inline keyboard
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None)

        # Mark description as done (skipped)
        user_data[user_id]['description_done'] = True

        # Notify user that they skipped the description
        bot.send_message(chat_id, messages[language]['description_skipped'])

        ask_final_confirmation(chat_id, user_id, language)

    except Exception as e:
        logging.exception(f"Error in handle_description_skip: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


def handle_description(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id

        # Ensure user is properly set up
        language = get_user_data(user_id, 'language')
        if not language:
            if get_user_profile(user_id, 'language'):
                language = get_user_profile(user_id, 'language')
                set_user_data(user_id, 'language', language)
            else:
                safe_send_message(chat_id, "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
                return

        description = ''
        voice_submitted = ''

        # Remove inline keyboard if it exists
        try:
            # Clear any previous keyboard
            message_id = get_message_id(user_id, "description_request")
            if message_id:
                bot.edit_message_reply_markup(
                    chat_id=chat_id, 
                    message_id=message_id, 
                    reply_markup=None
                )
        except Exception:
            pass  # Ignore failures in clearing previous keyboards

        if message.content_type == 'text':
            description = message.text.strip()
            safe_send_message(
                chat_id,
                f"<b>{messages[language]['your_response']}</b> <i>{escape_html(description)}</i>",
                parse_mode='HTML'
            )
        elif message.content_type == 'voice':
            # Check if fernet is available globally
            global fernet
            if fernet is None:
                # Log the error and inform the user
                flow_logger.error("Encryption system not initialized, voice message not saved")
                safe_send_message(
                    chat_id,
                    "Sorry, there was an error processing your voice message. Please try sending a text response instead.",
                    parse_mode='HTML'
                )
                # Re-register for a new attempt
                bot.register_next_step_handler_by_chat_id(
                    chat_id, handle_description)
                return

            try:
                # Process voice message with retry logic
                for attempt in range(3):  # Try up to 3 times
                    try:
                        voice_file_id = message.voice.file_id
                        file_info = bot.get_file(voice_file_id)
                        downloaded_file = bot.download_file(file_info.file_path)
                        
                        # Successfully downloaded, break retry loop
                        break
                    except ApiTelegramException as e:
                        if getattr(e, "error_code", None) == 429:
                            retry_after = telegram_retry_after(e, default=3)
                            flow_logger.warning(f"Voice download error: {e}, retrying in {retry_after}s")
                            time.sleep(retry_after)
                        elif attempt < 2:
                            retry_after = 2 ** attempt
                            flow_logger.warning(f"Voice download API error: {e}, retrying in {retry_after}s")
                            time.sleep(retry_after)
                        else:
                            # Final attempt failed
                            raise
                
                # Encrypt the voice file
                encrypted_voice = fernet.encrypt(downloaded_file)
                
                # Get a thread-safe copy of the nickname
                nickname = get_user_data(user_id, 'nickname')
                
                # Create directory for user's voice files
                user_voice_dir = safe_nickname_directory(voice_files_dir, nickname)
                os.makedirs(user_voice_dir, exist_ok=True)
                
                # Generate a non-racy filename to avoid concurrent upload collisions.
                filename = new_voice_filename(nickname)
                voice_filename = user_voice_dir / filename

                # Write the encrypted file
                with open(voice_filename, 'wb') as new_file:
                    new_file.write(encrypted_voice)

                voice_submitted = os.path.join(nickname, filename)

                safe_send_message(
                    chat_id,
                    f"<b>{messages[language]['your_response']}</b> {messages[language]['voice_message_submitted']}",
                    parse_mode='HTML'
                )
            except Exception as voice_error:
                flow_logger.error(f"Error processing voice message: {voice_error}")
                safe_send_message(
                    chat_id,
                    "Sorry, there was an error processing your voice message. Please try sending a text response instead.",
                    parse_mode='HTML'
                )
                # Re-register for a new attempt
                bot.register_next_step_handler_by_chat_id(
                    chat_id, handle_description)
                return
        else:
            safe_send_message(chat_id, messages[language]['please_send_text_or_voice'])
            bot.register_next_step_handler_by_chat_id(
                chat_id, handle_description)
            return

        # Store data using thread-safe methods
        set_user_data(user_id, 'description', description)
        set_user_data(user_id, 'voice_submitted', voice_submitted)
        set_user_data(user_id, 'description_done', True)

        ask_final_confirmation(chat_id, user_id, language)

    except Exception as e:
        logging.exception(f"Error in handle_description: {e}")
        try:
            language = get_user_data(user_id, 'language', 'en')
            error_msg = messages.get(language, {}).get('error_occurred', "An error occurred. Please try again later.")
            safe_send_message(chat_id, error_msg)
            
            # Provide a way to continue
            inline_kb = types.InlineKeyboardMarkup()
            skip_text = messages.get(language, {}).get('skip_button', "Skip")
            skip_button = types.InlineKeyboardButton(text=skip_text, callback_data='description_skip')
            inline_kb.add(skip_button)
            
            retry_msg = "Would you like to try again or skip the description?" if language == 'en' else "Хочете спробувати знову чи пропустити опис?"
            safe_send_message(chat_id, retry_msg, reply_markup=inline_kb)
        except Exception:
            # Fallback if everything else fails
            bot.reply_to(message, "An error occurred. Please try again later.")

                # Re-register for a new attempt


# Response confirmation and modification
def ask_final_confirmation(chat_id, user_id, language):
    """
    Shows a summary of all responses and asks for confirmation.
    This is the convergence point after all modifications.
    """
    try:
        # Ensure kremenchuk is loaded from profiles if available
        if 'kremenchuk' not in user_data[user_id] and user_id in user_profiles and 'kremenchuk' in user_profiles[user_id]:
            user_data[user_id]['kremenchuk'] = user_profiles[user_id]['kremenchuk']

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
        responses = user_data[user_id]
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
        if user_id not in user_data or 'language' not in user_data[user_id]:
            if user_id in user_profiles and 'language' in user_profiles[user_id]:
                user_data[user_id]['language'] = user_profiles[user_id]['language']
            else:
                bot.send_message(
                    chat_id,
                    "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
                return

        language = user_data[user_id]['language']
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

        # Combine user_data and user_profiles for existing fields
        combined_data = {
            **user_profiles.get(user_id, {}), **user_data[user_id]}

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
                    if field in combined_data or field in user_data[user_id]:
                        field_mapping[field] = label_mapping.get(
                            field, field.capitalize())
                    else:
                        # For conditional fields: if they do not exist at all, they might not be modifiable
                        # But in this case, we want them if at least once visited
                        # If you want all fields shown even if empty, you can
                        # remove this check
                        if field in label_mapping:
                            field_mapping[field] = label_mapping[field]

        user_data[user_id]['field_mapping'] = field_mapping

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
                f: user_data[user_id].get(
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

        language = user_data[user_id]['language']
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
            user_data[user_id]['modifying'] = True
            user_data[user_id]['modifying_field'] = field

            # Log the field being modified
            flow_logger.info(f"User {anon_id}: Modifying field: {field}")

            # Define field relationships for documentation
            field_dependencies = get_question_dependencies()

            # Log if modifying a field with dependencies
            if field in field_dependencies:
                dependent_fields = field_dependencies[field]
                # Log current values of the field and its dependents
                current_values = {
                    f: user_data[user_id].get(
                        f,
                        'not set') for f in [field] +
                    dependent_fields if f in user_data[user_id]}
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
    # Always use the nickname if available in user_data
    if user_id in user_data and 'nickname' in user_data[user_id]:
        return user_data[user_id]['nickname']

    # If not in user_data, check if we can retrieve it from the database
    user_hash = get_user_hash(user_id)
    nickname = get_user_nickname(user_hash)

    if nickname:
        # Store it in user_data for future use
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['nickname'] = nickname
        return nickname

    # If no nickname exists yet, generate one, save it, and return it
    nickname = generate_unique_nickname()
    save_user_nickname(user_hash, nickname)
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['nickname'] = nickname
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
    current_values = {f: user_data[user_id].get(
        f, 'not set') for f in fields_to_check if f in user_data[user_id]}

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
                if dep_field in user_data[user_id]:
                    user_data[user_id].pop(dep_field, None)
                    cleared_fields.append(dep_field)

                    # If changes_detail is cleared, also clear custom_changes
                    # if present
                    if dep_field == 'changes_detail' and 'custom_changes' in user_data[user_id]:
                        user_data[user_id].pop('custom_changes', None)
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
            if 'changes_detail' in user_data[user_id]:
                user_data[user_id].pop('changes_detail', None)
                cleared_fields.append('changes_detail')

                # Also clear custom_changes if present
                if 'custom_changes' in user_data[user_id]:
                    user_data[user_id].pop('custom_changes', None)
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

        nickname = user_data[user_id]['nickname']

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
        if user_id not in user_data or 'language' not in user_data[user_id]:
            if user_id in user_profiles and 'language' in user_profiles[user_id]:
                user_data[user_id] = {
                    'language': user_profiles[user_id]['language']}
            else:
                bot.send_message(
                    chat_id,
                    "Please use /start to begin.\nБудь ласка, використайте /start для початку.")
                return

        language = user_data[user_id]['language']
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
    if user_id not in user_data or 'language' not in user_data[user_id]:
        # Try to get language from user_profiles
        if user_id in user_profiles and 'language' in user_profiles[user_id]:
            user_data[user_id] = {
                'language': user_profiles[user_id]['language']}
            language = user_data[user_id]['language']
        else:
            # Send a start message if the user doesn't have an active session
            bot.send_message(
                chat_id,
                "Please use /start to begin a new survey.\nБудь ласка, використайте /start для початку нового опитування."
            )
            return
    else:
        language = user_data[user_id]['language']

    if 'awaiting_multiple_select' in user_data[user_id]:
        mode = user_data[user_id]['awaiting_multiple_select']
        user_input = m.text.strip()

        # Handle custom input for each multiple-select question type
        if mode == 'purpose_visit':
            if 'custom_purposes' not in user_data[user_id]:
                user_data[user_id]['custom_purposes'] = []
            user_data[user_id]['custom_purposes'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'changes_detail':
            if 'custom_changes' not in user_data[user_id]:
                user_data[user_id]['custom_changes'] = []
            user_data[user_id]['custom_changes'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'visitor_type':
            if 'custom_visitor_types' not in user_data[user_id]:
                user_data[user_id]['custom_visitor_types'] = []
            user_data[user_id]['custom_visitor_types'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'accessibility':
            if 'custom_accessibility' not in user_data[user_id]:
                user_data[user_id]['custom_accessibility'] = []
            user_data[user_id]['custom_accessibility'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'wishlist':
            if 'custom_wishlist' not in user_data[user_id]:
                user_data[user_id]['custom_wishlist'] = []
            user_data[user_id]['custom_wishlist'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        elif mode == 'kremenchuk':
            if 'custom_kremenchuk' not in user_data[user_id]:
                user_data[user_id]['custom_kremenchuk'] = []
            user_data[user_id]['custom_kremenchuk'].append(user_input)
            ack_text = "✅ Your input has been noted. You can select more options, type more text, or press Done to continue." if language == 'en' else "✅ Вашу відповідь додано. Можете обрати більше варіантів, ввести ще текст або натиснути 'Готово' для продовження."
            bot.send_message(chat_id, ack_text)

        else:
            # Unknown multiple select mode
            bot.send_message(chat_id, "Please make a selection from the available options." if language ==
                             'en' else "Будь ласка, зробіть вибір із доступних варіантів.")
    else:
        # Outside multiple-select mode, handle single-select questions
        current_question = user_data[user_id].get('current_question')
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
        # Get user data with thread-safe access
        with user_data_lock:
            user_data_copy = copy.deepcopy(user_data.get(user_id, {}))
            user_profile_copy = copy.deepcopy(user_profiles.get(user_id, {}))
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

        consent_str = "True"
        user_hash = get_user_hash(user_id)
        nickname = get_user_nickname(user_hash)
        month_year = datetime.datetime.now().strftime("%Y-%m")
        if not nickname:
            nickname = generate_unique_nickname()
            save_user_nickname(user_hash, nickname)

        # Ensure kremenchuk is loaded from profiles if needed
        kremenchuk_value = user_data_copy.get('kremenchuk', '')
        if not kremenchuk_value:
            kremenchuk_value = user_profile_copy.get('kremenchuk', '')

        # User consented. Create the data dictionary safely
        location_data = user_data_copy.get('location', {})
        venue_address = location_data.get('venue_address', '')

        # Process complex fields safely
        purpose_list = user_data_copy.get('purpose_visit', [])
        if isinstance(purpose_list, list):
            purpose_str = ';'.join(purpose_list)
        else:
            purpose_str = str(purpose_list)

        changes_detail_list = user_data_copy.get('changes_detail', [])
        if isinstance(changes_detail_list, list):
            changes_detail_str = ';'.join(changes_detail_list)
        else:
            changes_detail_str = str(changes_detail_list)

        wishlist_list = user_data_copy.get('wishlist', [])
        if isinstance(wishlist_list, list):
            wishlist_str = ';'.join(wishlist_list)
        else:
            wishlist_str = str(wishlist_list) if wishlist_list else ''

        visitor_type_list = user_data_copy.get('visitor_type', [])
        if isinstance(visitor_type_list, list):
            visitor_type_str = ';'.join(visitor_type_list)
        else:
            visitor_type_str = str(visitor_type_list)

        accessibility_list = user_data_copy.get('accessibility', [])
        if isinstance(accessibility_list, list):
            accessibility_str = ';'.join(accessibility_list)
        else:
            accessibility_str = str(accessibility_list) if accessibility_list else ''

        # Format kremenchuk_str based on type
        if isinstance(kremenchuk_value, list):
            kremenchuk_str = ';'.join(kremenchuk_value)
        else:
            kremenchuk_str = str(kremenchuk_value)

        data = {
            'nickname': nickname,
            'month_year': month_year,
            'latitude': str(location_data.get('latitude', '')),
            'longitude': str(location_data.get('longitude', '')),
            'venue_title': location_data.get('venue_title', ''),
            'venue_address': venue_address,
            'enjoyment': user_data_copy.get('enjoyment', ''),
            'purpose_visit': purpose_str,
            'regularity': user_data_copy.get('regularity', ''),
            'noticed_changes': user_data_copy.get('noticed_changes', ''),
            'changes_detail': changes_detail_str,
            'wishlist': wishlist_str,
            'kremenchuk': kremenchuk_str,
            'description': user_data_copy.get('description', ''),
            'voice_submitted': user_data_copy.get('voice_submitted', ''),
            'age': user_data_copy.get('age', ''),
            'gender': user_data_copy.get('gender', ''),
            'occupation': user_data_copy.get('occupation', ''),
            'income': user_data_copy.get('income', ''),
            'language': language,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'visitor_type': visitor_type_str,
            'duration_visit': user_data_copy.get('duration_visit', ''),
            'accessibility': accessibility_str,
            'consent': consent_str
        }

        # Check for fernet availability before attempting encryption
        if fernet is None:
            flow_logger.error("Encryption not initialized. Cannot save data securely.")
            safe_send_message(
                chat_id,
                "A security error occurred. Your data could not be saved securely. Please contact support." 
                if language == 'en' else 
                "Сталася помилка безпеки. Ваші дані не могли бути збережені надійно. Зверніться до служби підтримки."
            )
            return False

        # Fields to encrypt
        fields_to_encrypt = [
            'nickname', 'month_year', 'latitude', 'longitude', 'venue_title', 
            'venue_address', 'enjoyment', 'purpose_visit', 'regularity', 
            'noticed_changes', 'changes_detail', 'wishlist', 'kremenchuk', 
            'description', 'voice_submitted', 'age', 'gender', 'occupation', 
            'income', 'language', 'visitor_type', 'duration_visit', 
            'accessibility', 'consent'
        ]

        # Enhanced encryption with error tracking
        encryption_errors = []
        for field in fields_to_encrypt:
            try:
                if data[field]:
                    # Perform encryption
                    encrypted_value = fernet.encrypt(data[field].encode()).decode()
                    data[field] = encrypted_value
                else:
                    data[field] = ''
            except Exception as e:
                error_msg = f"Error encrypting {field}: {e}"
                flow_logger.error(error_msg)
                encryption_errors.append(field)
                data[field] = ''  # Use empty string as fallback

        # Alert if any encryption errors occurred
        if encryption_errors:
            flow_logger.error(f"Failed to encrypt fields: {encryption_errors}")

        # Use short-lived SQLite connections with retry for concurrent use.
        db_connection_attempts = 0
        max_db_attempts = 3
        
        while db_connection_attempts < max_db_attempts:
            db_connection_attempts += 1
            try:
                with sqlite3.connect(db_file, check_same_thread=False) as conn:
                    conn.execute("PRAGMA busy_timeout=5000")
                    insert_query = '''
                        INSERT INTO responses (
                            nickname, month_year, latitude, longitude, venue_title, venue_address,
                            enjoyment, purpose_visit, regularity, noticed_changes,
                            changes_detail, wishlist, kremenchuk, description,
                            voice_submitted, age, gender, occupation, income, language, timestamp,
                            visitor_type, duration_visit, accessibility, consent
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''

                    # Prepare the tuple in the exact order
                    values_tuple = (
                        data['nickname'], data['month_year'], data['latitude'], data['longitude'], 
                        data['venue_title'], data['venue_address'], data['enjoyment'], 
                        data['purpose_visit'], data['regularity'], data['noticed_changes'],
                        data['changes_detail'], data['wishlist'], data['kremenchuk'], 
                        data['description'], data['voice_submitted'], data['age'],
                        data['gender'], data['occupation'], data['income'], data['language'], 
                        data['timestamp'], data['visitor_type'], data['duration_visit'], 
                        data['accessibility'], data['consent']
                    )

                    cursor = conn.execute(insert_query, values_tuple)

                    # Verify row was inserted
                    last_id = cursor.lastrowid
                    flow_logger.info(f"Inserted row ID: {last_id}")
                    
                    # Database operation successful, exit the retry loop
                    break
                    
            except sqlite3.Error as db_error:
                flow_logger.error(f"Database error attempt {db_connection_attempts}: {db_error}")
                
                if db_connection_attempts < max_db_attempts:
                    # Exponential backoff for database retries
                    retry_delay = 2 ** (db_connection_attempts - 1)
                    flow_logger.info(f"Retrying database operation in {retry_delay} seconds")
                    time.sleep(retry_delay)
                else:
                    # Last attempt failed
                    flow_logger.error("All database attempts failed, cannot save data")
                    safe_send_message(
                        chat_id,
                        "A database error occurred. Your data could not be saved. Please try again later."
                        if language == 'en' else
                        "Сталася помилка бази даних. Ваші дані не могли бути збережені. Будь ласка, спробуйте пізніше."
                    )
                    return False

        # Clear current experience data using thread-safe method
        with user_data_lock:
            if user_id in user_data:
                experience_keys = [
                    'location', 'enjoyment', 'purpose_visit', 'regularity',
                    'noticed_changes', 'changes_detail', 'wishlist', 'kremenchuk',
                    'description', 'voice_submitted', 'visitor_type', 'duration_visit',
                    'accessibility', 'description_done'  # Added description_done to the list
                ]
                for key in experience_keys:
                    user_data[user_id].pop(key, None)

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
