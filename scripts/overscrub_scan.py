#!/usr/bin/env python3
"""
Over-scrub (gibberish-substitution) detector.  redaction-bug.

A token containing >= MIN_MORPHS of the substitution generator's building-block
morphemes is almost certainly a machine-mashed pseudonym a human would read as
nonsense.  A *single* morpheme is just a normal pseudonym syllable -- not a leak.

Run it in-container against a live DB (read-only), or against any text file.

  docker exec -i <CN> /app/backend/.venv/bin/python3 - < overscrub_scan.py

FP carve-outs handled:
  * requires >= 2 morphemes (tune MIN_MORPHS)
  * skips base64-ish blobs (long, high non-space ratio) -> tracking noise
  * you supply BENIGN to whitelist known-good pseudonyms / app residue
"""
import re, sys, sqlite3, base64, binascii

# ---- tune these to YOUR environment's substitution generator ----------------
MORPHS = ["path", "bright", "hydra", "cryo", "nex", "mag",
          "wren", "kep", "pol", "gen", "zen"]
MIN_MORPHS = 2
BENIGN = set()        # add known-benign pseudonyms / library tokens here
DB = "file:/app/backend/data/data.db?mode=ro"
# -----------------------------------------------------------------------------

TOKEN = re.compile(r"[A-Za-z]{4,}")


def looks_base64(s: str) -> bool:
    """Tracking pixels / file_data decode cleanly and are long -> skip."""
    if len(s) < 40:
        return False
    if re.fullmatch(r"[A-Za-z0-9+/=\s]+", s or ""):
        try:
            base64.b64decode(s[:120] + "===", validate=False)
            return True
        except (binascii.Error, ValueError):
            return False
    return False


def score(tok: str) -> int:
    t = tok.lower()
    return sum(t.count(m) for m in MORPHS)


def scan_text(text: str):
    if not text or looks_base64(text):
        return []
    out = []
    for tok in TOKEN.findall(text):
        if tok.lower() in BENIGN:
            continue
        if score(tok) >= MIN_MORPHS:
            out.append(tok)
    return out


def scan_db(db_uri=DB):
    con = sqlite3.connect(db_uri, uri=True)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    hits = {}
    for t in tables:
        cols = [r[1] for r in cur.execute(f'PRAGMA table_info("{t}")')]
        text_cols = [c for c in cols]  # try all; non-text just won't match
        for c in text_cols:
            try:
                rows = cur.execute(
                    f'SELECT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL')
            except sqlite3.Error:
                continue
            n = 0
            for (v,) in rows:
                if isinstance(v, (bytes, bytearray)):
                    continue
                if scan_text(str(v)):
                    n += 1
            if n:
                hits[f"{t}.{c}"] = n
    for k in sorted(hits, key=hits.get, reverse=True):
        print(f"{hits[k]:>8}  {k}")
    if not hits:
        print("no over-scrub candidates")


if __name__ == "__main__":
    if len(sys.argv) > 1:          # scan a file
        print(scan_text(open(sys.argv[1]).read()))
    else:
        scan_db()
