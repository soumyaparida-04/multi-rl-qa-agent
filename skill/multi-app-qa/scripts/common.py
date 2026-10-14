"""Shared helpers for the multi-app QA checkers.

Every checker reads a normalized records.jsonl and emits findings.jsonl.
Stdlib only -- runs anywhere Python 3.9+ does.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------- findings

BUCKETS = ("data-bug", "redaction-bug", "feature-gap")
SEVERITIES = ("blocker", "major", "minor", "info")


def finding(check, bucket, severity, app, record_id, summary,
            evidence="", recommendation=""):
    """Build one finding. Keep summary short; put raw text in evidence."""
    if bucket not in BUCKETS:
        raise ValueError("bad bucket: %s" % bucket)
    if severity not in SEVERITIES:
        raise ValueError("bad severity: %s" % severity)
    return {
        "check": check,
        "bucket": bucket,
        "severity": severity,
        "app": app or "unknown",
        "record_id": record_id or "",
        "summary": summary,
        "evidence": (evidence or "")[:600],
        "recommendation": recommendation,
    }


def write_findings(findings, path):
    with open(path, "w", encoding="utf-8") as fh:
        for f in findings:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    sys.stderr.write("%s: %d findings -> %s\n"
                     % (os.path.basename(sys.argv[0]), len(findings), path))


def load_findings(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ---------------------------------------------------------------- records

def load_records(path):
    """Yield normalized records from a .jsonl file."""
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                sys.stderr.write("warn: bad json on line %d: %s\n" % (n, exc))


def text_of(rec):
    """All human-readable text in a record, concatenated."""
    parts = [rec.get("title") or "", rec.get("body") or ""]
    for c in rec.get("comments") or []:
        if isinstance(c, dict):
            parts.append(c.get("body") or "")
        else:
            parts.append(str(c))
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------- dates

_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y", "%d %b %Y",
)


def parse_date(value):
    """Best-effort parse into an aware UTC datetime, or None."""
    if value in (None, "", "null"):
        return None
    if isinstance(value, (int, float)):
        # epoch seconds or milliseconds
        ts = float(value)
        if ts > 1e11:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def load_config(path):
    """Load qa-config.json -- persona, window, roster, brief."""
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
    for key in ("persona_start", "environment_today"):
        if cfg.get(key) and not parse_date(cfg[key]):
            raise SystemExit("config: %s is not a parsable date" % key)
    return cfg


# ---------------------------------------------------------------- ids

# Ticket / PR / doc identifiers referenced in free text across apps.
ID_PATTERNS = {
    "ticket": re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b"),
    "pr": re.compile(r"(?:PR|pull request)\s*#?(\d{1,6})", re.I),
    "issue": re.compile(r"(?<![\w/])#(\d{1,6})\b"),
    "commit": re.compile(r"\b([0-9a-f]{7,40})\b"),
}


def extract_ids(text):
    """Return {kind: set(ids)} found in free text."""
    found = {}
    for kind, pat in ID_PATTERNS.items():
        hits = set(m.group(1) for m in pat.finditer(text or ""))
        if hits:
            found[kind] = hits
    return found


def arg(flag, default=None, required=False):
    """Tiny argv reader: --flag value"""
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    if required:
        raise SystemExit("missing required argument: %s" % flag)
    return default
