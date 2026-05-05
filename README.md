# Ukrainability Telegram Bot

Telegram bot for the Ukrainability survey about people’s outdoor experiences in
Ukraine. The bot guides participants through consent, location, experience, and
demographic questions, stores responses in SQLite, and encrypts sensitive
response fields and voice-message files.

## Install

Use Python 3.9 or newer.

```bash
python3 -m pip install .
```

For development, install the package in editable mode with test/build tools:

```bash
python3 -m pip install -e ".[dev]"
```

If editable installation fails on an older system Python, upgrade pip first:

```bash
python3 -m pip install --upgrade pip
```

The package installs a command-line entrypoint:

```bash
ukrainability-bot
```

The legacy script name still works as a compatibility launcher:

```bash
python3 pryroda_kremenchuk.py
```

## Configuration

Required environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export ENCRYPTION_KEY="your-fernet-key"
export UKRAINABILITY_USER_HASH_SALT="your-secret-hmac-salt"
```

Generate a Fernet encryption key with:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
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

`UKRAINABILITY_STORAGE_DIR` defaults to `/home/ubuntu/kremenchuk` to preserve
the existing deployment. The legacy credentials file may contain:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export ENCRYPTION_KEY="your-fernet-key"
export UKRAINABILITY_USER_HASH_SALT="your-secret-hmac-salt"
```

For key rotation, set `ENCRYPTION_KEYS` to a comma-separated list where the
first key is active for new writes and later keys are accepted for decrypting
historical data:

```bash
export ENCRYPTION_KEYS="new-fernet-key,old-fernet-key"
```

See `.env.example` for a copyable template.

## Data And Files

At startup, the bot creates the storage directory if needed. By default it uses:

- SQLite database: `/home/ubuntu/kremenchuk/responses_kremenchuk.db`
- Encrypted voice files: `/home/ubuntu/kremenchuk/voice_messages/`
- Error log: `bot_errors.log`
- Flow log: `flow_control.log`

Survey response fields are encrypted before being written to SQLite. Voice
messages are encrypted as `.enc` files. Runtime logs use rotating file handlers,
and encrypted voice-message cleanup defaults to 30 days unless
`UKRAINABILITY_VOICE_RETENTION_DAYS` is set.

Back up the SQLite database and the key material together. Losing the Fernet
key, retiring keys, or `UKRAINABILITY_USER_HASH_SALT` makes historical encrypted
or pseudonymous data unusable. A simple SQLite backup can be made with:

```bash
sqlite3 /home/ubuntu/kremenchuk/responses_kremenchuk.db ".backup responses_kremenchuk.backup.db"
```

## Development

Run tests:

```bash
python3 -m pytest
```

Build the package:

```bash
python3 -m build
```

Publishing to PyPI is a separate maintainer action requiring PyPI credentials;
this repository only prepares the package for building and publishing.

## Project Layout

```text
src/ukrainability_telegram_bot/
  bot.py        # Telegram survey runtime
  cli.py        # ukrainability-bot entrypoint
  config.py     # environment and legacy credentials loading
  security.py   # Fernet helpers
  storage.py    # SQLite helpers
  keyboards.py  # keyboard construction helper
tests/          # pytest suite
```

The runtime code intentionally preserves the current survey flow while moving
startup work behind the CLI, so importing the package does not start polling,
call Telegram, create directories, initialize the database, or start cleanup
threads.
