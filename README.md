# Ukrainability Telegram Bot

[![codecov](https://codecov.io/gh/AaltoGIS/Ukrainability-Telegram-Bot/branch/main/graph/badge.svg)](https://codecov.io/gh/AaltoGIS/Ukrainability-Telegram-Bot)

<!-- TODO: add citation to the accompanying article once confirmed -->
The Ukrainability Telegram Bot turns Telegram, a messenger already used daily by
many people, into a low-cost, anonymous public participatory GIS (PPGIS) tool
for mapping how people experience outdoor places, designed with GDPR-oriented
privacy safeguards. Instead of asking participants to install a new app or learn
an unfamiliar interface, the survey runs entirely inside Telegram: participants
share a location, answer multiple-choice and free-text questions about their
visit, and optionally record a voice message. Responses are encrypted at rest,
and the bot does not store raw Telegram user IDs; each participant is identified
only by a salted HMAC-SHA-256 pseudonym and a randomly generated nickname. The
framework was piloted in 2025 along the Dnipro waterfront in Kremenchuk,
Ukraine, where 219 participants mapped 230 places. Submitted data is visualised
on an interactive dashboard at https://ukrainability.space/, integrated into the
bot as a Telegram mini-app, so contributing data and exploring it happen in the
same place. The codebase is designed to be forked and adapted for similar
studies in other cities and on other messenger platforms.

## Quick Start

Use Python 3.10 or newer.

```bash
git clone https://github.com/AaltoGIS/Ukrainability-Telegram-Bot.git
cd Ukrainability-Telegram-Bot
python3 -m pip install .
cp .env.example .env
```

Edit `.env` with your Telegram bot token, Fernet encryption key, and user-hash
salt. Then run:

```bash
ukrainability-bot
```

From a source checkout, you can also run the convenience launcher without first
installing the console script:

```bash
python3 pryroda_kremenchuk.py
```

## Setting Up Your Telegram Bot

1. Open Telegram, search for `@BotFather`, and start a chat.
2. Send `/newbot` and follow the prompts to choose a display name and a username
   ending in `bot`.
3. Save the HTTP API token BotFather returns. This is your `TELEGRAM_BOT_TOKEN`.
4. Send `/setcommands`, choose your bot when BotFather prompts, and paste:

   ```text
   start - Begin or restart the survey
   ```

5. For production deployments, optionally use `/setdescription`,
   `/setabouttext`, and `/setuserpic`.
6. Telegram's own guides are useful references:
   https://core.telegram.org/bots/tutorial and
   https://core.telegram.org/bots/features.

## Configuration

Required environment variables (see below recommendations how to generate secure keys):

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export ENCRYPTION_KEY="your-fernet-key"
export UKRAINABILITY_USER_HASH_SALT="your-secret-hmac-salt"
```

Optional environment variables:

```bash
export UKRAINABILITY_STORAGE_DIR="/home/ubuntu/kremenchuk"
export UKRAINABILITY_CREDENTIALS_FILE="/home/ubuntu/kremenchuk/secure/credentials"
export UKRAINABILITY_BOT_ERRORS_LOG="bot_errors.log"
export UKRAINABILITY_FLOW_CONTROL_LOG="flow_control.log"
export UKRAINABILITY_LOG_MAX_BYTES="5000000"
export UKRAINABILITY_LOG_BACKUP_COUNT="5"
export UKRAINABILITY_VOICE_RETENTION_DAYS="30"
export UKRAINABILITY_CLEANUP_INTERVAL_SECONDS="86400"
```

`UKRAINABILITY_STORAGE_DIR` defaults to `/home/ubuntu/kremenchuk`, , which is specific to the original Kremenchuk deployment and almost certainly does not exist on your machine. Forks should override this before the first run — the bot creates the directory at startup and writes the SQLite database, encrypted voice files, and log files there. The optional
credentials file can contain the same shell-style exports as `.env`:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export ENCRYPTION_KEY="your-fernet-key"
export UKRAINABILITY_USER_HASH_SALT="your-secret-hmac-salt"
```

### Generating Secure Keys

`ENCRYPTION_KEY` is a Fernet key. Fernet is symmetric encryption from the
`cryptography` library: the same secret encrypts and decrypts. The bot encrypts
sensitive response fields, including locations and free-text answers, before
writing them to SQLite.

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If you lose this key, stored encrypted responses become permanently unreadable.
Treat it like a database password.

`UKRAINABILITY_USER_HASH_SALT` is used to hash Telegram user IDs with
HMAC-SHA-256. The database stores the resulting pseudonym, not the raw Telegram
user ID, so repeat participants can receive a stable monthly nickname without
exposing their Telegram identifier.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Back up this salt alongside the database. Losing it means existing pseudonyms
cannot be linked to new sessions.

For key rotation, set `ENCRYPTION_KEYS` to a comma-separated list where the
first key is active for new writes and later keys are accepted for decrypting
historical data:

```bash
export ENCRYPTION_KEYS="new-fernet-key,old-fernet-key"
```

## Architecture

The import-side-effect rule is load-bearing: importing the package must never
start polling, contact Telegram, create directories, initialize the database, or
start cleanup threads. Runtime effects live behind `configure_runtime()`,
`run()`, and `cli.main()`.

1. **Entry point** - `cli.main()` reads environment configuration, builds
   `AppConfig`, and hands off to `runtime.run(config)`.
   ([cli.py](src/ukrainability_telegram_bot/cli.py))
2. **AppContext** - a dependency container passed through the runtime; it bundles
   the bot, config, sessions, Fernet encryption, logger, and cleanup event.
   ([app.py](src/ukrainability_telegram_bot/app.py))
3. **Runtime setup** - `runtime.configure_runtime(config)` configures logging,
   builds the Telegram client, registers handlers, and returns the context.
   ([runtime.py](src/ukrainability_telegram_bot/runtime.py))
4. **Handler registration** - `handlers.register_handlers(ctx)` wires every
   `message_handler` and `callback_query_handler` against the live bot.
   ([handlers.py](src/ukrainability_telegram_bot/handlers.py))
5. **Survey orchestration** - `SurveyActions` is the adapter callbacks use to
   advance the survey. ([survey/actions.py](src/ukrainability_telegram_bot/survey/actions.py))
6. **Survey questions** - each question is a focused module exposing `ask_*` and,
   where needed, `callbacks_from_context(ctx, actions)`.
   ([survey/questions/](src/ukrainability_telegram_bot/survey/questions/))
7. **State** - `SessionStore` keeps per-user state thread-safe, while
   `survey/flow.py` encodes branching based on prior answers.
   ([sessions.py](src/ukrainability_telegram_bot/sessions.py),
   [survey/flow.py](src/ukrainability_telegram_bot/survey/flow.py))
8. **Persistence** - `survey/persistence.py` builds the encrypted response row
   and writes it through `storage.py`; encryption lives in `security.py`, and
   pseudonymous user hashing lives in
   [pseudonym.py](src/ukrainability_telegram_bot/pseudonym.py) and
   `nickname_db.py`.
   ([survey/persistence.py](src/ukrainability_telegram_bot/survey/persistence.py))
9. **Cleanup** - `cleanup.py` runs a background scheduler that deletes encrypted
   voice files past their retention window.
   ([cleanup.py](src/ukrainability_telegram_bot/cleanup.py))

## Exporting decrypted data

The responses table stores every field except timestamp as Fernet ciphertext, and voice messages are stored as encrypted .enc files. To work with the data outside the bot, decrypt with the same key(s) the bot was running with. Set ENCRYPTION_KEY (or ENCRYPTION_KEYS if you have rotated keys), then run the `export_responses.py`. Typical usage:

```export ENCRYPTION_KEY="your-fernet-key"

python export_responses.py \
    --db        "$UKRAINABILITY_STORAGE_DIR/responses_kremenchuk.db" \
    --out       responses_kremenchuk_anon.csv \
    --voice-dir "$UKRAINABILITY_STORAGE_DIR/voice_messages" \
    --voice-out voice_decrypted
```
The decrypted CSV and voice messages (if any) contain personal, often also sensitive data and should be handled accordingly: store it on a filesystem with restricted permissions, never commit it to git, and treat its disposal with the same care as the encryption key itself.


## GDPR compliance

The bot is designed to make compliance with the EU General Data Protection Regulation feasible for small research teams. The bot stores data in pseudonymous form: response fields are encrypted with Fernet, and the user_hash column in both responses and user_nicknames is HMAC-SHA-256(telegram_user_id, UKRAINABILITY_USER_HASH_SALT) instead of the raw Telegram ID. While the controller holds the salt, this is pseudonymous personal data under GDPR — risk-reduced compared to identified data, but still personal data. Anonymisation happens at export time: `export_responses.py` drops user_hash from the output and keeps only the nickname that was already stored alongside each response. Nicknames are randomly drawn from a fixed pool when a participant first appears in a given month and have no mathematical relationship to the Telegram user ID; with user_hash removed, the exported CSV contains no salt-derived identifier and cannot be relinked to a Telegram user.

**Lawful use** - forks must add an explicit consent step at the start of the survey describing purpose, retention, controller contact, recipients, and rights. Participants identify themselves by the nickname the bot showed them and the month they participated - use them to erase data subject's submissions, if needed. Voice messages should be erased upon manual content recognition. 

**Key and salt management** - ENCRYPTION_KEY(S) and UKRAINABILITY_USER_HASH_SALT are part of the security boundary. They should live outside the database backup, ideally in a secrets manager or an encrypted credentials file referenced by UKRAINABILITY_CREDENTIALS_FILE. The database alone reveals nothing; the database with the keys reveals everything. Loss of the keys is, by design, equivalent to deletion.


## Customising The Survey

### Changing An Existing Question

1. Find the question module under
   `src/ukrainability_telegram_bot/survey/questions/`, such as
   `enjoyment.py`.
2. Update the prompt text in `messages.py` for both `en` and `uk`.
3. Update the option list or keyboard layout in the question module's `ask_*`
   function.
4. If the option set affects branching, update the matching predicates or index
   sets in `survey/flow.py`. Branching predicates match literal answer strings
   in both `en` and `uk`, so update both language variants together when option
   wording changes.
5. Run the focused test, for example:

   ```bash
   python3 -m pytest tests/test_question_experience.py
   ```

Use `enjoyment.py` as a single-select template and `purpose.py` as a
multi-select template.

### Adding A New Question

1. Create `src/ukrainability_telegram_bot/survey/questions/<your_question>.py`
   modelled on a similar sibling module.
2. Define `ask_<your_question>(ctx, chat_id, user_id, language)` and, if the
   question has callbacks, a `callbacks_from_context(ctx, actions)` factory.
3. Add prompt and option strings to `messages.py` under both `en` and `uk`.
4. Add an `ask_<your_question>` method to `SurveyActions` in `survey/actions.py`
   that delegates to the question module.
5. Wire callbacks or message entry points in `handlers.register_handlers`.
6. If the question changes branching, update `survey/flow.py`.
7. If the answer is persisted, add the field to `storage.RESPONSE_COLUMNS`, the
   `responses` schema in `storage.initialize_database`, and the row-building
   logic in `survey/persistence.py`.
8. Add a focused test under `tests/` modelled on existing question tests.

## Data And Files

At startup, the bot creates the storage directory if needed. By default it uses:

- SQLite database: `/home/ubuntu/kremenchuk/responses_kremenchuk.db`
- Encrypted voice files: `/home/ubuntu/kremenchuk/voice_messages/`
- Error log: `bot_errors.log`
- Flow log: `flow_control.log`

Every `responses` field except `timestamp` is encrypted with Fernet before being
written to SQLite. The source of truth is `storage.RESPONSE_COLUMNS` and
`storage.PLAINTEXT_COLUMNS`.

The `user_nicknames` table stores `(user_hash, nickname, month_year)` with
`(user_hash, month_year)` as the primary key. `user_hash` is the salted
HMAC-SHA-256 pseudonym derived from the Telegram user ID. This lets the bot give
one stable nickname per participant per month without storing raw Telegram user
IDs.

Voice messages are written as `.enc` files under
`<storage_dir>/voice_messages/`, encrypted with the same Fernet key, and deleted
by the cleanup scheduler after `UKRAINABILITY_VOICE_RETENTION_DAYS` days
(default 30).

Back up the SQLite database and key material together. Losing the Fernet key,
retiring keys, or `UKRAINABILITY_USER_HASH_SALT` makes historical encrypted or
pseudonymous data unusable. A simple SQLite backup can be made with:

```bash
sqlite3 /home/ubuntu/kremenchuk/responses_kremenchuk.db ".backup responses_kremenchuk.backup.db"
```

## Development

Install development tools:

```bash
python3 -m pip install -e ".[dev]"
```

Run tests:

```bash
python3 -m pytest
```

Run linting and formatting checks:

```bash
ruff check .
ruff format --check .
```

Build the package:

```bash
python3 -m build
```

## Maintainers

- Oleksandr Karasov (creator of the tool), GIST Lab, Aalto University
- Henrikki Tenkanen, GIST Lab, Aalto University
