"""Coverage against the brief.

Covers checklist items 17-19:
  - every app in the brief is present with content, or its absence is a
    documented, accepted gap
  - every capability the brief claims is backed by evidence in at least
    one app
  - missing app features are logged as feature gaps, not data bugs

Capabilities are declared in qa-config.json as keyword sets. A capability
counts as evidenced when a record matches enough of its keywords. The point
isn't precision -- it's producing a matrix you can hand a client and defend.

Usage:
    python check_coverage.py --records records.jsonl --config qa-config.json \
        --out findings/coverage.jsonl --matrix coverage-matrix.csv
"""

import csv
import os
import re
from collections import defaultdict

from common import (arg, finding, load_config, load_records, text_of,
                    write_findings)


def main():
    recs = list(load_records(arg("--records", "records.jsonl")))
    cfg = load_config(arg("--config", "qa-config.json"))
    out = arg("--out", "findings/coverage.jsonl")
    matrix_path = arg("--matrix", "coverage-matrix.csv")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    expected_apps = cfg.get("expected_apps", [])
    accepted_gaps = set(a.lower() for a in cfg.get("accepted_gaps", []))
    capabilities = cfg.get("capabilities", {})   # name -> [keywords]
    min_records = int(cfg.get("min_records_per_app", 5))

    per_app = defaultdict(list)
    for r in recs:
        per_app[r["app"]].append(r)

    findings = []

    # ---- app presence
    for app in expected_apps:
        got = per_app.get(app, [])
        substantive = [r for r in got if len(text_of(r).strip()) > 40]
        if not got:
            if app.lower() in accepted_gaps:
                findings.append(finding(
                    "coverage.accepted-gap", "feature-gap", "info", app, "",
                    "App absent, listed as an accepted gap in the brief", "",
                    "No action. Keep it documented in the client report."))
            else:
                findings.append(finding(
                    "coverage.app-missing", "data-bug", "blocker", app, "",
                    "App named in the brief has no records at all", "",
                    "Generate content or get the absence accepted and "
                    "documented as a gap."))
        elif not substantive:
            findings.append(finding(
                "coverage.app-empty-shell", "data-bug", "major", app, "",
                "App present but every record is empty or near-empty",
                "%d records, none over 40 chars" % len(got),
                "Populate with real content; empty shells fail a demo."))
        elif len(substantive) < min_records:
            findings.append(finding(
                "coverage.app-thin", "data-bug", "minor", app, "",
                "App has only %d substantive records (min %d)"
                % (len(substantive), min_records), "",
                "Thin apps read as an afterthought. Add depth or justify."))

    for app in sorted(set(per_app) - set(expected_apps) - {"unknown"}):
        findings.append(finding(
            "coverage.unexpected-app", "data-bug", "minor", app, "",
            "Records found for an app not named in the brief", "",
            "Confirm intended; otherwise remove or add to the brief."))

    # ---- capability evidence
    rows = []
    for cap, keywords in capabilities.items():
        kws = [k.lower() for k in keywords]
        hits = defaultdict(int)
        examples = {}
        for r in recs:
            blob = text_of(r).lower()
            matched = sum(1 for k in kws if re.search(r"\b%s" % re.escape(k), blob))
            if matched >= max(1, len(kws) // 2):
                hits[r["app"]] += 1
                examples.setdefault(r["app"], r.get("id") or r.get("title") or "")
        rows.append((cap, hits, examples))
        if not hits:
            findings.append(finding(
                "coverage.capability-unevidenced", "data-bug", "blocker",
                "-", "",
                "Brief claims '%s' but no app shows evidence of it" % cap,
                "keywords: %s" % ", ".join(keywords),
                "Either generate the supporting artefacts or withdraw the "
                "claim from the brief."))
        elif len(hits) == 1 and cfg.get("require_multi_app_capabilities"):
            only = list(hits)[0]
            findings.append(finding(
                "coverage.capability-single-app", "data-bug", "minor",
                only, "",
                "'%s' is evidenced in %s only" % (cap, only), "",
                "Multi-app workflows should leave a trail in more than one "
                "place."))

    # ---- write the matrix
    apps = expected_apps or sorted(per_app)
    with open(matrix_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["capability"] + apps + ["status"])
        for cap, hits, _ex in rows:
            status = ("unevidenced" if not hits else
                      "single-app" if len(hits) == 1 else "ok")
            w.writerow([cap] + [hits.get(a, 0) for a in apps] + [status])
        w.writerow([])
        w.writerow(["record count"] + [len(per_app.get(a, [])) for a in apps] + [""])

    write_findings(findings, out)
    print("coverage matrix -> %s" % matrix_path)


if __name__ == "__main__":
    main()
