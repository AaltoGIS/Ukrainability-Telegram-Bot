# Implementation Updates vs. the Original `pryroda_kremenchuk.py`

This document summarises the substantive differences between the original
single-file script (`pryroda_kremenchuk.py`, 6074 lines, commit `892f8ee`)
and the current packaged implementation under `src/ukrainability_telegram_bot/`.

The survey itself (questions, branching, languages, keyboards, voice handling,
SQLite schema) is unchanged. The differences below are infrastructure,
security, and correctness fixes — not user-visible behaviour changes.

---

## Packaging and lifecycle

| Original | Current |
|---|---|
| Single 6074-line script. | `src/ukrainability_telegram_bot/` package with `cli.py` entrypoint, `pyproject.toml`, installable as `ukrainability-bot`. |
| Side effects at import time: created storage directories, opened the DB, called `bot.get_me()`, spawned the cleanup thread. | All side effects deferred to `configure_runtime(AppConfig)` / `run()`. Importing the package does nothing observable. |
| Handlers registered at import via `@bot.message_handler(...)` against a real `TeleBot`. | `HandlerRegistry` records decorators at import; `configure_runtime` replays them against the real `TeleBot` once it's built. |
| Hard-coded `/home/ubuntu/kremenchuk` paths and inline credentials parsing. | `AppConfig.from_env()` dataclass with explicit fields; `UKRAINABILITY_STORAGE_DIR`, `UKRAINABILITY_CREDENTIALS_FILE`, `UKRAINABILITY_BOT_ERRORS_LOG`, `UKRAINABILITY_FLOW_CONTROL_LOG`, `UKRAINABILITY_LOG_MAX_BYTES`, `UKRAINABILITY_LOG_BACKUP_COUNT`, `UKRAINABILITY_VOICE_RETENTION_DAYS`, `UKRAINABILITY_CLEANUP_INTERVAL_SECONDS`. |
| No tests. | Unit tests covering config, security, storage, pseudonym, voice helpers, nicknames, keyboards, messages, cleanup, Telegram I/O, and helper functions. |

## Security

| Original | Current |
|---|---|
| `hashlib.sha1(str(user_id).encode())` as the participant identifier — trivially reversible since Telegram user IDs are public 64-bit ints. | `pseudonym.hash_user_id` using HMAC-SHA-256 with a required `UKRAINABILITY_USER_HASH_SALT` per deployment. |
| Single `Fernet(ENCRYPTION_KEY)` with no decrypt helper and no key rotation path. | `MultiFernet` built from `ENCRYPTION_KEYS` (active + retiring); `security.encrypt_text` / `security.decrypt_text` for round-trip. |
| Voice filenames generated as `len(os.listdir(user_voice_dir)) + 1` — race-prone; concurrent uploads collide and overwrite. | `voice.new_voice_filename` uses `secrets.token_hex(8)`; `voice.safe_nickname_directory` validates the nickname against `[A-Za-z0-9][A-Za-z0-9 ]*` before any path join. |
| `storage.table_columns` (formerly inline in the script) used an f-string for the table name. | `ALLOWED_TABLES` whitelist guards the parameter. |
| Plaintext `print("DEBUG: User {user_id} sent text location: '{location_text}'")` plus lat/lon and venue text in `flow_control.log`. | All location data redacted in logs; `redacted_coordinate` rounds to 0.1°; debug prints removed. |
| Bare `except:` and `except BaseException` blocks would swallow `KeyboardInterrupt` / `SystemExit`. | All replaced with `except Exception:`. |
| Credentials file values silently mangled when quotes were unbalanced. | `_has_unbalanced_quotes` warns and preserves the raw value. |

## Correctness and concurrency

| Original | Current |
|---|---|
| Two separate `RLock`s (`user_data_lock`, `user_profiles_lock`) — risk of lock-order inversion across handlers. | One `RLock` aliased as both names; `save_data_and_restart` snapshots both dicts under one acquisition. |
| `recover_user_sessions`, `cleanup_stale_sessions`, `update_activity_timestamp` mutated `user_data` outside the lock; iteration could race with handler inserts (`RuntimeError: dictionary changed size during iteration`). | All three hold `user_data_lock` while iterating/mutating. |
| Two parallel schema definitions (script-inline + an extracted helper) could drift. | `storage.initialize_database` is the single source; runtime delegates to it. |
| `db_pool = queue.Queue(maxsize=DB_POOL_SIZE)` plus a global `db_lock` serialised every connection — pool was effectively dead weight; failed transactions could re-enter the pool dirty. | Pool and `db_lock` removed entirely; per-call `sqlite3.connect` everywhere. |
| Consent-denied flow wrote a fully empty `responses` row (`nickname=''`, all blanks, `consent='False'`). | Early-returns with no DB insert; logs `"Consent denied; skipping response row insert"`. |
| `int(call.data.split('_')[1])` raw — no prefix check, no bounds check; cross-language drift could silently select the wrong option. | `callback_index(callback_data, prefix, options)` enforces both. |
| `safe_send_message` retry loop could fall off implicitly returning `None`; callers then crashed on `msg.message_id`. | Explicit `raise RuntimeError("Failed to send message after retry loop")`. |
| Rate-limit handling parsed `int(str(e).split("retry after ")[1].split(" seconds")[0])`. | `telegram_retry_after` reads `result_json["parameters"]["retry_after"]`, coerces to `float`, caps at 60 s. Voice-download 429 detection uses `getattr(e, "error_code", None) == 429` instead of string sniffing. |
| `bot.register_next_step_handler(msg, ...)` registered after `send_message` — race window where a fast user reply was lost. | `bot.register_next_step_handler_by_chat_id(chat_id, ...)` registered before the prompt, via the `send_next_step_prompt` helper. |

## Operations

| Original | Current |
|---|---|
| `logging.FileHandler('flow_control.log')` — unbounded log growth. | `RotatingFileHandler` with `UKRAINABILITY_LOG_MAX_BYTES` / `UKRAINABILITY_LOG_BACKUP_COUNT` (defaults 5 MB × 5). |
| Encrypted response columns still left operational metadata visible through SQLite row order and timestamps. | Preserved for compatibility: `responses.id` and `responses.timestamp` remain plaintext metadata, while all other response columns are encrypted. Treat DB access as sensitive even without the Fernet key. |
| `cleanup_scheduler` ran `while True: cleanup(); time.sleep(24*60*60)` — no graceful shutdown, restart hammered cleanup, exception backoff stacked with the next normal sleep. | `cleanup.py` owns `cleanup_stop_event` + `cleanup_thread_lock` and exposes `start_cleanup_scheduler` / `stop_cleanup_scheduler`. The loop runs cleanup, then `wait()`s; exception branch uses its own bounded `wait()` with explicit `continue` so back-offs never stack. Interval and retention configurable. |
| Voice retention hard-coded to 30 days. | Configurable via `UKRAINABILITY_VOICE_RETENTION_DAYS`. |
| Cleanup interval hard-coded. | Configurable via `UKRAINABILITY_CLEANUP_INTERVAL_SECONDS`. |

## Code organisation

| Original | Current |
|---|---|
| Survey text, adjective/noun pools, encryption helpers, DB helpers, callback parsing, message-id registry, cleanup scheduler, runtime setup, polling, session globals, and response persistence — all inline in the script. | Extracted into `messages.py`, `nicknames.py`, `security.py`, `storage.py`, `voice.py`, `pseudonym.py`, `keyboards.py`, `constants.py`, `cleanup.py`, `telegram_io.py`, `runtime.py`, `app.py`, `sessions.py`, `survey/persistence.py`, and pilot `survey/questions/` modules for consent, purpose, and description. Phase 5 moved the remaining legacy survey flow to `survey/legacy_flow.py`; `bot.py` is now a compatibility shim that re-exports `configure_runtime` and `run`. |
| Survey text duplicated between an inline `messages` dict and a module-level constant during the migration. | Single source: `messages.py`, imported by the survey flow modules. |

## What is intentionally unchanged

- The survey flow itself: every question, every branching predicate, every language string, every keyboard layout.
- The SQLite schema (`responses`, `user_nicknames`, indices).
- The `Fernet`/encryption choice; `MultiFernet` is a superset.
- The legacy `pryroda_kremenchuk.py` launcher path remains supported via the
  `ukrainability-bot` console script and the package's runtime entrypoint.

## Open work (planned, not yet done)

- Splitting the remaining `survey/legacy_flow.py` responsibilities into per-question modules under `survey/questions/` and removing the temporary `HandlerRegistry`.
- Broader survey-flow integration tests (drive a full callback chain through a mocked `TeleBot`).
- HTML-output audit for any remaining unescaped user content in `parse_mode='HTML'` sends.
