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
```

Generate a Fernet encryption key with:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Optional environment variables:

```bash
export UKRAINABILITY_STORAGE_DIR="/home/ubuntu/kremenchuk"
export UKRAINABILITY_CREDENTIALS_FILE="/home/ubuntu/kremenchuk/secure/credentials"
```

`UKRAINABILITY_STORAGE_DIR` defaults to `/home/ubuntu/kremenchuk` to preserve
the existing deployment. The legacy credentials file may contain:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export ENCRYPTION_KEY="your-fernet-key"
```

See `.env.example` for a copyable template.

## Data And Files

At startup, the bot creates the storage directory if needed. By default it uses:

- SQLite database: `/home/ubuntu/kremenchuk/responses_kremenchuk.db`
- Encrypted voice files: `/home/ubuntu/kremenchuk/voice_messages/`
- Error log: `bot_errors.log`
- Flow log: `flow_control.log`

Survey response fields are encrypted before being written to SQLite. Voice
messages are encrypted as `.enc` files.

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
  state.py      # testable session/dependency helpers
  keyboards.py  # keyboard construction helper
tests/          # pytest suite
```

The runtime code intentionally preserves the current survey flow while moving
startup work behind the CLI, so importing the package does not start polling,
call Telegram, create directories, initialize the database, or start cleanup
threads.
