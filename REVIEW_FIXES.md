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
- Consolidated `user_data` and `user_profiles` under the same reentrant lock to avoid lock-order inversions.
- Consolidated schema creation by making the runtime call `storage.initialize_database()`.
- Removed the runtime SQLite connection pool and use per-call SQLite connections instead.
- Replaced string parsing of Telegram `retry_after` with structured `result_json` / `result` lookup.
- Coerced `retry_after` values to floats and capped waits at 60 seconds.
- Made `safe_send_message()` raise explicitly if the retry loop exits unexpectedly.
- Added callback parsing helpers and applied them to all survey callback handlers that parse indexed choices.
- Consolidated survey text so `bot.py` imports the live dictionary from `messages.py`.
- Skipped response-row insertion when consent is denied instead of writing a mostly empty row.
- Registered next-step handlers by chat ID before sending prompts that expect a free-text/location/voice reply.
- Audited HTML-mode sends in `bot.py` and escaped interpolated nicknames in addition to existing escaped user-response echoes.
- Removed a redundant reentrant lock read in `save_data_and_restart()` by snapshotting profile data with the user data.
- Added a warning for malformed legacy credentials values with unbalanced quotes.
- Deleted the unused `state.py` helper and its tests so there is only one in-memory session system.
- Removed leftover notebook `# In[...]` markers from the runtime module.

## Operations Fixes

- Switched bot and flow logs to `RotatingFileHandler` with configurable size and backup count.
- Added configurable encrypted voice-message retention and cleanup interval environment variables.
- Replaced the hard-coded daily cleanup `time.sleep()` loop with a waitable cleanup event and configurable cadence.
- Changed cleanup scheduling so a restart waits for the configured interval before the first cleanup pass, and added `stop_cleanup_scheduler()`.

## Remaining Review Items

- The larger architecture split into `survey/flow.py`, `telegram_io.py`, and an app context remains future work.
- Survey-flow integration tests around mocked Telegram callbacks remain future work; current coverage focuses on config/security/storage/runtime helpers.
