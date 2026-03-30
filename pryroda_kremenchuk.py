#!/usr/bin/env python
# coding: utf-8

# In[1]:


# Imports and configuration
import telebot
from telebot import types
import os
import logging
import time
import datetime
import threading
import sqlite3
from cryptography.fernet import Fernet
import hashlib
import random
from dotenv import load_dotenv
import os
import subprocess
import requests  # Add this line
# Add this at the top of your script, after imports
import sqlite3
import threading
import queue
import sys


# Try to get token from environment first
token = os.environ.get('TELEGRAM_BOT_TOKEN')
if not token:
    # If not present, try to source from credentials file
    try:
        with open('/home/ubuntu/kremenchuk/secure/credentials') as f:
            for line in f:
                if line.startswith('export TELEGRAM_BOT_TOKEN='):
                    token = line.split('=', 1)[1].strip().strip('"\'')
                    os.environ['TELEGRAM_BOT_TOKEN'] = token
                if line.startswith('export ENCRYPTION_KEY='):
                    key = line.split('=', 1)[1].strip().strip('"\'')
                    os.environ['ENCRYPTION_KEY'] = key
    except Exception as e:
        print(f"Error loading credentials: {e}")
# Set up logging with more detailed format
logging.basicConfig(
    filename='bot_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add a logger for state transitions and flow control
flow_logger = logging.getLogger('flow_control')
handler = logging.FileHandler('flow_control.log')
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'))
flow_logger.addHandler(handler)
# Change logging level to focus mostly on modifications
# Keep at INFO but we'll be more selective about what we log
flow_logger.setLevel(logging.INFO)

# Configure storage directories
local_storage_dir = '/home/ubuntu/kremenchuk'
voice_files_dir = os.path.join(local_storage_dir, 'voice_messages')

os.makedirs(local_storage_dir, exist_ok=True)
os.makedirs(voice_files_dir, exist_ok=True)


# Initialize bot
bot = telebot.TeleBot(token, threaded=True)

bot_info = bot.get_me()
bot_username = bot_info.username

# State variables
user_data = {}
user_profiles = {}
# Add at the top with other global variables
user_data_lock = threading.RLock()  # Reentrant lock for user data
user_profiles_lock = threading.RLock()  # Reentrant lock for user profiles


# Database setup
db_file = os.path.join(local_storage_dir, 'responses_kremenchuk.db')


# Near the top where encryption is initialized
# Replace the current code with:

# Encryption setup
ENCRYPTION_KEY_GLOBAL = os.environ.get('ENCRYPTION_KEY')
fernet = None  # Initialize global variable

if ENCRYPTION_KEY_GLOBAL:
    # Encode the key to bytes
    ENCRYPTION_KEY_GLOBAL = ENCRYPTION_KEY_GLOBAL.encode()
    # Validate the key
    try:
        fernet = Fernet(ENCRYPTION_KEY_GLOBAL)
    except ValueError as e:
        raise ValueError(f"Invalid encryption key: {e}")
else:
    raise ValueError("No ENCRYPTION_KEY found in environment variables. Please source your secrets file.")


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
PRIVACY_NOTICE_URL_EN = 'https://telegra.ph/Ukrainabilitys-Privacy-Notice-03-15'
PARTICIPANT_INFORMATION_SHEET_URL_EN = 'https://telegra.ph/Participant-Information-Sheet-for-Ukrainability-project-03-15'

PRIVACY_NOTICE_URL_UK = 'https://telegra.ph/Polіtika-konfіdencіjnostі-dlya-doslіdzhennya-Ukrainability-03-14'
PARTICIPANT_INFORMATION_SHEET_URL_UK = 'https://telegra.ph/Іnformacіjnij-list-dlya-uchasnikіv-proektu-Ukrainability-03-14'


# In[2]:


# Messages dictionary
messages = {
    'en': {
        'welcome': "Welcome! Please select a language.",
        'select_language': "Please select a language:",
        'language_selected': "Language set to English.",
        'project_intro': f'''Participation confirmation
Participation is voluntary. You may stop at any time, but information gathered until then can be used as described in the <a href="{PRIVACY_NOTICE_URL_EN}">privacy notice</a> and <a href="{PARTICIPANT_INFORMATION_SHEET_URL_EN}">participant information sheet</a>. Please do not participate if you are in 1) temporarily occupied territories or 2) areas near the frontline. Do not send information related to military activities. For persons aged 18+ only.

By clicking 'I agree', I confirm that I am 18+ years old, have received sufficient information about the study, and consent to participate. My data will be processed according to GDPR and Ukrainian personal data protection law.''',
        'consent_options': ["I agree", "I do not agree"],
        'consent_given': (
            "Thank you for agreeing to participate!\n\n"
            "Your participation is anonymous. Your anonymised ID is {nickname}. "
            "Be sure to remember this ID – it will unlock additional benefits for you after completing the survey."
        ),
        'consent_denied': "Thank you for your time. If you change your mind, you can restart the bot.",
        'restart_button': "Restart",
        'send_location': (
            "This survey covers the area of the left bank waterfront of the Dnipro River"
            " in the city of Kremenchuk and its surroundings. It may also include Student Park,"
            " Prydniprovskyi Park, Yuvileinyi Park, and other places and areas within"
            " walking distance of the waterfront. "
            "Please send the location on the left bank waterfront where you spent some time outdoors,"
            " or if it's a large area, just give an approximate location.\n\n"
            "To do this:\n"
            "1. Tap the attachment icon (📎) in the message bar.\n"
            "2. Select 'Location'.\n"
            "3. Move the map to the desired location.\n"
            "4. Tap 'Send this location'.\n\n"
            "Alternatively, if you prefer not to share coordinates, you can simply type the name "
            "of the location (e.g., 'Student Park') as a text message."
        ),
        'please_send_location': (
            "Invalid input. Please send the location as instructed.\n\n"
            "To do this:\n"
            "1. Tap the attachment icon (📎) in the message bar.\n"
            "2. Select 'Location'.\n"
            "3. Move the map to the desired location.\n"
            "4. Tap 'Send this location'.\n\n"
            "Alternatively, you can simply type the name of the location as a text message."
        ),
        'enjoyment_question': "How did you find your time spent at this place?",
        'enjoyment_options': [
            "Very enjoyable",
            "Enjoyable",
            "Neutral",
            "Not enjoyable",
            "Not enjoyable at all"
        ],
        'visitor_type_question': "Who would you recommend this place to?",
        'visitor_type_options': [
            "Solo visitors",
            "Families",
            "Couples",
            "Groups of friends",
            "People with pets",
            "Other"
        ],
        'duration_question': "How much time did you spend in the area around this location during your visit?",
        'duration_options': [
            "Passing by or a short stop",
            "1–2 hours visit",
            "Most of the day",
            "Part of a trip for a few days",
            "Part of a longer stay for a few weeks or more",
            "Prefer not to disclose"
        ],
        'invalid_rating': "Invalid input. Please select an option requested in the question.",
        'purpose_visit': "What outdoor activities were your main reasons for visiting this place?",
        'other_purpose': "Please specify your other purpose of visit. ",
        'other_visitor_type': "Please specify who else would appreciate this place:",
        'other_accessibility': "Please specify another way you traveled to this place:",
        'other_changes': "Please specify what else has changed at this place:",
        'other_wishlist': "Please specify what else you would like to improve or change:",
        'other_kremenchuk': "Please specify your own situation:",
        'regularity_question': "Do you visit this place regularly, occasionally, or is this your first time?",
        'changes_question': "Have you noticed any differences in this place since the full-scale invasion?",
        'changes_detail_question': "What exactly has changed? You can select multiple options.",
        'wishlist_question': "Would you like to improve/change something in this place/area?",
        'kremenchuk_question': "For how long do you live in Kremenchuk city? ",
        'add_description': (
            "We'd love to hear more about your experience. Please share any stories, feelings, or memorable moments from your visit. "
            "You can type your response or send a voice message. The voice message will be transcribed to text for analysis, and the original message will be deleted immediately afterward to protect your privacy. If you'd prefer to skip and finish, please press 'Skip'."
        ),
        'thank_you': "Thank you! Your data has been received.",
        'thank_you_lottery': "Thank you! Your data has been received. Good luck in the lottery!",
        'thank_you_no_lottery': "Thank you! Your data has been received.",
        'skip_button': "Skip",
        'age_question': "Please select your age group:",
        'gender_question': "Please select your gender:",
        'occupation_question': "Please select your occupational status:",
        'income_question': "Please select your monthly income level:",
        'done_button': "Done",
        'accessibility_question': "How did you travel to this place? Select all relevant options. ",
        'accessibility_options': [
            "By foot",
            "By bicycle",
            "By public transport",
            "By car",
            "By shared mobility (e.g., taxi)",
            "Other"],
        'continue_question': (
            "Your anonymised ID is {nickname}. With your saved ID, you participate in a monthly lottery for a 1000 UAH certificate. Be sure to join our channel https://t.me/ukrainability and follow the lottery results on the first day of each month — you might be the next winner!"
            "Would you like to submit another place or stop here?"
        ),
        'continue_options': ["Continue", "Stop"],
        'location_received': "Location received",
        'responses_so_far': "Your responses so far:",
        'description_skipped': "Description skipped.",
        'your_description': "Your description:",
        'selected': "Selected:",
        'unselected': "Unselected:",
        'you_selected': "You selected:",
        'voice_message_submitted': "Voice message submitted.",
        'error_occurred': "An error occurred. Please try again later.",
        'invalid_selection': "Invalid selection.",
        'your_response': "Your response:",
        'confirm_responses': "Please review your responses above. Do you confirm them or would like to modify anything?",
        'modify_responses': "I want to modify my responses",
        'confirm_submission': "I confirm my responses",
        'select_questions_to_modify': "Please select the question(s) to modify your responses:",
        'submission_confirmed': "Thank you! Your responses have been submitted.",
        'done_button': "Done",
        'please_send_text_or_voice': "Invalid input. Please send a text message or a voice message.",
        'please_select_at_least_one': "Please select at least one option.",
        'labels': {
            'location': 'Location',
            'enjoyment': 'Enjoyment',
            'purpose_visit': 'Purpose of visit',
            'regularity': 'Regularity',
            'accessibility': 'Accessibility',
            'noticed_changes': 'Noticed changes',
            'changes_detail': 'Changes detail',
            'wishlist': 'Improvements wished',
            'kremenchuk': 'Time living in Kremenchuk',
            'description': 'Description',
            'age': 'Age',
            'gender': 'Gender',
            'occupation': 'Occupation',
            'income': 'Income',
            'visitor_type': 'Recommended for',
            'duration_visit': 'Duration of visit',
        },
        'options': {
            'purpose_visit': [
                "Relaxation: nature, sunbathing, rest",
                "Activity: walking, running, cycling",
                "Professional sports or competitions",
                "Communication: meetings, holidays, events",
                "Gastronomy: barbecue, picnic",
                "Excursions, educational activities",
                "Bird watching, nature observation",
                "Fishing",
                "Gathering: mushrooms, berries, herbs",
                "Gardening: plant care",
                "Creativity: art, photography, performances",
                "Spiritual practices and meditation",
                "Other"
            ],
            'regularity': [
                "Very frequently: several times a week",
                "Frequently: several times a month",
                "Regularly (multiple times a year or more)",
                "Occasionally (once a year or less)",
                "One-time visit",
                "Visited before 2022 but not anymore",
                "Prefer not to disclose"
            ],
            'noticed_changes': [
                "Yes, positive changes",
                "Yes, negative changes",
                "No noticeable changes/I don't know"
            ],
            'changes_detail': [
                "Environment (cleanliness, landscape)",
                "Accessibility (e.g., transport, paths)",
                "Services (e.g., maintenance)",
                "Safety (perception, risks, etc.)",
                "Number of visitors",
                "Other"
            ],
            'wishlist': [
                "Water quality in the river/lake",
                "Cleaner air",
                "Less noise",
                "More shade, fountains in summer",
                "More facilities and services",
                "Better lighting at night",
                "Pedestrian safety (traffic)",
                "Safer pedestrian areas",
                "More convenient transportation",
                "Access for people with limited mobility",
                "More greenery",
                "Everything is fine, no suggestions",
                "Other"
            ],
            'kremenchuk': [
                "Less than 1 year",
                "1-3 years",
                "3-10 years",
                "10-20 years",
                "My whole life",
                "I don't live in Kremenchuk",
                "Other",
                "Prefer not to disclose"
            ],
            'age': [
                "18-25", "26-40", "41-60", "Above 60", "Prefer not to disclose"
            ],
            'gender': [
                "Male", "Female", "Other", "Prefer not to disclose"
            ],
            'occupation': [
                "Working", "Not working", "Student", "Retired", "Military service", "Other", "Prefer not to disclose"
            ],
            'income': [
                "0-5000 UAH", "5001-10000 UAH", "10001-20000 UAH", "More than 20000 UAH", "Prefer not to disclose"
            ],
        },
    },
    'uk': {
        'welcome': "Ласкаво просимо! Будь ласка, оберіть мову.",
        'select_language': "Будь ласка, оберіть мову:",
        'language_selected': "Мову встановлено на українську.",
        'project_intro': f'''Підтвердження участі
Участь є добровільною. Ви можете припинити в будь-який час, але вже зібрана інформація може використовуватись, як описано в <a href="{PRIVACY_NOTICE_URL_UK}">політиці конфіденційності</a> та <a href="{PARTICIPANT_INFORMATION_SHEET_URL_UK}">інформаційному листі учасника</a>. Не беріть участь, якщо ви на 1) тимчасово окупованих або 2) прифронтових територіях. Не надсилайте інформацію, пов'язану з воєнною активністю. Тільки для осіб від 18 років.

Натискаючи «Я погоджуюсь», я підтверджую, що мені більше 18 років, я отримав(ла) достатньо інформації про дослідження та погоджуюсь взяти участь. Дані будуть оброблятись відповідно до європейського та українського законодавства про захист персональних даних.''',
        'consent_options': ["Я згоден/згодна", "Я не згоден/не згодна"],
        'consent_given': (
            "Дякуємо за вашу згоду на участь!\n\n"
            "Ваша участь є анонімною. Ваш анонімний ID: {nickname}. "
            "Будь-ласка, запам'ятайте цей ID – він відкриє вам додаткові переваги після завершення опитування"
        ),
        'consent_denied': "Дякуємо за ваш час. Якщо ви передумаєте, ви можете перезапустити бота.",
        'restart_button': "Перезапустити",
        'send_location': (
            "Дане опитування розглядає територію набережної лівого берега річки Дніпро в місті Кременчук "
            "та на його околицях. Також можуть бути позначені Студентський парк, Придніпровський парк, "
            "Ювілейний парк та інші місця та території в пішохідній доступності до набережної. "
            "Будь ласка, надішліть місце на набережній лівого берега, де провели якийсь час на свіжому повітрі;"
            " якщо це місце велике за площею, просто оберіть приблизну локацію.\n\n"
            "Щоб зробити це:\n"
            "1. Натисніть на іконку вкладення (📎) у рядку повідомлень.\n"
            "2. Оберіть 'Розташування'.\n"
            "3. Перемістіть карту до бажаного місця.\n"
            "4. Натисніть 'Надіслати вибране розташування'.\n\n"
            "Альтернативно, якщо вам важко знайти місце на карті, ви можете просто ввести назву "
            "місця (наприклад, Студентський парк) як текстове повідомлення."
        ),
        'please_send_location': (
            "Невірний формат. Будь ласка, надішліть локацію, як вказано в інструкції.\n\n"
            "Щоб зробити це:\n"
            "1. Натисніть на іконку вкладення (📎) у рядку повідомлень.\n"
            "2. Оберіть 'Розташування'.\n"
            "3. Перемістіть карту до бажаного місця.\n"
            "4. Натисніть 'Надіслати вибране розташування'."
        ),
        'enjoyment_question': "Як вам сподобався ваш час, проведений у цьому місці?",
        'enjoyment_options': [
            "Дуже сподобався",
            "Сподобався",
            "Нейтрально",
            "Не сподобався",
            "Зовсім не сподобався"
        ],
        'visitor_type_question': "Кому б ви порекомендували це місце?",
        'visitor_type_options': [
            "Для прогулянок наодинці",
            "Парам",
            "Сім'ям з дітьми",
            "Великим компаніям",
            "Людям з домашніми тваринами",
            "Інше (кому саме?)"
        ],
        'other_visitor_type_prompt': "Будь ласка, вкажіть, кому б сподобалось це місце:",
        'other_visitor_type': "Будь ласка, вкажіть, хто ще оцінив би це місце:",
        'other_purpose': "Будь ласка, вкажіть чим ще ви займались в цьому місці:",
        'other_accessibility': "Будь ласка, вкажіть інший спосіб, яким ви дісталися до цього місця:",
        'other_changes': "Будь ласка, вкажіть, що ще змінилося в цьому місці:",
        'other_wishlist': "Будь ласка, вкажіть, що ще ви хотіли б покращити або змінити:",
        'other_kremenchuk': "Будь ласка, вкажіть вашу власну ситуацію:",
        'duration_question': "Скільки часу ви провели у цій місцевості під час вашого візиту?",
        'duration_options': [
            "Проходив повз або коротка зупинка",
            "1–2 години",
            "Більшу частину дня",
            "Поїздка на кілька днів",
            "Тривала поїздка, тиждень+",
            "Надаю перевагу не вказувати"
        ],
        'invalid_rating': "Недійсний вибір. Будь ласка, оберіть варіант, запропонований у запитанні.",
        'purpose_visit': "Чим ви займалися в цьому місці? Оберіть усі варіанти, які найкраще підходять, та/або додайте свій, якщо його немає у списку.",
        'regularity_question': "Ви відвідуєте це місце регулярно, час від часу, чи лише один раз?",
        'changes_question': "Чи помітили ви якісь зміни в цьому місці після повномасштабного вторгнення?",
        'changes_detail_question': "Що саме змінилося? Ви можете обрати декілька варіантів.",
        'wishlist_question': "Що, на вашу думку, варто покращити чи змінити в цьому місці?",
        'kremenchuk_question': "Як довго ви проживаєте в місті Кременчук?",
        'add_description': (
            "Ми були б раді почути більше про ваш досвід. Будь ласка, поділіться будь-якими історіями, почуттями або пам'ятними моментами від вашого візиту. "
            "Ви можете написати відповідь або надіслати голосове повідомлення. Голосове повідомлення буде перетворено в текст для аналізу, а оригінальне голосове повідомлення буде негайно видалене для захисту вашої конфіденційності. Якщо ви хочете пропустити та завершити, будь ласка, натисніть 'Пропустити'."
        ),
        'thank_you': "Дякуємо! Ваші дані були отримані.",
        'skip_button': "Пропустити",
        'age_question': "Будь ласка, оберіть вашу вікову групу:",
        'gender_question': "Будь ласка, оберіть вашу стать:",
        'occupation_question': "Будь ласка, оберіть ваш основний професійний статус:",
        'income_question': "Будь ласка, оберіть рівень вашого місячного доходу:",
        'done_button': "Готово",
        'accessibility_question': "Яким чином ви дісталися до цього місця? Оберіть усі відповідні варіанти.",
        'accessibility_options': [
            "Пішки",
            "На велосипеді",
            "Громадським транспортом",
            "Автомобілем",
            "Таксі чи каршеринг",
            "Інше"
        ],
        'continue_question': (
            "Ваш анонімний ID: {nickname}. Зі збереженим ID ви берете участь у щомісячному розіграші сертифікату на 1000 грн. Заохочуємо доєднатись до нашого каналу https://t.me/ukrainability та слідкувати за результатами розіграшу першого числа кожного місяця — можливо, саме ви станете наступним переможцем! "
            "Ви бажаєте розповісти про інше місце чи завершити?"
        ),
        'continue_options': ["Продовжити", "Завершити"],
        'location_received': "Локацію отримано",
        'responses_so_far': "Ваші відповіді наразі:",
        'description_skipped': "Опис пропущено.",
        'your_description': "Ваш опис:",
        'selected': "Вибрано:",
        'unselected': "Знято вибір:",
        'you_selected': "Ви обрали:",
        'voice_message_submitted': "Голосове повідомлення надіслано.",
        'error_occurred': "Виникла помилка. Будь ласка, спробуйте пізніше.",
        'invalid_selection': "Недійсний вибір.",
        'your_response': "Ваша відповідь:",
        'confirm_responses': "Ви підтверджуєте відповіді, чи хотіли б щось змінити?",
        'modify_responses': "Хочу щось змінити",
        'confirm_submission': "Підтверджую",
        'select_questions_to_modify': "Будь-ласка, оберіть питання для зміни відповіді:",
        'submission_confirmed': "Дякую! Відповіді було збережено",
        'done_button': "Готово",
        'please_select_at_least_one': "Будь ласка, оберіть принаймні один варіант.",
        'please_send_text_or_voice': "Невірний формат. Будь ласка, надішліть текстове або голосове повідомлення.",
        'labels': {
            'location': 'Локація',
            'enjoyment': 'Якість часу',
            'purpose_visit': 'Мета візиту',
            'regularity': 'Регулярність',
            'accessibility': 'Доступність',
            'noticed_changes': 'Помічені зміни',
            'changes_detail': 'Деталі змін',
            'wishlist': 'Побажання покращень',
            'kremenchuk': 'Час проживання в Кременчуці',
            'visitor_type': 'Рекомендовано',
            'duration_visit': 'Тривалість відвідування',
            'description': 'Опис',
            'age': 'Вікова група',
            'gender': 'Стать',
            'occupation': 'Рід занять',
            'income': 'Рівень доходу'
        },
        'options': {
            'purpose_visit': [
                "Релакс: природа, засмага, відпочинок",
                "Активність: ходьба, біг, велосипед",
                "Професійний спорт або змагання",
                "Спілкування: зустрічі, свята, події",
                "Гастрономія: барбекю, пікнік",
                "Екскурсії, освітні заходи",
                "Спостереження за птахами, природою",
                "Риболовля",
                "Збирання: гриби, ягоди, трави",
                "Садівництво: догляд за рослинами",
                "Творчість: мистецтво, фото, виступи",
                "Духовні практики та медитація",
                "Інше"
            ],
            'regularity': [
                "Дуже часто: кілька разів на тиждень",
                "Часто: кілька разів на місяць",
                "Регулярно: кілька разів на рік і частіше",
                "Час від часу: раз на рік і рідше",
                "Разове відвідування",
                "Відвідував(-ла) до 2022 р., але не зараз",
                "Надаю перевагу не вказувати"
            ],
            'noticed_changes': [
                "Так, позитивні зміни",
                "Так, негативні зміни",
                "Не помітив(ла) змін, або не знаю"
            ],
            'changes_detail': [
                "Чистота довкілля, краєвид",
                "Доступність (дороги, транспорт)",
                "Сервіси (заклади)",
                "Безпека (ризики, освітлення)",
                "Кількість відвідувачів",
                "Рекреаційна інфраструктура",
                "Інше"
            ],
            'wishlist': [
                "Чистіша вода у водоймах",
                "Чистіше повітря",
                "Менше шуму",
                "Більше тіні, фонтанів в спеку",
                "Більше закладів і сервісів",
                "Краще освітлення вночі",
                "Безпечніші пішоходні зони",
                "Зручніший транспорт",
                "Доступ для малобільних людей",
                "Більше зелені",
                "Все влаштовує, не маю побажань",
                "Інше"
            ],
            'kremenchuk': [
                "Менше року",
                "1-3 роки",
                "3-10 років",
                "10-20 років",
                "Все життя",
                "Не проживаю у Кременчуці",
                "Інше",
                "Надаю перевагу не вказувати"
            ],
            'age': [
                "18-25", "26-40", "41-60", "Понад 60", "Надаю перевагу не вказувати"
            ],
            'gender': [
                "Чоловіча", "Жіноча", "Інше", "Надаю перевагу не вказувати"
            ],
            'occupation': [
                "Працюю", "Не працюю", "Навчаюсь", "На пенсії", "Військова служба", "Інше", "Надаю перевагу не вказувати"
            ],
            'income': [
                "0-5000 грн", "5001-10000 грн", "10001-20000 грн", "Більше 20000 грн", "Надаю перевагу не вказувати"
            ],
        },
    }
}


# In[3]:


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
    with db_lock:
        conn = sqlite3.connect(db_file, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT nickname FROM user_nicknames')
        results = cursor.fetchall()
        conn.close()
        return set([row[0] for row in results])


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
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT nickname FROM user_nicknames
                WHERE user_hash = ?
                ORDER BY month_year DESC LIMIT 1
            ''', (user_hash,))
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            return_db_connection(conn)

# Add to the global variables section
# For tracking message IDs for each user
message_id_registry = {}
message_id_lock = threading.Lock()

# Add these functions for message ID tracking
def register_message_id(user_id, message_type, message_id):
    """
    Register a message ID for a specific user and message type.
    """
    with message_id_lock:
        if user_id not in message_id_registry:
            message_id_registry[user_id] = {}
        message_id_registry[user_id][message_type] = message_id

def get_message_id(user_id, message_type):
    """
    Get a previously registered message ID.
    """
    with message_id_lock:
        return message_id_registry.get(user_id, {}).get(message_type)

def clear_message_ids(user_id):
    """
    Clear all message IDs for a user.
    """
    with message_id_lock:
        if user_id in message_id_registry:
            message_id_registry.pop(user_id)

# Enhanced keyboard send function that tracks the message ID
def send_keyboard_message(chat_id, user_id, text, keyboard, message_type, parse_mode=None):
    """
    Send a message with a keyboard and register its ID for future updates.
    """
    try:
        msg = safe_send_message(chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)
        register_message_id(user_id, message_type, msg.message_id)
        return msg
    except Exception as e:
        flow_logger.error(f"Error sending keyboard message: {e}")
        # Fall back to regular send without tracking
        return safe_send_message(chat_id, text, reply_markup=keyboard, parse_mode=parse_mode)

# Enhanced edit keyboard function that uses the tracked ID
def edit_keyboard(user_id, chat_id, message_type, new_keyboard):
    """
    Update a previously sent keyboard using the tracked message ID.
    """
    message_id = get_message_id(user_id, message_type)
    if not message_id:
        flow_logger.warning(f"No message ID found for {message_type}, cannot edit keyboard")
        return False
    
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=new_keyboard
        )
        return True
    except ApiTelegramException as e:
        if "message is not modified" in str(e):
            # This is normal, not an error
            return True
        else:
            flow_logger.error(f"Failed to edit keyboard: {e}")
            return False
    except Exception as e:
        flow_logger.error(f"Error editing keyboard: {e}")
        return False


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


# Add to the top of your file
from telebot.apihelper import ApiTelegramException

# Replace the existing send_message functions with this enhanced version
def safe_send_message(chat_id, text, reply_markup=None, parse_mode=None, max_retries=3):
    """
    Safely send a message with retry logic for rate limits and connection issues.
    """
    for attempt in range(max_retries):
        try:
            return bot.send_message(
                chat_id, 
                text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        except ApiTelegramException as e:
            # Handle rate limiting
            if "429" in str(e) or "too many requests" in str(e).lower():
                retry_after = 3
                # Try to extract retry_after value if provided by Telegram
                if hasattr(e, 'result') and isinstance(e.result, dict):
                    retry_after = e.result.get('parameters', {}).get('retry_after', 3)
                
                flow_logger.warning(f"Rate limited, waiting {retry_after}s before retry {attempt+1}/{max_retries}")
                time.sleep(retry_after)
                continue
            elif attempt < max_retries - 1:
                # For other API errors, retry with backoff
                flow_logger.warning(f"API error: {e}, retrying in {2**attempt}s")
                time.sleep(2**attempt)
                continue
            else:
                # Last attempt failed, log and raise
                flow_logger.error(f"Failed to send message after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            # For non-API errors, retry once quickly
            if attempt == 0:
                flow_logger.warning(f"Error sending message: {e}, retrying once")
                time.sleep(1)
                continue
            else:
                flow_logger.error(f"Failed to send message: {e}")
                raise


def save_user_nickname(user_hash, nickname):
    month_year = datetime.datetime.now().strftime('%Y-%m')
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO user_nicknames
                (user_hash, nickname, month_year)
                VALUES (?, ?, ?)
            ''', (user_hash, nickname, month_year))
            conn.commit()
        finally:
            return_db_connection(conn)


def escape_html(text):
    if not isinstance(text, str):
        text = str(text)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

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
    except BaseException:
        # Ultimate fallback
        return 'en'


def handle_callback_error(call, e, func_name):
    """
    Enhanced error handler for callback functions with proper state clearing.
    """
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id

        # Log the error with full details
        logging.exception(f"Error in {func_name}: {e}")

        # Get language safely
        language = safe_get_language(user_id)
        error_msg = messages[language].get(
            'error_occurred', "An error occurred. Please try again later.")

        # Attempt to clear user's state in a thread-safe way
        with user_data_lock:
            if user_id in user_data:
                # Clear all temporary state variables
                keys_to_remove = []
                for k in user_data[user_id]:
                    if (k.startswith('temp_') or 
                        k == 'awaiting_multiple_select' or 
                        k == 'current_question' or 
                        k == 'modifying' or 
                        k == 'modifying_field'):
                        keys_to_remove.append(k)
                
                for k in keys_to_remove:
                    user_data[user_id].pop(k, None)

        # Use safe send to inform the user
        try:
            bot.answer_callback_query(call.id, "Error occurred / Виникла помилка")
            safe_send_message(chat_id, error_msg)
            
            # Provide a way for the user to recover
            inline_kb = types.InlineKeyboardMarkup()
            restart_text = "Restart" if language == 'en' else "Перезапустити"
            restart_button = types.InlineKeyboardButton(text=restart_text, callback_data='restart')
            inline_kb.add(restart_button)
            
            safe_send_message(
                chat_id,
                "You can restart the survey if needed:" if language == 'en' else 
                "Ви можете перезапустити опитування за потреби:",
                reply_markup=inline_kb
            )
        except Exception as send_error:
            logging.critical(f"Failed to send error message to user: {send_error}")
    except Exception as recovery_error:
        # Last resort logging if the error handler itself fails
        logging.critical(f"Error handler failed: {recovery_error}")


def safe_answer_callback(call, message):
    """Safely answer a callback query, ignoring expired queries"""
    try:
        bot.answer_callback_query(call.id, message)
    except telebot.apihelper.ApiTelegramException as e:
        if "query is too old" in str(e) or "query ID is invalid" in str(e):
            # Quietly ignore expired callback queries
            flow_logger.info(f"Ignoring expired callback query: {e}")
        else:
            # Re-raise other API exceptions
            flow_logger.error(f"API exception in safe_answer_callback: {e}")
            # Try to send a message to inform user something went wrong
            try:
                user_id = call.from_user.id
                language = safe_get_language(user_id)
                bot.send_message(call.message.chat.id, messages[language].get(
                    'error_occurred', "An error occurred. Please try again."))
            except BaseException:
                pass


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
            except BaseException:
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


def check_telegram_connection():
    """Check if the connection to Telegram API is active"""
    try:
        bot.get_me()
        return True
    except Exception as e:
        flow_logger.error(f"Connection check failed: {e}")
        return False


def recover_user_sessions():
    """Attempt to recover user sessions after bot restart"""
    try:
        flow_logger.info("Attempting to recover user sessions...")

        # Get a snapshot of current user_data to avoid modification during
        # iteration
        users_to_recover = list(user_data.keys())
        recovered_count = 0

        for user_id in users_to_recover:
            try:
                # Ensure basic data structures exist
                if 'language' not in user_data[user_id]:
                    if user_id in user_profiles and 'language' in user_profiles[user_id]:
                        user_data[user_id]['language'] = user_profiles[user_id]['language']
                    else:
                        # Can't recover without language
                        continue

                # Restore nickname from database if needed
                if 'nickname' not in user_data[user_id]:
                    user_hash = hashlib.sha1(str(user_id).encode()).hexdigest()
                    nickname = get_user_nickname(user_hash)
                    if nickname:
                        user_data[user_id]['nickname'] = nickname

                # Mark recovery state - will be used to inform users later
                user_data[user_id]['session_recovered'] = True
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

        # First identify which users to remove
        for user_id, data in user_data.items():
            last_activity = data.get('last_activity_time', 0)
            if last_activity < cutoff_time:
                users_to_remove.append(user_id)

        # Then remove them
        for user_id in users_to_remove:
            try:
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
    if user_id in user_data:
        user_data[user_id]['last_activity_time'] = time.time()
    else:
        # If user doesn't exist in user_data, initialize it
        user_data[user_id] = {'last_activity_time': time.time()}
# In[4]:


# Database functions
def initialize_database():
    conn = None
    with db_lock:
        try:
            conn = sqlite3.connect(db_file, check_same_thread=False)
            cursor = conn.cursor()
            
            # Set pragmas for better performance
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")

            # Make sure all columns exist
            create_responses_table_query = '''
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nickname TEXT,
                    month_year TEXT,
                    latitude TEXT,
                    longitude TEXT,
                    venue_title TEXT,
                    venue_address TEXT,
                    enjoyment TEXT,
                    purpose_visit TEXT,
                    regularity TEXT,
                    noticed_changes TEXT,
                    changes_detail TEXT,
                    wishlist TEXT,
                    kremenchuk TEXT,
                    description TEXT,
                    voice_submitted TEXT,
                    age TEXT,
                    gender TEXT,
                    occupation TEXT,
                    income TEXT,
                    language TEXT,
                    timestamp TEXT,
                    visitor_type TEXT,
                    duration_visit TEXT,
                    accessibility TEXT,
                    consent TEXT
                );
            '''
            cursor.execute(create_responses_table_query)

            create_nicknames_table_query = '''
                CREATE TABLE IF NOT EXISTS user_nicknames (
                    user_hash TEXT,
                    nickname TEXT NOT NULL,
                    month_year TEXT,
                    PRIMARY KEY (user_hash, month_year)
                );
            '''
            cursor.execute(create_nicknames_table_query)
            
            # Add indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nickname ON responses(nickname)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_hash ON user_nicknames(user_hash)")

            conn.commit()
            
            print("Database initialized successfully")
            flow_logger.info("Database initialized successfully")
            
            # Check if connection pool is empty before initializing
            if db_pool.empty():
                initialize_connection_pool()

        except Exception as e:
            logging.exception(f"Error initializing responses database: {e}")
            raise e
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

def hide_keyboard(chat_id):
    """
    Helper function to hide the keyboard in the chat.
    Uses a completely invisible character (zero-width space) to hide the keyboard.

    Args:
        chat_id (int): Telegram chat ID where keyboard should be hidden
    """
    try:
        remove_keyboard = types.ReplyKeyboardRemove()
        # Use zero-width space (U+200B) - completely invisible character
        bot.send_message(
            chat_id,
            "\u200B",  # Zero-width space character
            reply_markup=remove_keyboard
        )
    except Exception as e:
        # Just log, don't interrupt flow if this fails
        logging.warning(f"Failed to hide keyboard: {e}")

# In[5]:


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

        user_hash = hashlib.sha1(str(user_id).encode()).hexdigest()
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
                        nickname=f"<b>{nickname}</b>")
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
                        nickname=f"<b>{nickname}</b>")
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


# In[6]:


# Language and consent handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith('language_'))
def handle_language_selection(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        data = call.data.split('_')[1]

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
                msg = bot.send_message(
                    chat_id, messages[language]['send_location'])
                bot.register_next_step_handler(msg, handle_location_step)
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
        idx = int(call.data.split('_')[1])

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
                    nickname=f"<b>{nickname}</b>")
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
        msg = bot.send_message(chat_id, messages[language]['send_location'])
        bot.register_next_step_handler(msg, handle_location_step)
    except Exception as e:
        logging.exception(f"Error in handle_post_consent_continue: {e}")
        bot.send_message(chat_id, "An error occurred. Please try again later.")


# In[7]:


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
                f"User {user_id}: Coordinate location received - lat: {latitude}, long: {longitude}")

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
                f"User {user_id}: Venue location received - title: {venue_title}, address: {venue_address}")

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
                    bot.send_message(
                        chat_id, messages[language]['please_send_location'])
                    bot.register_next_step_handler(
                        message, handle_location_step)
                    return

            # Debug logs for text-based location
            print(
                f"DEBUG: User {user_id} sent text location: '{location_text}'")
            flow_logger.info(
                f"User {user_id}: Text location received: '{location_text}'")

            # Store in location data with empty coordinates but populated
            # venue_address
            user_data[user_id]['location'] = {
                'latitude': '',  # Empty as exact coordinates are not provided
                'longitude': '',  # Empty as exact coordinates are not provided
                'venue_title': '',
                'venue_address': location_text  # Store the text input in venue_address
            }

            # Verify data was stored correctly
            venue_address_stored = user_data[user_id]['location'].get(
                'venue_address', '')
            print(
                f"DEBUG: Stored in user_data: venue_address='{venue_address_stored}'")
            flow_logger.info(
                f"User {user_id}: Stored venue_address='{venue_address_stored}' in user_data")

            # Confirmation message
            location_received_msg = f"📍 {messages[language]['location_received']}: {location_text}"
            bot.send_message(
                chat_id,
                location_received_msg,
                reply_markup=remove_keyboard)

            # Now ask for purpose of visit
            ask_purpose_visit(chat_id, user_id, language)

        else:
            msg = bot.send_message(
                chat_id, messages[language]['please_send_location'])
            bot.register_next_step_handler(msg, handle_location_step)
    except Exception as e:
        logging.exception(f"Error in handle_location_step: {e}")
        try:
            language = "en"  # Default fallback
            if user_id in user_data and 'language' in user_data[user_id]:
                language = user_data[user_id]['language']
            error_msg = messages[language].get(
                'error_occurred', "An error occurred. Please try again later.")
            bot.reply_to(message, error_msg)
        except:
            # Fallback if language is not accessible
            bot.reply_to(
                message,
                "An error occurred. Please try again later. / Виникла помилка. Будь ласка, спробуйте пізніше.")

# In[8]:


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
        data = call.data.split('_')[1]

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
            idx = int(data)
            # Remove the 'Other' option
            options = messages[language]['options']['purpose_visit'][:-1]
            if 0 <= idx < len(options):
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
            else:
                safe_answer_callback(
                    call, messages[language].get(
                        'invalid_selection', "Invalid selection."))
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

# In[9]:


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
        idx = int(call.data[len('enjoyment_'):])

        if 0 <= idx < len(options):
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
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(call, messages[language]['invalid_rating'])
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
        data = call.data.split('_')[1]

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
            idx = int(data)
            if 0 <= idx < len(visitor_options):
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
            else:
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, messages[language]['invalid_selection'])
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

# In[10]:


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
        idx = int(call.data.split('_')[1])

        if 0 <= idx < len(duration_options):
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
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(call, messages[language]['invalid_selection'])
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

        data = call.data.split('_', 1)[1]
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

# In[11]:


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

        # Store initial selection in temp storage
        selected_idx = int(call.data.split('_')[1])
        options = messages[language]['options']['regularity']

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

        data_parts = call.data.split('_')
        if len(data_parts) >= 3 and data_parts[2].isdigit():
            idx = int(data_parts[2])
            options = messages[language]['options']['frequency_change']

            if 0 <= idx < len(options):
                selected_frequency_change = options[idx]
                previous_freq_change = user_data[user_id].get(
                    'frequency_change', '')

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
                    # Set a consistent value for noticed_changes for data
                    # integrity
                    user_data[user_id]['noticed_changes'] = selected_frequency_change

                # Determine next question based on modification state
                if user_data[user_id].get('modifying'):
                    if selected_frequency_change in didnt_visit_options:
                        # Skip noticed_changes and go to final confirmation
                        user_data[user_id].pop('modifying')
                        user_data[user_id].pop('modifying_field', None)
                        ask_final_confirmation(chat_id, user_id, language)
                    else:
                        # If noticed_changes not already answered or we're
                        # directly modifying frequency_change, proceed to ask
                        # it
                        ask_noticed_changes(chat_id, user_id, language)
                else:
                    # Normal flow if not modifying
                    if selected_frequency_change in didnt_visit_options:
                        # Skip to wishlist question
                        ask_wishlist(chat_id, user_id, language)
                    else:
                        ask_noticed_changes(chat_id, user_id, language)
            else:
                bot.answer_callback_query(
                    call.id, messages[language].get(
                        'invalid_selection', "Invalid selection."))
        else:
            bot.answer_callback_query(
                call.id, messages[language].get(
                    'invalid_selection', "Invalid selection."))
    except Exception as e:
        logging.exception(f"Error in handle_frequency_change_selection: {e}")
        bot.send_message(
            chat_id,
            messages[language].get(
                'error_occurred',
                "An error occurred. Please try again later."))


# In[12]:


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

        data = call.data.split('_')[2]
        options = messages[language]['options']['noticed_changes']
        idx = int(data)

        if 0 <= idx < len(options):
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
        else:
            # Replace direct call with safe_answer_callback
            safe_answer_callback(
                call, messages[language].get(
                    'invalid_selection', "Invalid selection."))
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

        data = call.data.split('_')[2]
        # Remove the 'Other' option
        options = messages[language]['options']['changes_detail'][:-1]

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
            idx = int(data)
            if 0 <= idx < len(options):
                selected_option = options[idx]

                # Toggle selection
                if selected_option in user_data[user_id]['changes_detail']:
                    user_data[user_id]['changes_detail'].remove(
                        selected_option)
                    # Replace direct call with safe_answer_callback
                    safe_answer_callback(
                        call, f"{messages[language]['unselected']} {selected_option}")
                    flow_logger.info(
                        f"User {anon_id}: Unselected changes_detail option: {selected_option}")
                else:
                    user_data[user_id]['changes_detail'].append(
                        selected_option)
                    # Replace direct call with safe_answer_callback
                    safe_answer_callback(
                        call, f"{messages[language]['selected']} {selected_option}")
                    flow_logger.info(
                        f"User {anon_id}: Selected changes_detail option: {selected_option}")

                update_changes_detail_selection_keyboard(
                    call.message, user_id, language)
            else:
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, messages[language].get(
                        'invalid_selection', "Invalid selection."))
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

# In[13]:


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
        data = call.data.split('_')[1]

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
            idx = int(data)

            if 0 <= idx < len(options):
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

                update_wishlist_keyboard(
                    call.message, user_id, language, options)
            else:
                # Replace direct call with safe_answer_callback
                safe_answer_callback(
                    call, messages[language]['invalid_selection'])
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

# In[14]:


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

        idx = int(call.data.split('_')[1])
        options = messages[language]['options']['age']

        if 0 <= idx < len(options):
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
        else:
            bot.answer_callback_query(
                call.id, messages[language].get(
                    'invalid_selection', "Invalid selection."))
    except Exception as e:
        logging.exception(f"Error in handle_age_selection: {e}")
        try:
            # Safely get language with a fallback
            language = user_data.get(user_id, {}).get('language', 'en')
            error_msg = messages[language].get(
                'error_occurred', "An error occurred. Please try again later.")
        except BaseException:
            # Ultimate fallback if everything else fails
            error_msg = "An error occurred. Please try again later. / Виникла помилка. Будь ласка, спробуйте пізніше."

        try:
            bot.send_message(chat_id, error_msg)
        except BaseException:
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
        except BaseException:
            # Ultimate fallback if everything else fails
            error_msg = "An error occurred. Please try again later. / Виникла помилка. Будь ласка, спробуйте пізніше."

        try:
            bot.send_message(chat_id, error_msg)
        except BaseException:
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
        data = call.data.split('_')[1]

        if data.isdigit():
            idx = int(data)
            options = messages[language]['options']['gender']

            if 0 <= idx < len(options):
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
                        logging.exception(
                            f"Error in handle_gender_selection: {e}")

                # Notify user of selection (but not confirmation yet)
                bot.answer_callback_query(
                    call.id, f"{messages[language]['selected']} {selected_gender}")
            else:
                bot.answer_callback_query(
                    call.id, messages[language]['invalid_selection'])
        else:
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
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
        data = call.data.split('_')[1]
        options = messages[language]['options']['occupation']

        if data.isdigit():
            idx = int(data)
            if 0 <= idx < len(options):
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
                        logging.exception(
                            f"Error in handle_occupation_selection: {e}")

                # Notify user of selection (but not confirmation yet)
                bot.answer_callback_query(
                    call.id, f"{messages[language]['selected']} {selected_occupation}")
            else:
                bot.answer_callback_query(
                    call.id, messages[language]['invalid_selection'])
        else:
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
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

# In[15]:


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
        data = call.data.split('_')[1]
        options = messages[language]['options']['income']

        if data.isdigit():
            idx = int(data)
            if 0 <= idx < len(options):
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
                        logging.exception(
                            f"Error in handle_income_selection: {e}")

                # Notify user of selection (but not confirmation yet)
                bot.answer_callback_query(
                    call.id, f"{messages[language]['selected']} {selected_income}")
            else:
                bot.answer_callback_query(
                    call.id, messages[language]['invalid_selection'])
        else:
            bot.answer_callback_query(
                call.id, messages[language]['invalid_selection'])
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
        data = call.data.split('_')[1]
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
            idx = int(data)
            if 0 <= idx < len(options):
                selected_kremenchuk = options[idx]

                # Set the selection
                user_data[user_id]['kremenchuk'] = selected_kremenchuk

                safe_answer_callback(
                    call, f"{messages[language]['selected']} {selected_kremenchuk}")

                # Update the keyboard to show selection
                update_kremenchuk_keyboard(
                    call.message, user_id, language, options)
            else:
                safe_answer_callback(
                    call, messages[language].get(
                        'invalid_selection', "Invalid selection."))
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

# In[16]:


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

        msg = bot.send_message(
            chat_id,
            enhanced_instructions,
            reply_markup=inline_kb
        )
        bot.register_next_step_handler(msg, handle_description)

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
                bot.register_next_step_handler(message, handle_description)
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
                        if "429" in str(e) or attempt < 2:
                            # Rate limited or other temporary error, retry
                            retry_after = 3 if "429" not in str(e) else int(str(e).split("retry after ")[1].split(" seconds")[0])
                            flow_logger.warning(f"Voice download error: {e}, retrying in {retry_after}s")
                            time.sleep(retry_after)
                        else:
                            # Final attempt failed
                            raise
                
                # Encrypt the voice file
                encrypted_voice = fernet.encrypt(downloaded_file)
                
                # Get a thread-safe copy of the nickname
                nickname = get_user_data(user_id, 'nickname')
                
                # Create directory for user's voice files
                user_voice_dir = os.path.join(voice_files_dir, nickname)
                os.makedirs(user_voice_dir, exist_ok=True)
                
                # Generate unique filename
                existing_files = os.listdir(user_voice_dir)
                submission_id = len(existing_files) + 1
                filename = f"{nickname} {submission_id}.enc"
                voice_filename = os.path.join(user_voice_dir, filename)

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
                bot.register_next_step_handler(message, handle_description)
                return
        else:
            safe_send_message(chat_id, messages[language]['please_send_text_or_voice'])
            bot.register_next_step_handler(message, handle_description)
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
        except:
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
        choice = call.data.split('_')[1]

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
            field = '_'.join(call.data.split('_')[1:])
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
    user_hash = hashlib.sha1(str(user_id).encode()).hexdigest()
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
# In[18]:


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
            nickname=f'<b>{nickname}</b>')
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
        data = call.data.split('_')[1]
        options = messages[language]['continue_options']

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

            msg = bot.send_message(
                chat_id, messages[language]['send_location'])
            bot.register_next_step_handler(msg, handle_location_step)

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

# In[ ]:


# Connection pool size
# Database connection pool implementation
DB_POOL_SIZE = 5
db_pool = queue.Queue(maxsize=DB_POOL_SIZE)
db_lock = threading.Lock()

def initialize_connection_pool():
    """Initialize the database connection pool."""
    flow_logger.info(f"Initializing database connection pool with {DB_POOL_SIZE} connections")
    for _ in range(DB_POOL_SIZE):
        try:
            conn = sqlite3.connect(db_file, check_same_thread=False)
            # Set pragmas for better performance and reliability
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            db_pool.put(conn)
        except Exception as e:
            logging.exception(f"Error initializing connection pool: {e}")

def get_db_connection():
    """Get a database connection from the pool or create a new one if needed."""
    try:
        # Try to get a connection from the pool with a timeout
        connection = db_pool.get(block=True, timeout=5)
        
        # Test the connection is valid before returning it
        try:
            connection.execute("SELECT 1")
            return connection
        except sqlite3.Error:
            # Connection is stale, create a new one
            try:
                connection.close()
            except:
                pass
            flow_logger.warning("Retrieved stale connection from pool, creating new one")
            return sqlite3.connect(db_file, check_same_thread=False)
            
    except queue.Empty:
        # If pool is empty and timeout expires, create a new connection
        flow_logger.warning("DB pool exhausted, creating new connection")
        return sqlite3.connect(db_file, check_same_thread=False)
    except Exception as e:
        flow_logger.error(f"Error getting DB connection: {e}")
        # Always return a working connection
        return sqlite3.connect(db_file, check_same_thread=False)

def return_db_connection(connection):
    """Return a connection to the pool or close it if pool is full."""
    try:
        # Test the connection before returning it to the pool
        try:
            connection.execute("SELECT 1")
            # Try to return the connection to the pool
            db_pool.put(connection, block=False)
        except (sqlite3.Error, Exception):
            # If connection is no longer valid, close it
            try:
                connection.close()
            except:
                pass
    except queue.Full:
        # If pool is full, close the connection
        try:
            connection.close()
        except:
            pass
    except Exception as e:
        # Ensure connection is closed on any error
        flow_logger.error(f"Error returning DB connection: {e}")
        try:
            connection.close()
        except:
            pass

# Data saving
# Updated save_data_and_restart function with better error handling for concurrent use
def save_data_and_restart(chat_id, user_id, language, restart_survey=False):
    try:
        # Get user data with thread-safe access
        with user_data_lock:
            user_data_copy = copy.deepcopy(user_data.get(user_id, {}))
        
        with user_profiles_lock:
            user_consent = user_profiles.get(user_id, {}).get('consent', False)
        
        consent_str = "True" if user_consent else "False"

        user_hash = hashlib.sha1(str(user_id).encode()).hexdigest()
        nickname = get_user_nickname(user_hash)
        month_year = datetime.datetime.now().strftime("%Y-%m")
        if not nickname:
            nickname = generate_unique_nickname()
            save_user_nickname(user_hash, nickname)

        # Ensure kremenchuk is loaded from profiles if needed
        kremenchuk_value = user_data_copy.get('kremenchuk', '')
        if not kremenchuk_value:
            with user_profiles_lock:
                kremenchuk_value = user_profiles.get(user_id, {}).get('kremenchuk', '')

        # Prepare data dictionary
        if not user_consent:
            # User declined consent, store only consent
            data = {
                'nickname': '',
                'month_year': '',
                'latitude': '',
                'longitude': '',
                'venue_title': '',
                'venue_address': '',
                'enjoyment': '',
                'purpose_visit': '',
                'regularity': '',
                'noticed_changes': '',
                'changes_detail': '',
                'wishlist': '',
                'kremenchuk': '',
                'description': '',
                'voice_submitted': '',
                'age': '',
                'gender': '',
                'occupation': '',
                'income': '',
                'language': language,  # language chosen can still be stored
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'visitor_type': '',
                'duration_visit': '',
                'accessibility': '',
                'consent': consent_str
            }
        else:
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

        # Use connection pool with proper retry for concurrent use
        db_connection_attempts = 0
        max_db_attempts = 3
        
        while db_connection_attempts < max_db_attempts:
            db_connection_attempts += 1
            conn = None
            
            try:
                with db_lock:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
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

                    cursor.execute(insert_query, values_tuple)
                    conn.commit()

                    # Verify row was inserted
                    cursor.execute("SELECT last_insert_rowid()")
                    last_id = cursor.fetchone()[0]
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
            finally:
                if conn:
                    return_db_connection(conn)

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

def cleanup_old_voice_messages(days_to_keep=30):
    """
    Cleans up voice messages older than the specified number of days.
    This prevents unlimited storage growth.

    Args:
        days_to_keep (int): Number of days to keep voice messages before deleting
    """
    try:
        flow_logger.info(
            f"Starting voice message cleanup, keeping messages from last {days_to_keep} days")
        current_time = time.time()
        cutoff_time = current_time - (days_to_keep * 24 * 60 * 60)
        total_deleted = 0

        # Walk through voice files directory
        for root, dirs, files in os.walk(voice_files_dir):
            for file in files:
                if file.endswith('.enc'):  # Only process encrypted voice files
                    file_path = os.path.join(root, file)
                    file_time = os.path.getmtime(file_path)

                    # Check if file is older than cutoff
                    if file_time < cutoff_time:
                        try:
                            os.remove(file_path)
                            total_deleted += 1
                        except Exception as e:
                            flow_logger.error(
                                f"Failed to delete old voice file {file_path}: {e}")

        flow_logger.info(
            f"Voice message cleanup complete. Deleted {total_deleted} files.")
    except Exception as e:
        flow_logger.error(f"Error in voice message cleanup: {e}")


def cleanup_scheduler():
    """Periodically runs cleanup tasks in the background."""
    while True:
        try:
            # Run cleanup tasks
            cleanup_stale_sessions(hours_inactive=48)
            cleanup_old_voice_messages(days_to_keep=30)

            # Sleep for a day
            time.sleep(24 * 60 * 60)
        except Exception as e:
            flow_logger.error(f"Error in cleanup scheduler: {e}")
            # If an error occurs, wait a bit and try again
            time.sleep(60 * 60)  # 1 hour


# Start the cleanup scheduler in a background thread
cleanup_thread = threading.Thread(target=cleanup_scheduler, daemon=True)
cleanup_thread.start()


# Update the start_polling_with_retry function for better error handling
def start_polling_with_retry():
    max_retries = 10  # Increased retries
    initial_delay = 5
    max_delay = 300  # 5 minutes max delay

    for retry in range(max_retries):
        try:
            # Use longer timeout for more stability
            bot.polling(non_stop=True, interval=1, timeout=60)
            return True  # Successful polling
        except requests.exceptions.ReadTimeout:
            delay = min(initial_delay * (2 ** retry), max_delay)  # Exponential backoff
            flow_logger.warning(f"Read timeout occurred (attempt {retry+1}/{max_retries}), retrying in {delay} seconds...")
            time.sleep(delay)
        except requests.exceptions.ConnectionError:
            delay = min(initial_delay * (2 ** retry), max_delay)  # Exponential backoff
            flow_logger.warning(f"Connection error (attempt {retry+1}/{max_retries}), retrying in {delay} seconds...")
            
            # Try to verify connectivity before retrying
            try:
                # Use a different URL than the Telegram API to check internet connectivity
                test_connection = requests.get("https://www.google.com", timeout=5)
                if test_connection.status_code == 200:
                    flow_logger.info("Internet connection appears to be working, likely a Telegram API issue")
                else:
                    flow_logger.warning("Internet connection test failed with status code: " + str(test_connection.status_code))
            except Exception as conn_test_error:
                flow_logger.warning(f"Internet connection test failed: {conn_test_error}")
            
            time.sleep(delay)
        except ApiTelegramException as e:
            # Specific handling for Telegram API errors
            if "429" in str(e) or "too many requests" in str(e).lower():
                # Extract retry_after if available
                retry_after = 30  # Default
                try:
                    retry_after_str = str(e).split("retry after ")[1].split(" seconds")[0]
                    retry_after = int(retry_after_str)
                except:
                    pass
                
                flow_logger.warning(f"Rate limited by Telegram API, waiting {retry_after} seconds before retry")
                time.sleep(retry_after + 5)  # Add a buffer
            else:
                delay = min(initial_delay * (2 ** retry), max_delay)
                flow_logger.error(f"Telegram API error: {e}, retrying in {delay} seconds")
                time.sleep(delay)
        except Exception as e:
            delay = min(initial_delay * (2 ** retry) * 2, max_delay)  # Longer exponential backoff
            flow_logger.error(f"Unexpected error in polling: {e}")
            time.sleep(delay)

    # If we've exhausted retries, log this
    flow_logger.critical("Exhausted all polling retries, bot may be down!")
    return False  # Failed after all retries


# Update the main loop for better error handling and recovery
if __name__ == '__main__':
    # Add import
    import copy
    
    # Output startup information
    startup_message = f"Bot starting with username: {bot_username}"
    print(startup_message)
    flow_logger.info(startup_message)

    # Initialize the database
    try:
        initialize_database()  # Initializes responses_kremenchuk.db
        flow_logger.info("Database initialized successfully")
    except Exception as e:
        flow_logger.error(f"Failed to initialize database: {e}")
        print(f"ERROR: Database initialization failed: {e}")
        # Exit if database initialization fails - can't run without a database
        sys.exit(1)

    # Try to recover any active sessions from a previous run
    try:
        recover_user_sessions()
    except Exception as e:
        flow_logger.error(f"Session recovery failed: {e}")

    # Add a voice message cleanup task
    try:
        cleanup_old_voice_messages()
    except Exception as e:
        flow_logger.error(f"Voice message cleanup failed: {e}")

    # Track consecutive fast failures to detect severe issues
    consecutive_fast_failures = 0
    failure_threshold_time = 5  # seconds
    max_consecutive_fast_failures = 8
    last_error_time = 0

    while True:
        try:
            # Check if we've had too many errors in a short time
            current_time = time.time()
            if consecutive_fast_failures > max_consecutive_fast_failures:
                time_since_last_error = current_time - last_error_time
                if time_since_last_error < 60:  # Less than a minute since last error
                    recovery_time = 60 - time_since_last_error
                    flow_logger.warning(f"Too many errors recently, pausing for {recovery_time:.1f} seconds")
                    time.sleep(recovery_time)
                    # Reset counter after pause
                    consecutive_fast_failures = max_consecutive_fast_failures // 2
            
            print("Starting bot polling...")
            flow_logger.info("Starting bot polling loop")

            # Reset fast failure counter on successful start
            start_time = time.time()

            # Use our improved polling function
            polling_successful = start_polling_with_retry()
            
            # If polling returned False, it means all retries were exhausted
            if not polling_successful:
                flow_logger.critical("All polling retries failed, entering recovery mode")
                time.sleep(60)  # Wait a full minute
                continue

            # If we reach here, polling was explicitly stopped
            flow_logger.warning("Bot polling ended normally. Restarting polling loop.")
            time.sleep(3)  # Short delay before restart

        except Exception as e:
            last_error_time = time.time()
            # Calculate how long the bot ran before failing
            runtime = last_error_time - start_time

            # Check if this was a fast failure
            if runtime < failure_threshold_time:
                consecutive_fast_failures += 1
                # Progressive backoff up to 30 seconds
                recovery_delay = min(30, 2 * consecutive_fast_failures)
                error_msg = f"Bot polling failed quickly after {runtime:.2f}s (consecutive failure #{consecutive_fast_failures}): {e}"
            else:
                # Reset counter on non-fast failures
                consecutive_fast_failures = max(0, consecutive_fast_failures - 1)
                recovery_delay = 5  # Normal recovery delay
                error_msg = f"Bot polling failed after {runtime:.2f}s: {e}"

            # Log the error
            logging.exception(error_msg)
            flow_logger.error(error_msg)
            print(error_msg)

            # Extended recovery for persistent issues
            if consecutive_fast_failures > max_consecutive_fast_failures:
                flow_logger.critical(f"Detected {consecutive_fast_failures} consecutive fast failures. Entering extended recovery mode.")
                recovery_delay = 60  # Longer delay for persistent issues

                # Try to reconnect to Telegram
                try:
                    if check_telegram_connection():
                        flow_logger.info("Successfully reconnected to Telegram API")
                        consecutive_fast_failures = consecutive_fast_failures // 2  # Reduce counter on successful connection
                except Exception as conn_err:
                    flow_logger.error(f"Failed to check Telegram connection in recovery mode: {conn_err}")

                # Try to reconnect to database
                try:
                    initialize_database()
                    flow_logger.info("Successfully reinitialized database connection")
                except Exception as db_err:
                    flow_logger.error(f"Failed to reinitialize database: {db_err}")

            # Wait before retrying
            print(f"Waiting {recovery_delay} seconds before retry...")
            time.sleep(recovery_delay)