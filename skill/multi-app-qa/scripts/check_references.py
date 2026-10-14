"""Cross-app referential integrity.

Every ticket key, PR number, doc link and @mention cited in one app should
resolve to something that actually exists in another. This is where a
synthetic environment usually falls apart first: the Slack thread discusses
ENG-412, and ENG-412 was never generated.

Also flags orphan islands -- records no other app ever mentions -- which are
the signature of apps generated independently rather than as one story.

Usage:
    python check_references.py --records records.jsonl \
        --out findings/references.jsonl
"""

import os
import re
from collections import defaultdict

from common import arg, finding, load_records, text_of, write_findings

URL_RE = re.compile(r"https?://[^\s<>\")]+")
MENTION_RE = re.compile(r"(?<![\w])@([A-Za-z][\w.\-]{2,40})")


def main():
    recs = list(load_records(arg("--records", "records.jsonl")))
    out = arg("--out", "findings/references.jsonl")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    known_ids = set()
    known_handles = set()
    for r in recs:
        if r.get("id"):
            known_ids.add(str(r["id"]).upper())
        for person in [r.get("author"), r.get("assignee")] + (r.get("participants") or []):
            if person:
                known_handles.add(re.sub(r"[^a-z0-9]", "", str(person).lower()))

    cited_by = defaultdict(set)
    findings = []

    for r in recs:
        rid = r.get("id") or r.get("title") or r.get("source_file")
        text = text_of(r)

        for kind, ids in (r.get("refs") or {}).items():
            if kind == "commit":
                continue  # hashes are noisy; checked separately if needed
            for ref in ids:
                key = str(ref).upper()
                if key == str(r.get("id") or "").upper():
                    continue
                cited_by[key].add(r["app"])
                if kind == "ticket" and key not in known_ids:
                    findings.append(finding(
                        "refs.dangling-ticket", "data-bug", "blocker",
                        r["app"], rid,
                        "Cites %s, which exists nowhere in the environment" % ref,
                        text[:200],
                        "Generate the referenced item, or rewrite the reference "
                        "to point at an item that exists."))

        for handle in set(MENTION_RE.findall(text)):
            flat = re.sub(r"[^a-z0-9]", "", handle.lower())
            if flat and flat not in known_handles and len(flat) > 3:
                findings.append(finding(
                    "refs.unknown-mention", "data-bug", "minor",
                    r["app"], rid,
                    "@%s is mentioned but appears in no roster" % handle,
                    text[:200],
                    "Map the mention to a roster persona or remove it."))

        for url in set(URL_RE.findall(text)):
            if "example.com" in url or "localhost" in url or "TBD" in url:
                findings.append(finding(
                    "refs.placeholder-url", "redaction-bug", "major",
                    r["app"], rid,
                    "Placeholder URL left in content",
                    url,
                    "Replace with an in-environment link or remove."))

    # Orphans: records nothing else ever cites.
    for r in recs:
        rid = str(r.get("id") or "").upper()
        if not rid:
            continue
        others = cited_by.get(rid, set()) - {r["app"]}
        if not others and r.get("type") in ("issue", "ticket", "pr", "pull"):
            findings.append(finding(
                "refs.orphan-record", "data-bug", "minor",
                r["app"], r.get("id"),
                "No other app references this item",
                (r.get("title") or "")[:200],
                "A work item with no trace in Slack, GitHub or docs reads as "
                "generated in isolation. Add at least one cross-app mention."))

    write_findings(findings, out)


if __name__ == "__main__":
    main()
