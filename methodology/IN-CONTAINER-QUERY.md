# Querying live multi-GB app databases without copying them

Synthetic environments ship as live Docker Compose stacks. Each app has its own
database (commonly SQLite at `/app/backend/data/data.db`), and these get **large**
— 7–10 GB each; one mail-app DB in a production run held 159k message bodies and
1.2M recipient rows. Copying them out is slow and fills the disk. Query them
**in place, read-only.**

---

## The pattern

Exec a Python one-liner inside the container, using the app's own venv
interpreter, opening the DB **read-only** via a URI:

```bash
docker exec -i <CONTAINER> /app/backend/.venv/bin/python3 - <<'PY'
import sqlite3
con = sqlite3.connect('file:/app/backend/data/data.db?mode=ro', uri=True)
cur = con.cursor()
# list tables
print([r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table'")])
PY
```

- `mode=ro` + `uri=True` → **observe-only**, physically cannot mutate.
- Using the container's `.venv/bin/python3` guarantees the right SQLite build and
  avoids host/container version skew.
- `docker exec -i … <<'PY'` streams the script over stdin — no file to copy in.

## Finding the containers

```bash
docker ps --format '{{.Names}}' | grep <deployment-id>
# e.g. persona-24-2026-10-12-2141-outlook-app-1
```

Name convention seen: `<deployment-id>-<app>-app-1`. The deployment id encodes
the persona and build time — **use it to confirm which build you're testing**
(see below).

## Push the work into SQL, pull back only counts

On a 10 GB DB, do **not** `SELECT *` into Python. Count and aggregate in SQL,
return scalars:

```sql
SELECT count(*)              FROM messages WHERE snippet LIKE '%Surname%';
SELECT col, count(*)         FROM t GROUP BY col ORDER BY 2 DESC LIMIT 20;
SELECT count(DISTINCT value) FROM dataset_rows WHERE value GLOB '[0-9][0-9]*Z*';
```

For regex re-checks that SQL can't do, pull only the `LIKE`-prefiltered rows,
then apply the word-boundary regex in Python on that small set.

## Long scans: background them

A full-column scan on a huge DB can exceed a 120s foreground timeout. Run it in
the background and read the output file when it lands:

- Use the harness's background execution (don't rely on `&` + `wait`).
- macOS has **no `timeout`** command — don't wrap commands in it (exit 127).
- `sleep`-chaining to poll is blocked — use the harness's monitor/until loop.
- **Killing by task id doesn't work for docker-exec'd processes** — the task id
  isn't in the in-container process cmdline, so `pkill -f "<task-id>"` misses it
  and you end up with multiple competing scans hammering the same DB. Track the
  actual in-container PID if you must kill one.

## Confirming you're testing the right build — **do this before every round**

Timestamps lie. After a dev says "fixes are pushed", the live stack may still be
the *old* build. Two independent confirmations:

1. **DB mtime** inside the container — necessary, not sufficient.
2. **A known marker delta.** Pick a value a fix was supposed to change (a count
   of leaked names, a pseudonym, a specific row) and verify it actually moved.
   In one engagement, a round was only trusted once a known marker went 4046 → 0 —
   the timestamps alone had looked "new" while the data was unchanged.

Only start a retest round once a marker delta proves the rebuild is live.
