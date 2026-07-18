## SQLite write hardening (busy_timeout + WAL)
**Priority:** Medium · **Area:** backend/database · **Size:** S

### Context
The async multimodal receipt path performs concurrent DB saves via
`asyncio.to_thread` (each on its own connection). SQLite permits one
writer at a time; without a busy timeout, simultaneous saves fail
immediately with `database is locked`, causing intermittent per-receipt
failures that scale with batch size and `GEMINI_MAX_CONCURRENCY`.

### Tasks
- [ ] Set `PRAGMA busy_timeout = 5000` in the connection factory
      (`database/connection.py` / repository base), so it applies to
      every connection, including the connection-per-save path.
- [ ] Enable `PRAGMA journal_mode = WAL` once at startup (migrations or
      app init). Note: WAL is persistent per database file; document
      this in the backend README.
- [ ] Add a regression test: batch of ~10 receipts with concurrency 10
      against a temp DB, assert zero `database is locked` failures.

### Acceptance criteria
Large multimodal batches at max concurrency complete with no
lock-related receipt failures.

## Fence temp-file cleanup against active receipt batches
**Priority:** Medium · **Area:** backend/scheduler · **Size:** M

### Context
`api/scheduler.py` runs hourly cleanup of stale temp files. A large
multimodal batch slowed by API rate limiting / retry backoff can run
longer than the staleness threshold, at which point cleanup deletes
temp files for receipts **not yet processed**. Symptom: early receipts
in a big batch succeed, later ones fail with file-not-found. Only
reproduces on long runs, so it looks like random flakiness.

### Tasks
- [ ] Add an in-flight registry: batch processors register their temp
      paths (or a per-batch temp subdirectory) on start and deregister
      in a `finally` on completion/disconnect.
- [ ] Cleanup job skips registered paths/directories regardless of age.
- [ ] Keep age-based deletion as the fallback for orphans (e.g. process
      killed mid-batch and never deregistered) — raise the orphan
      threshold to comfortably exceed the max plausible batch duration
      given `MAX_RECEIPT_BATCH_SIZE` and worst-case per-receipt latency.
- [ ] Log every deletion with file age, to make any future recurrence
      diagnosable.

### Acceptance criteria
A batch whose runtime exceeds the cleanup interval completes with no
mid-batch file-not-found failures; orphaned temp files from crashed
runs are still eventually removed.

### Notes
Simplest robust shape: one subdirectory per batch
(`tmp/batch_<uuid>/`), registered at creation, deleted by the
processor itself on completion — cleanup job then only handles
orphaned batch dirs older than the fallback threshold.