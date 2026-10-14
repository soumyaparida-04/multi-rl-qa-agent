#!/usr/bin/env python3
"""
Structured-PII sweep.  redaction-bug.

Region-specific identifiers survive scrubbing because they don't look like names.
Counts DISTINCT values and locates them by column, so a systemic leak reads as
ONE finding, not thousands.

  docker exec -i <CN> /app/backend/.venv/bin/python3 - < pii_scan.py

Adapt PATTERNS to the corpus locale (US: SSN/EIN/routing; EU: IBAN/VAT; ...).
The India set below suits an India-flavoured corpus; swap per locale.
"""
import re, sqlite3

DB = "file:/app/backend/data/data.db?mode=ro"

PATTERNS = {
    # phone fakes often end 0000 -> a non-0000 match is the stronger leak
    "phone":  re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"),
    "phone_real_looking": re.compile(r"(?<!\d)[6-9]\d{5}(?!0000)\d{4}(?!\d)"),
    "PAN":    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "GSTIN":  re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Zz][A-Z\d]\b"),
    "IFSC":   re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
}


def scan_db(db_uri=DB):
    con = sqlite3.connect(db_uri, uri=True)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    # distinct value sets per (pii, column)
    found = {}   # (pii, table.col) -> set of distinct values
    for t in tables:
        cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{t}")')]
        for c in cols:
            try:
                rows = cur.execute(
                    f'SELECT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL')
            except sqlite3.Error:
                continue
            for (v,) in rows:
                if isinstance(v, (bytes, bytearray)):
                    continue
                s = str(v)
                for name, pat in PATTERNS.items():
                    for m in pat.findall(s):
                        found.setdefault((name, f"{t}.{c}"), set()).add(m)
    if not found:
        print("no structured PII found")
        return
    for (name, loc) in sorted(found, key=lambda k: len(found[k]), reverse=True):
        print(f"{len(found[(name, loc)]):>8} distinct  {name:<18} {loc}")


if __name__ == "__main__":
    scan_db()
