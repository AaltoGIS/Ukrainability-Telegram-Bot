# Review Fixes

This document tracks the code-review items addressed after the initial package
modernization commit.

## Security Fixes

- Replaced bare SHA-1 user hashes with HMAC-SHA-256 via `hash_user_id(user_id, UKRAINABILITY_USER_HASH_SALT)`.
- Added required `UKRAINABILITY_USER_HASH_SALT` configuration and documented it in `.env.example` and `README.md`.
- Added MultiFernet support with `ENCRYPTION_KEYS` for key rotation, plus `decrypt_text()`.
- Whitelisted accepted table names in `storage.table_columns()` to remove the SQL injection footgun.
- Added voice-file helpers that validate nickname path components and generate random `secrets.token_hex(8)` filenames instead of `len(os.listdir(...)) + 1`.
- Redacted location details from flow logs and removed text-location debug prints.
- Replaced bare `except:` / `except BaseException:` handlers in the runtime module with `except Exception:`.

## Correctness Fixes

- Made session recovery, stale-session cleanup, and activity timestamp updates use `user_data_lock`.
- Consolidated schema creation by making the runtime call `storage.initialize_database()`.
- Added rollback before returning SQLite connections to the pool.
- Replaced string parsing of Telegram `retry_after` with structured `result_json` / `result` lookup.
- Made `safe_send_message()` raise explicitly if the retry loop exits unexpectedly.
- Added callback parsing helpers and applied them to consent, purpose, duration, and regularity handlers.
- Consolidated survey text so `bot.py` imports the live dictionary from `messages.py`.

## Remaining Review Items

- The larger architecture split into `survey/flow.py`, `telegram_io.py`, and an app context remains future work.
- Several callback handlers still need migration to the new callback parsing helpers.
- `register_next_step_handler_by_chat_id`, full HTML-output audit, rotating log handlers, configurable voice retention, and scheduler replacement remain open.
- The old connection-pool design is still present, though dirty-connection reuse is reduced by rollback.
