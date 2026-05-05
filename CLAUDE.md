# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Install for development: `python3 -m pip install -e ".[dev]"`
- Run the bot: `ukrainability-bot` (or `python3 pryroda_kremenchuk.py` from a checkout)
- Run tests: `python3 -m pytest`
- Run a single test: `python3 -m pytest tests/test_storage.py::test_name`
- Build distributables: `python3 -m build`

Required env vars: `TELEGRAM_BOT_TOKEN`, `ENCRYPTION_KEY` (Fernet). Optional: `UKRAINABILITY_STORAGE_DIR` (default `/home/ubuntu/kremenchuk`), `UKRAINABILITY_CREDENTIALS_FILE` (`export NAME=value` shell file). See `.env.example`.

## Architecture

The package is structured around an `AppContext` dependency container, a thread-safe `SessionStore`, runtime setup in `runtime.configure_runtime`, handler wiring in `handlers.register_handlers`, and question modules under `survey/questions/`. Key invariant: **importing the package must not start polling, contact Telegram, create directories, init the DB, or start cleanup threads.** All such side effects must live behind `configure_runtime()` / `run()` and `cli.main()`.

### Startup flow

`cli.main()` builds an `AppConfig.from_env()` (env vars, falling back to an `export`-style credentials file) and calls `runtime.run(config)`. `runtime.configure_runtime(config)` configures logging, creates storage directories, builds the `telebot.TeleBot`, builds Fernet encryption, creates the `SessionStore`, returns an `AppContext`, and calls `handlers.register_handlers(ctx)`.

### Handler registration

`handlers.register_handlers(ctx)` registers message and callback handlers against the live `TeleBot` after runtime configuration. Add new Telegram entry points there, and keep question-specific behavior in the relevant module under `survey/questions/`.

### Storage and encryption

SQLite at `<storage_dir>/responses_kremenchuk.db` with two tables defined in `storage.initialize_database`:
- `responses` — survey answers; column list is the source of truth in `storage.RESPONSE_COLUMNS`.
- `user_nicknames` — `(user_hash, month_year)` PK so a participant gets one stable nickname per month.

Every response field except `timestamp` is Fernet-encrypted before insertion; voice messages are saved as `.enc` files under `<storage_dir>/voice_messages/`. `security.build_fernet` validates the key. Connections use `WAL` + `synchronous=NORMAL` + `busy_timeout=5000` for concurrent access from the bot's thread pool.

### Survey state and branching

`SessionStore` in `sessions.py` owns per-user data, profile data, message IDs, and activity timestamps behind one `RLock`. The survey has conditional branches encoded in `survey/flow.py`; when a parent answer changes, dependent fields must be cleared to avoid stale follow-ups.

### i18n

The bot is bilingual EN/UK. Branching predicates in `survey/flow.py` match on the literal answer strings in both languages, so keep both variants in sync when editing options. User-facing strings live in `messages.py`.

## Conventions (from AGENTS.md)

1. Don't assume; surface tradeoffs rather than hide confusion.
2. Minimum code that solves the problem — nothing speculative.
3. Touch only what you must; clean up only your own mess.
4. Define success criteria and loop until verified.
