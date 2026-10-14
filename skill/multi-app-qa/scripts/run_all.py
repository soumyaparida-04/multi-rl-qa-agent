"""Run every automated checker and assemble the client report.

Usage:
    python run_all.py --in ./export --config qa-config.json --out ./qa-run

Produces in --out:
    records.jsonl        normalized corpus
    findings/*.jsonl     per-checker findings
    findings.csv         everything, flat, for triage
    coverage-matrix.csv  capability x app
    REPORT.md            the human-readable deliverable
"""

import csv
import os
import subprocess
import sys
from collections import Counter, defaultdict

from common import arg, load_findings

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKERS = ("check_temporal.py", "check_references.py",
            "check_scrub.py", "check_entities.py", "check_coverage.py")

SEV_ORDER = {"blocker": 0, "major": 1, "minor": 2, "info": 3}


def run(cmd):
    print("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=HERE)
    if proc.returncode != 0:
        print("  ! %s exited %d" % (cmd[1], proc.returncode))
    return proc.returncode


def main():
    src = arg("--in", required=True)
    cfg = os.path.abspath(arg("--config", "qa-config.json"))
    outdir = os.path.abspath(arg("--out", "./qa-run"))
    os.makedirs(os.path.join(outdir, "findings"), exist_ok=True)

    records = os.path.join(outdir, "records.jsonl")
    run([sys.executable, "normalize.py", "--in", os.path.abspath(src),
         "--out", records])

    for checker in CHECKERS:
        name = checker.replace("check_", "").replace(".py", "")
        cmd = [sys.executable, checker, "--records", records,
               "--config", cfg,
               "--out", os.path.join(outdir, "findings", name + ".jsonl")]
        if checker == "check_coverage.py":
            cmd += ["--matrix", os.path.join(outdir, "coverage-matrix.csv")]
        run(cmd)

    findings = []
    for f in sorted(os.listdir(os.path.join(outdir, "findings"))):
        findings += load_findings(os.path.join(outdir, "findings", f))
    findings.sort(key=lambda x: (SEV_ORDER.get(x["severity"], 9),
                                 x["bucket"], x["app"]))

    flat = os.path.join(outdir, "findings.csv")
    cols = ["severity", "bucket", "check", "app", "record_id", "summary",
            "evidence", "recommendation"]
    with open(flat, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for f in findings:
            w.writerow(f)

    by_bucket = Counter(f["bucket"] for f in findings)
    by_sev = Counter(f["severity"] for f in findings)
    by_app = Counter(f["app"] for f in findings)
    grouped = defaultdict(list)
    for f in findings:
        grouped[(f["bucket"], f["check"])].append(f)

    lines = [
        "# Multi-app environment QA — findings report",
        "",
        "Automated pass only. Judgement checks (tone, conversational realism, "
        "UI behaviour) are recorded separately by the reviewing agents — see "
        "the manual section at the end.",
        "",
        "## Summary",
        "",
        "| | count |",
        "|---|---|",
    ]
    for sev in ("blocker", "major", "minor", "info"):
        lines.append("| %s | %d |" % (sev, by_sev.get(sev, 0)))
    lines += ["", "| bucket | count |", "|---|---|"]
    for b in ("data-bug", "redaction-bug", "feature-gap"):
        lines.append("| %s | %d |" % (b, by_bucket.get(b, 0)))
    lines += ["", "| app | findings |", "|---|---|"]
    for app, n in by_app.most_common():
        lines.append("| %s | %d |" % (app, n))

    lines += ["", "## Findings by category", ""]
    for (bucket, check), items in sorted(
            grouped.items(), key=lambda kv: (SEV_ORDER.get(kv[1][0]["severity"], 9),
                                             kv[0])):
        worst = min(items, key=lambda x: SEV_ORDER.get(x["severity"], 9))
        lines += ["### %s — %s (%d)" % (check, bucket, len(items)),
                  "",
                  "Severity: **%s**. %s" % (worst["severity"],
                                            worst["recommendation"]),
                  ""]
        for f in items[:8]:
            loc = "%s %s" % (f["app"], f["record_id"] or "")
            lines.append("- `%s` — %s" % (loc.strip(), f["summary"]))
            if f["evidence"]:
                ev = f["evidence"].replace("\n", " ")[:180]
                lines.append("  > %s" % ev)
        if len(items) > 8:
            lines.append("- …and %d more, see findings.csv" % (len(items) - 8))
        lines.append("")

    lines += [
        "## Manual checks — to be completed by reviewer",
        "",
        "These cannot be automated. Record verdicts here before delivery.",
        "",
        "- [ ] Tone and vocabulary match the stated seniority and role",
        "- [ ] Conversations read like conversations — questions get answered, "
        "decisions have owners",
        "- [ ] A genuine tool switch has an explicit cutover date; a sourcing "
        "substitution does not",
        "- [ ] In-app search actually filters before any \"found nothing\" is "
        "trusted",
        "- [ ] Every offered attachment opens and isn't empty — list what "
        "wouldn't open",
        "- [ ] Images and file metadata carry no surviving PII",
        "",
    ]

    with open(os.path.join(outdir, "REPORT.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\n%d findings — %s blockers, %s major"
          % (len(findings), by_sev.get("blocker", 0), by_sev.get("major", 0)))
    print("report  -> %s" % os.path.join(outdir, "REPORT.md"))
    print("triage  -> %s" % flat)


if __name__ == "__main__":
    main()
