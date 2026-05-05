"""Survey messages and text constants extracted from the legacy bot."""

PRIVACY_NOTICE_URL_EN = 'https://telegra.ph/Ukrainabilitys-Privacy-Notice-03-15'

PARTICIPANT_INFORMATION_SHEET_URL_EN = 'https://telegra.ph/Participant-Information-Sheet-for-Ukrainability-project-03-15'

PRIVACY_NOTICE_URL_UK = 'https://telegra.ph/Polіtika-konfіdencіjnostі-dlya-doslіdzhennya-Ukrainability-03-14'

PARTICIPANT_INFORMATION_SHEET_URL_UK = 'https://telegra.ph/Іnformacіjnij-list-dlya-uchasnikіv-proektu-Ukrainability-03-14'

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
        'purpose_visit_custom_instruction': (
            "You can also type your own activity as a text message. When finished, press Done."
        ),
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
        'voice_instruction': (
            "To send a voice message, touch and hold the microphone icon in the message bar, speak, and then release."
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
        'voice_processing_error': (
            "Sorry, there was an error processing your voice message. Please try sending a text response instead."
        ),
        'description_retry_or_skip': "Would you like to try again or skip the description?",
        'selections_saved': "Selections saved",
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
        'purpose_visit_custom_instruction': (
            "Ви також можете ввести власний варіант у полі введення тексту. Коли закінчите, натисніть Готово."
        ),
        'regularity_question': "Ви відвідуєте це місце регулярно, час від часу, чи лише один раз?",
        'changes_question': "Чи помітили ви якісь зміни в цьому місці після повномасштабного вторгнення?",
        'changes_detail_question': "Що саме змінилося? Ви можете обрати декілька варіантів.",
        'wishlist_question': "Що, на вашу думку, варто покращити чи змінити в цьому місці?",
        'kremenchuk_question': "Як довго ви проживаєте в місті Кременчук?",
        'add_description': (
            "Ми були б раді почути більше про ваш досвід. Будь ласка, поділіться будь-якими історіями, почуттями або пам'ятними моментами від вашого візиту. "
            "Ви можете написати відповідь або надіслати голосове повідомлення. Голосове повідомлення буде перетворено в текст для аналізу, а оригінальне голосове повідомлення буде негайно видалене для захисту вашої конфіденційності. Якщо ви хочете пропустити та завершити, будь ласка, натисніть 'Пропустити'."
        ),
        'voice_instruction': (
            "Щоб надіслати голосове повідомлення, натисніть і утримуйте іконку мікрофона в рядку повідомлень, говоріть і потім відпустіть."
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
        'voice_processing_error': (
            "Вибачте, сталася помилка під час обробки голосового повідомлення. Будь ласка, спробуйте надіслати текстову відповідь."
        ),
        'description_retry_or_skip': "Хочете спробувати знову чи пропустити опис?",
        'selections_saved': "Вибір збережено",
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
