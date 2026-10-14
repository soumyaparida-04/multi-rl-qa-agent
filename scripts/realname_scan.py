#!/usr/bin/env python3
"""
Surviving real-name detector.  redaction-bug.

The trap is substrings: LIKE '%shah%' matches 'Shahbaz', '%das%' matches 'Dash'.
So: cheap LIKE prefilter in SQL, then RE-CHECK every row with a word-boundary
regex in Python.  Never trust the LIKE count (seen: 487 LIKE hits -> 66 real).

  docker exec -i <CN> /app/backend/.venv/bin/python3 - < realname_scan.py

Curate SURNAMES to actual regional names present in the source identities --
not a dictionary, or you drown in FPs.
"""
import re, sqlite3, sys

DB = "file:/app/backend/data/data.db?mode=ro"

# ---- curate to the real identities the corpus was built from ----------------
SURNAMES = [
    # e.g. real Indian surnames for an India-flavoured corpus
    "Sharma", "Patel", "Reddy", "Nair", "Iyer", "Shah", "Das", "Gupta",
]
# columns worth scanning first (highest yield), by table.column substring match
PRIORITY = ["snippet", "subject", "filename", "file_data",
            "recipient_name", "name", "rows_json"]
# -----------------------------------------------------------------------------


def wb(surname: str) -> re.Pattern:
    # explicit boundary class (mixed scripts/punctuation break \b)
    return re.compile(rf"(^|[^A-Za-z]){re.escape(surname)}([^A-Za-z]|$)")


PATS = {s: wb(s) for s in SURNAMES}


def real_hits(text: str):
    if not text:
        return []
    return [s for s, p in PATS.items() if p.search(text)]


def scan_db(db_uri=DB, priority_only=True):
    con = sqlite3.connect(db_uri, uri=True)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    totals = {}
    for t in tables:
        cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{t}")')]
        for c in cols:
            key = f"{t}.{c}"
            if priority_only and not any(p in c.lower() for p in PRIORITY):
                continue
            # cheap SQL prefilter: any surname via LIKE
            like = " OR ".join([f'"{c}" LIKE ?' for _ in SURNAMES])
            try:
                rows = cur.execute(
                    f'SELECT "{c}" FROM "{t}" WHERE {like}',
                    [f"%{s}%" for s in SURNAMES])
            except sqlite3.Error:
                continue
            n = 0
            for (v,) in rows:
                if isinstance(v, (bytes, bytearray)):
                    continue
                if real_hits(str(v)):     # word-boundary re-check
                    n += 1
            if n:
                totals[key] = n
    for k in sorted(totals, key=totals.get, reverse=True):
        print(f"{totals[k]:>8}  {k}")
    if not totals:
        print("no surviving real-name candidates (after word-boundary recheck)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(real_hits(open(sys.argv[1]).read()))
    else:
        scan_db()
