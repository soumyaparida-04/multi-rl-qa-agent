"""Entity and identity consistency.

Covers checklist items 8 and 11:
  - replacement names fit what they replaced (a company must not become a
    person, a programme must not become a company)
  - nonsense name substitutions sitting in running text
  - plus: the same human should carry one identity across all nine apps

Usage:
    python check_entities.py --records records.jsonl --config qa-config.json \
        --out findings/entities.jsonl
"""

import os
import re
from collections import defaultdict

from common import (arg, finding, load_config, load_records, text_of,
                    write_findings)

# Grammatical frames that tell you what kind of thing a name must be.
PERSON_FRAMES = [
    r"\b%s\s+(?:said|asked|replied|wrote|mentioned|thinks|agreed|will|"
    r"has|owns|joined|left|reviewed|approved|assigned)\b",
    r"\b(?:assigned to|reviewed by|thanks|cc|ping|spoke with|1:1 with)\s+%s\b",
]
ORG_FRAMES = [
    r"\b(?:at|with|from|contract with|vendor|acquired|partnership with|"
    r"invoice from|onboarding)\s+%s\b",
    r"\b%s\s+(?:invoiced|renewed|quoted|shipped|announced|acquired)\b",
]
PROGRAMME_FRAMES = [
    r"\b(?:project|programme|program|initiative|epic|workstream|migration)\s+%s\b",
    r"\b%s\s+(?:rollout|migration|launch|kickoff|phase)\b",
]

PERSON_SHAPE = re.compile(r"^[A-Z][a-z'\-]+(?:\s+[A-Z][a-z'\-]+){1,2}$")
ORG_SHAPE = re.compile(
    r"\b(Inc|LLC|Ltd|GmbH|Corp|Technologies|Labs|Systems|Solutions|"
    r"Software|Group|Holdings|Partners|Ventures)\b", re.I)


def classify_shape(name):
    if ORG_SHAPE.search(name):
        return "org"
    if PERSON_SHAPE.match(name.strip()):
        return "person"
    return "unknown"


def main():
    recs = list(load_records(arg("--records", "records.jsonl")))
    cfg = load_config(arg("--config", "qa-config.json"))
    out = arg("--out", "findings/entities.jsonl")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    roster = cfg.get("roster", [])          # [{name, email, handle, role, kind}]
    by_name = {p["name"]: p for p in roster if p.get("name")}
    findings = []

    # ---- 1. identity drift: one person, many spellings across apps
    def identity_key(name):
        """Collapse a person to a surname key, so 'P. Raman', 'Priya Raman'
        and 'priya.raman@corp.test' all land on 'raman'."""
        s = str(name).strip()
        if "@" in s:                      # email -> use the local part
            s = s.split("@")[0]
        tokens = [t for t in re.split(r"[\s,._\-]+", s) if t]
        words = [re.sub(r"[^A-Za-z]", "", t) for t in tokens]
        words = [w for w in words if w]
        long_words = [w for w in words if len(w) > 1]
        if len(words) >= 2 and long_words:
            return long_words[-1].lower()
        if long_words:
            return long_words[-1].lower()
        return re.sub(r"[^a-z]", "", s.lower())[:12]

    seen = defaultdict(lambda: defaultdict(set))   # key -> app -> variants
    for r in recs:
        for person in [r.get("author"), r.get("assignee")] + (r.get("participants") or []):
            if not person or len(str(person)) < 3:
                continue
            p = str(person).strip()
            key = identity_key(p)
            if key:
                seen[key][r["app"]].add(p)

    for flat, apps in seen.items():
        variants = set()
        for vs in apps.values():
            variants |= vs
        if len(variants) > 1 and len(apps) > 1:
            findings.append(finding(
                "entity.identity-drift", "data-bug", "major",
                ",".join(sorted(apps)), "",
                "Same person rendered differently across apps",
                " | ".join(sorted(variants)),
                "Pick one canonical display name and email per persona and "
                "propagate it to every app."))

    # ---- 2. roster diff: names appearing nowhere in the approved roster
    if roster:
        approved = set(identity_key(p["name"]) for p in roster if p.get("name"))
        for flat, apps in seen.items():
            if flat and flat not in approved:
                variants = sorted({v for vs in apps.values() for v in vs})
                findings.append(finding(
                    "entity.off-roster-name", "redaction-bug", "major",
                    ",".join(sorted(apps)), "",
                    "Name appears that is not on the approved roster",
                    " | ".join(variants)[:300],
                    "Either add to the roster as an intended persona or treat "
                    "as an unscrubbed real identity."))

    # ---- 3. category mismatch: a name used in the wrong grammatical frame
    for r in recs:
        rid = r.get("id") or r.get("title") or r.get("source_file")
        text = text_of(r)
        if not text:
            continue
        for name, meta in by_name.items():
            kind = meta.get("kind") or classify_shape(name)
            esc = re.escape(name)
            if kind != "person":
                for frame in PERSON_FRAMES:
                    m = re.search(frame % esc, text, re.I)
                    if m:
                        findings.append(finding(
                            "entity.category-mismatch", "redaction-bug", "blocker",
                            r["app"], rid,
                            "'%s' (a %s) is used as a person" % (name, kind),
                            text[max(0, m.start() - 80):m.end() + 80],
                            "Substitution changed the category of the entity. "
                            "Replace with a name of the same kind."))
                        break
            if kind != "org":
                for frame in ORG_FRAMES:
                    m = re.search(frame % esc, text, re.I)
                    if m:
                        findings.append(finding(
                            "entity.category-mismatch", "redaction-bug", "blocker",
                            r["app"], rid,
                            "'%s' (a %s) is used as a company" % (name, kind),
                            text[max(0, m.start() - 80):m.end() + 80],
                            "Replace with an organisation-shaped name."))
                        break
            if kind == "org":
                for frame in PROGRAMME_FRAMES:
                    m = re.search(frame % esc, text, re.I)
                    if m:
                        findings.append(finding(
                            "entity.category-mismatch", "redaction-bug", "major",
                            r["app"], rid,
                            "'%s' (a company) is used as a programme" % name,
                            text[max(0, m.start() - 80):m.end() + 80],
                            "Programmes should get programme-shaped names."))
                        break

    # ---- 4. nonsense substitutions sitting in running text
    NONSENSE = re.compile(
        r"\b(?:[A-Z]{2,}_[A-Z0-9_]{2,}|[A-Za-z]+\d{4,}|"
        r"[bcdfghjklmnpqrstvwxz]{5,}[aeiou]?)\b")
    for r in recs:
        rid = r.get("id") or r.get("title") or r.get("source_file")
        text = text_of(r)
        for m in NONSENSE.finditer(text):
            token = m.group(0)
            if token.upper() in ("TODO", "FIXME") or len(token) < 5:
                continue
            findings.append(finding(
                "entity.nonsense-substitution", "redaction-bug", "minor",
                r["app"], rid,
                "Unpronounceable token reads as a failed substitution: %s" % token,
                text[max(0, m.start() - 80):m.end() + 80],
                "Confirm this is intended (an identifier) or replace with a "
                "plausible name."))
            break

    write_findings(findings, out)


if __name__ == "__main__":
    main()
