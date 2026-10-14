"""Temporal integrity.

Covers checklist items 1-3:
  - "modified" never predates "created"
  - nothing after the environment's today, nothing before persona start
  - referenced events happen in a sane order (nothing shared before it existed)

Usage:
    python check_temporal.py --records records.jsonl --config qa-config.json \
        --out findings/temporal.jsonl
"""

import os

from common import (arg, finding, load_config, load_records, parse_date,
                    text_of, write_findings)


def index_by_id(records):
    idx = {}
    for r in records:
        rid = (r.get("id") or "").strip()
        if rid:
            idx.setdefault(rid.upper(), r)
    return idx


def main():
    recs = list(load_records(arg("--records", "records.jsonl")))
    cfg = load_config(arg("--config", "qa-config.json"))
    out = arg("--out", "findings/temporal.jsonl")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    start = parse_date(cfg.get("persona_start"))
    today = parse_date(cfg.get("environment_today"))
    idx = index_by_id(recs)
    findings = []

    for r in recs:
        rid = r.get("id") or r.get("title") or r.get("source_file")
        created = parse_date(r.get("created"))
        modified = parse_date(r.get("modified"))

        if created and modified and modified < created:
            findings.append(finding(
                "temporal.modified-before-created", "data-bug", "major",
                r["app"], rid,
                "Modified timestamp predates created timestamp",
                "created=%s modified=%s" % (r.get("created"), r.get("modified")),
                "Regenerate both timestamps from one clock; modified >= created."))

        for label, dt, raw in (("created", created, r.get("created")),
                               ("modified", modified, r.get("modified"))):
            if not dt:
                continue
            if today and dt > today:
                findings.append(finding(
                    "temporal.after-today", "data-bug", "major",
                    r["app"], rid,
                    "%s timestamp is after the environment's today" % label,
                    "%s=%s today=%s" % (label, raw, cfg.get("environment_today")),
                    "Clamp generation to the environment window."))
            if start and dt < start:
                findings.append(finding(
                    "temporal.before-persona-start", "data-bug", "major",
                    r["app"], rid,
                    "%s timestamp predates the persona's start date" % label,
                    "%s=%s start=%s" % (label, raw, cfg.get("persona_start")),
                    "Either move the record inside the window or justify it as "
                    "pre-existing context the persona inherited."))

        # Cross-app ordering: a record that cites another must not predate it.
        if created:
            for ids in (r.get("refs") or {}).values():
                for ref in ids:
                    target = idx.get(str(ref).upper())
                    if not target:
                        continue
                    t_created = parse_date(target.get("created"))
                    if t_created and created < t_created:
                        findings.append(finding(
                            "temporal.reference-precedes-target", "data-bug",
                            "blocker", r["app"], rid,
                            "Record references %s before that item existed" % ref,
                            "this=%s %s=%s" % (r.get("created"), ref,
                                               target.get("created")),
                            "Shift the referring record after the referenced "
                            "item's creation, or drop the reference."))

        # Conversation threads should advance, not jump backwards.
        prev = None
        for c in r.get("comments") or []:
            c_dt = parse_date(c.get("created")) if isinstance(c, dict) else None
            if prev and c_dt and c_dt < prev:
                findings.append(finding(
                    "temporal.comment-out-of-order", "data-bug", "minor",
                    r["app"], rid,
                    "Comment timestamps run backwards within a thread",
                    text_of(r)[:200],
                    "Sort thread entries chronologically at generation time."))
                break
            prev = c_dt or prev

    write_findings(findings, out)


if __name__ == "__main__":
    main()
