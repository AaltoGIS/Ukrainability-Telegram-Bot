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
- Added a warning for malformed legacy credentials values with unbalanced quotes and leave those values untouched for operator correction.
- Deleted the unused `state.py` helper and its tests so there is only one in-memory session system.
- Removed leftover notebook `# In[...]` markers from the runtime module.

## Operations Fixes

- Switched bot and flow logs to `RotatingFileHandler` with configurable size and backup count.
- Added configurable encrypted voice-message retention and cleanup interval environment variables.
- Replaced the hard-coded daily cleanup `time.sleep()` loop with a waitable cleanup event and configurable cadence.
- Added `stop_cleanup_scheduler()` and locking around cleanup start/stop.
- Kept opportunistic cleanup on startup, then wait for the configured interval between future cleanup passes.
- After cleanup errors, retry after the shorter error backoff instead of stacking it with the normal cleanup interval.
- Introduced `AppContext` as the runtime dependency container and `SessionStore` as the owner of user session, profile, and tracked message-id state.
- Retired the temporary `cleanup.bind()` and `telegram_io.bind()` patterns; both modules now receive `AppContext` explicitly.
- Removed the legacy `user_data`, `user_profiles`, and lock globals from `bot.py`; remaining survey handlers access session state through `ctx.sessions`.
- Extracted runtime configuration, logging setup, polling retry logic, and the temporary `HandlerRegistry` into `runtime.py`; `bot.py` now keeps wrappers so the CLI and legacy imports continue to work.
- Extracted response row construction, encryption, and insertion retry orchestration into `survey/persistence.py`; `storage.py` now defines the explicit plaintext/encrypted column partition.

## Remaining Review Items

- The larger architecture split into `survey/flow.py` and per-question modules remains future work.
- Survey-flow integration tests around mocked Telegram callbacks remain future work; current coverage focuses on config/security/storage/runtime helpers.
