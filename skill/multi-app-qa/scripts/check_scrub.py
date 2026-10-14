"""Redaction and scrub quality.

Covers checklist items 6, 7, 10, 11, 14, 15, 16:
  - broken sentences where a redaction token dropped mid-sentence
  - domain vocabulary over-scrubbed along with real PII
  - leftover placeholders (TBD, <name>, null, example.com, Masked Address)
  - surviving PII in text, filenames and metadata
  - visibly broken redaction, even where nothing leaked
  - real outside company / vendor / product names left in

Usage:
    python check_scrub.py --records records.jsonl --config qa-config.json \
        --out findings/scrub.jsonl
"""

import os
import re

from common import (arg, finding, load_config, load_records, text_of,
                    write_findings)

PLACEHOLDERS = [
    (r"\bTBD\b", "TBD"),
    (r"\bTODO\b", "TODO"),
    (r"\bFIXME\b", "FIXME"),
    (r"\bXXX+\b", "XXX"),
    (r"Masked\s+Address", "Masked Address"),
    (r"<\s*(name|email|user|person|company|address|phone|redacted)\s*>", "<token>"),
    (r"\[\s*(REDACTED|MASKED|NAME|EMAIL|PII)\s*\]", "[TOKEN]"),
    (r"\{\{\s*[\w.]+\s*\}\}", "{{template}}"),
    (r"\bnull\b", "null"),
    (r"\bundefined\b", "undefined"),
    (r"\bNaN\b", "NaN"),
    (r"lorem ipsum", "lorem ipsum"),
    (r"example\.com", "example.com"),
    (r"\bJohn Doe\b|\bJane Doe\b", "Doe placeholder"),
    (r"PERSON_\d+|COMPANY_\d+|EMAIL_\d+", "token_N"),
]

PII = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")),
    ("phone", re.compile(r"(?<!\w)(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?"
                         r"\d{3,4}[ -]\d{3,4}(?:[ -]\d{2,4})?(?!\w)")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit-card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("aadhaar", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")),
    ("ip", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("api-key", re.compile(r"\b(?:sk|pk|ghp|gho|xox[baprs])[-_][A-Za-z0-9]{16,}\b")),
]

# A redaction that ate part of a sentence leaves these shapes behind.
BROKEN_SCRUB = [
    (r"\b(?:the|a|an|of|to|with|from|by|for|at|in|and)\s*[.!?]",
     "sentence ends on a function word -- content dropped after it"),
    (r"\s{3,}", "run of whitespace where a token was removed"),
    (r"[,;]\s*[,;]", "doubled punctuation"),
    (r"\(\s*\)|\[\s*\]|\{\s*\}", "empty bracket pair"),
    (r"\b(\w+)\s+\1\b(?!\w)", "word immediately repeated"),
    (r"^[a-z][^.!?]{0,40}[.!?]\s*$", "fragment starting lowercase"),
    (r"\s+[.!?]", "space before terminal punctuation"),
]


def main():
    recs = list(load_records(arg("--records", "records.jsonl")))
    cfg = load_config(arg("--config", "qa-config.json"))
    out = arg("--out", "findings/scrub.jsonl")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    allow_domains = set(d.lower() for d in cfg.get("allowed_domains", []))
    outside_orgs = [o for o in cfg.get("forbidden_org_names", [])]
    domain_terms = [t for t in cfg.get("domain_vocabulary", [])]
    findings = []

    for r in recs:
        rid = r.get("id") or r.get("title") or r.get("source_file")
        text = text_of(r)
        haystacks = [("content", text),
                     ("filename", r.get("source_file") or ""),
                     ("attachments", " ".join(r.get("attachments") or [])),
                     ("metadata", " ".join(str(v) for v in (
                         r.get("author"), r.get("assignee"), r.get("url")) if v))]

        for where, hay in haystacks:
            if not hay:
                continue

            for pat, label in PLACEHOLDERS:
                m = re.search(pat, hay, re.I)
                if m:
                    findings.append(finding(
                        "scrub.placeholder", "redaction-bug", "major",
                        r["app"], rid,
                        "Leftover placeholder %s in %s" % (label, where),
                        hay[max(0, m.start() - 60):m.end() + 60],
                        "Replace with generated content or remove the field."))

            for kind, pat in PII:
                for m in pat.finditer(hay):
                    hit = m.group(0)
                    if kind == "email":
                        dom = hit.split("@")[-1].lower()
                        if dom in allow_domains:
                            continue
                    if kind == "ip" and hit.startswith(("10.", "192.168.", "127.")):
                        continue
                    findings.append(finding(
                        "scrub.pii-survived", "redaction-bug", "blocker",
                        r["app"], rid,
                        "Possible %s in %s" % (kind, where),
                        hay[max(0, m.start() - 60):m.end() + 60],
                        "Confirm whether real. If real, re-scrub and re-export; "
                        "if synthetic, add its domain to allowed_domains."))

        for pat, why in BROKEN_SCRUB:
            m = re.search(pat, text, re.M)
            if m:
                findings.append(finding(
                    "scrub.broken-redaction", "redaction-bug", "major",
                    r["app"], rid,
                    "Damaged text: %s" % why,
                    text[max(0, m.start() - 80):m.end() + 80],
                    "Redaction removed content mid-sentence. Regenerate the "
                    "sentence rather than patching the gap. This is a defect "
                    "even though no PII leaked."))
                break

        for org in outside_orgs:
            if re.search(r"\b%s\b" % re.escape(org), text, re.I):
                findings.append(finding(
                    "scrub.real-org-name", "redaction-bug", "major",
                    r["app"], rid,
                    "Real outside organisation named: %s" % org,
                    text[:200],
                    "Substitute a fictional vendor consistently across all apps."))

        # Over-scrubbing: the domain term should be here but its neighbours
        # got replaced by a person-shaped token.
        for term in domain_terms:
            pat = r"\b%s\b" % re.escape(term)
            if re.search(pat, text, re.I):
                continue
        if domain_terms and r["app"] in cfg.get("domain_apps", []):
            if not any(re.search(r"\b%s\b" % re.escape(t), text, re.I)
                       for t in domain_terms):
                findings.append(finding(
                    "scrub.over-scrubbed", "redaction-bug", "minor",
                    r["app"], rid,
                    "No domain vocabulary survives in a record that should have it",
                    text[:200],
                    "Check the scrubber didn't treat product or programme names "
                    "as PII. Domain terms carry the realism."))

    write_findings(findings, out)


if __name__ == "__main__":
    main()
