"""Flatten arbitrary app exports into one normalized records.jsonl.

Usage:
    python normalize.py --in ./export --out records.jsonl [--strict]

Walks the export tree, infers the app from the path, and maps each object
to a common record shape. Field mapping is heuristic by design -- these
environments rarely share a schema. Run it, then eyeball the coverage
report it prints; if a field mapped badly, add it to FIELD_ALIASES.

Record shape:
    app, type, id, title, body, author, assignee, participants,
    created, modified, refs, attachments, url, source_file, raw
"""

import csv
import json
import os
import re
import sys

from common import arg, extract_ids, text_of  # noqa: F401

# Common app-name spellings collapse to one canonical token. This is a
# convenience, not a constraint -- unknown apps are discovered from the export
# structure and kept under their own name.
APP_ALIASES = {
    "atlassian-jira": "jira", "jira-cloud": "jira", "jira_issues": "jira",
    "gh": "github", "git-hub": "github", "github-enterprise": "github",
    "google-calendar": "calendar", "gcal": "calendar", "outlook-calendar": "calendar",
    "google-mail": "gmail", "mail": "gmail", "outlook": "gmail",
    "msteams": "teams", "ms-teams": "teams",
    "confluence-cloud": "confluence", "wiki": "confluence",
}

STOP_SEGMENTS = {"export", "exports", "data", "dump", "dumps", "seed", "seeds",
                 "fixtures", "raw", "json", "out", "output", "app", "apps",
                 "src", "db", "backup"}

FIELD_ALIASES = {
    "id": ("id", "key", "number", "uid", "uuid", "ticket", "identifier",
           "message_id", "event_id", "page_id"),
    "title": ("title", "summary", "subject", "name", "headline"),
    "body": ("body", "description", "text", "content", "message",
             "markdown", "plain_text", "comment"),
    "author": ("author", "creator", "reporter", "from", "sender",
               "user", "owner", "organizer", "created_by"),
    "assignee": ("assignee", "assigned_to", "owner", "responsible"),
    "created": ("created", "created_at", "createdAt", "created_on", "date",
                "timestamp", "ts", "sent_at", "start", "start_time",
                "opened_at", "recorded_at"),
    "modified": ("modified", "updated", "updated_at", "updatedAt",
                 "last_modified", "lastEditedTime", "edited_at",
                 "last_edited", "closed_at", "merged_at"),
    "url": ("url", "html_url", "link", "permalink", "web_url"),
    "participants": ("participants", "attendees", "members", "to",
                     "recipients", "reviewers", "watchers"),
    "attachments": ("attachments", "files", "documents", "media"),
    "comments": ("comments", "replies", "thread", "messages", "notes"),
}


def pick(obj, key):
    """First matching alias value, case-insensitively."""
    lowered = {str(k).lower(): v for k, v in obj.items()}
    for alias in FIELD_ALIASES[key]:
        if alias.lower() in lowered:
            val = lowered[alias.lower()]
            if val not in (None, "", [], {}):
                return val
    return None


def as_text(val):
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        for k in ("text", "body", "content", "value", "name", "plain_text"):
            if k in val and isinstance(val[k], str):
                return val[k]
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, list):
        return "\n".join(as_text(v) for v in val)
    return str(val)


def as_person(val):
    """Normalize a person-ish value to a display string."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        for k in ("displayName", "display_name", "name", "email",
                  "emailAddress", "login", "username", "real_name"):
            if val.get(k):
                return str(val[k]).strip()
        return json.dumps(val, ensure_ascii=False)[:120]
    if isinstance(val, list):
        return ", ".join(as_person(v) for v in val if v)
    return str(val)


def as_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def app_from_path(path):
    """Infer the app from the export's own structure.

    Preference order: first meaningful directory segment, then any later
    segment, then the filename stem. Works for any app suite -- nothing here
    is specific to a particular set of tools.
    """
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    candidates = parts[:-1] if len(parts) > 1 else []
    for seg in candidates:
        token = re.sub(r"[^a-z0-9]+", "-", seg.lower()).strip("-")
        if token and token not in STOP_SEGMENTS and not token.isdigit():
            return APP_ALIASES.get(token, token)
    stem = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(parts[-1])[0].lower()).strip("-")
    stem = stem.split("-")[0] if stem else ""
    if stem and stem not in STOP_SEGMENTS:
        return APP_ALIASES.get(stem, stem)
    return "unknown"


def type_from_path(path):
    base = os.path.basename(path).lower()
    for t in ("issue", "ticket", "pr", "pull", "commit", "message",
              "thread", "page", "doc", "event", "email", "video",
              "comment", "user", "channel"):
        if t in base:
            return t
    return "record"


def to_record(obj, source_file, app, rtype):
    if not isinstance(obj, dict):
        obj = {"body": obj}
    body = as_text(pick(obj, "body"))
    title = as_text(pick(obj, "title"))
    comments = []
    for c in as_list(pick(obj, "comments")):
        comments.append({"body": as_text(c), "author": as_person(
            c.get("author") if isinstance(c, dict) else None)})
    rec = {
        "app": app,
        "type": rtype,
        "id": as_text(pick(obj, "id")) or "",
        "title": title,
        "body": body,
        "author": as_person(pick(obj, "author")),
        "assignee": as_person(pick(obj, "assignee")),
        "participants": [as_person(p) for p in as_list(pick(obj, "participants"))],
        "created": pick(obj, "created"),
        "modified": pick(obj, "modified"),
        "url": as_text(pick(obj, "url")),
        "attachments": [as_text(a) for a in as_list(pick(obj, "attachments"))],
        "comments": comments,
        "source_file": source_file,
        "raw": obj,
    }
    rec["refs"] = {k: sorted(v) for k, v in extract_ids(text_of(rec)).items()}
    return rec


def iter_objects(path):
    """Yield dict objects from a json / jsonl / csv file."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".jsonl", ".ndjson"):
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        elif ext == ".json":
            with open(path, encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                for o in data:
                    yield o
            elif isinstance(data, dict):
                # A wrapper like {"issues": [...]} -- take the longest list.
                lists = [v for v in data.values() if isinstance(v, list)]
                if lists:
                    for o in max(lists, key=len):
                        yield o
                else:
                    yield data
        elif ext in (".csv", ".tsv"):
            delim = "\t" if ext == ".tsv" else ","
            with open(path, encoding="utf-8", errors="replace", newline="") as fh:
                for row in csv.DictReader(fh, delimiter=delim):
                    yield row
        elif ext in (".md", ".txt", ".html"):
            with open(path, encoding="utf-8", errors="replace") as fh:
                yield {"title": os.path.basename(path), "body": fh.read()}
    except (json.JSONDecodeError, UnicodeDecodeError, csv.Error) as exc:
        sys.stderr.write("UNREADABLE %s: %s\n" % (path, exc))


def main():
    src = arg("--in", required=True)
    out = arg("--out", "records.jsonl")
    strict = "--strict" in sys.argv

    records, per_app, unreadable = [], {}, []
    for root, _dirs, files in os.walk(src):
        for name in sorted(files):
            if name.startswith("."):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, src)
            if os.path.splitext(name)[1].lower() not in (
                    ".json", ".jsonl", ".ndjson", ".csv", ".tsv",
                    ".md", ".txt", ".html"):
                continue
            app = app_from_path(rel)
            rtype = type_from_path(rel)
            before = len(records)
            for obj in iter_objects(path):
                records.append(to_record(obj, rel, app, rtype))
            if len(records) == before:
                unreadable.append(rel)
            per_app[app] = per_app.get(app, 0) + (len(records) - before)

    with open(out, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("normalized %d records -> %s" % (len(records), out))
    for app in sorted(per_app):
        print("  %-12s %5d" % (app, per_app[app]))
    if unreadable:
        print("\nyielded nothing (check these by hand):")
        for u in unreadable:
            print("  %s" % u)
    missing_dates = sum(1 for r in records if not r["created"])
    if missing_dates:
        print("\n%d records have no 'created' date -- temporal checks will "
              "skip them. Add the right field name to FIELD_ALIASES."
              % missing_dates)
    if strict and (unreadable or missing_dates):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
