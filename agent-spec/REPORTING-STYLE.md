# Reporting style — how findings are written

The report is the product. A finding nobody can act on, or a report that claims
more coverage than it has, destroys trust in the whole QA pass. This document
defines the house style the QA agent must follow.

---

## Principles

1. **Every finding is actionable by its owner.** The owner is implied by the
   bucket (data-bug → data generator, redaction-bug → scrubber, feature-gap →
   environment builder). Write so that owner can reproduce and fix without
   asking a question.
2. **Evidence over assertion.** Never "names are leaking". Instead: the exact
   column, the count of distinct instances, and a redacted sample.
3. **One root cause = one finding.** If the same scrub miss shows up in six
   apps, it is one finding with six instances, not six findings.
4. **Quantify.** "513 snippets, 37 subjects, ~52% of xlsx attachment payloads"
   beats "many". Counts set severity and let the dev confirm the fix landed.
5. **State coverage honestly.** Say what was checked, what wasn't, and why. A
   documented gap is a feature of the report; a hidden one is a liability.
6. **Neutral, specific tone.** No hedging ("might possibly"), no drama. A defect
   is stated as a fact with evidence, or it isn't filed.

## The anatomy of a finding

Each finding carries these fields (they map 1:1 to the tracking-sheet columns):

| Field | Rule |
|---|---|
| **id** | stable tag, e.g. `OL2`, `PB6`, `XA1` (app-initials + number). Used to reference it across rounds and in comments. |
| **Bug Summary** | one line, `[id] <what is wrong, where>`. Starts with the id tag. |
| **Path** | precise location: `app → table.column`, or UI path. Reproducible. |
| **Reference / Evidence** | a redacted sample + the count of distinct instances. |
| **Type** | exactly one bucket: data-bug / redaction-bug / feature-gap. |
| **Severity** | blocker / high / medium / low, by the demo-impact rubric. |
| **Verdict (QA Status)** | from the 6-value vocabulary, per round. |

## Writing the Bug Summary

- Lead with the id, then the defect, then the location.
  - Good: `[PB6] 8,623 GSTIN tax IDs present unredacted in dataset values (Power BI → dataset_table_data.rows_json)`
  - Bad: `PII issue in Power BI` (no id, no count, no location, not actionable)
- Keep it to one line. Detail goes in Evidence.

## Writing Evidence

- Give a **redacted** sample — enough to recognize the pattern, never the full
  live PII. Mask the middle: `9XXXXX1234`, `ABXXX1234C`.
- Give the **distinct count** and the **column(s)**.
- If it's cross-app, name every app the instance appears in.
- If a detector produced it, name the detector and the FP rules you ruled out —
  this is the audit trail that makes the finding defensible.

## Severity rubric (demo-impact)

| Severity | Test |
|---|---|
| **Blocker** | breaks the story in a 5-minute demo walkthrough, or leaks real PII at scale |
| **High** | wrong/inconsistent across apps, or a systemic redaction miss in a visible field |
| **Medium** | localized inconsistency, or PII in a low-visibility field |
| **Low** | cosmetic, rare, or buried deep in a payload |

## Per-app findings document

For each app, a short markdown doc:

```
# <App> — findings

## Summary
N findings: X data-bug, Y redaction-bug, Z feature-gap. Headline: <one line>.

## Findings
### [id] <one-line summary>
- Type / Severity: redaction-bug / blocker
- Path: <app → table.column>
- Evidence: <count distinct>, sample `9XXXXX1234`; ruled out FP rules 2,3.
- Notes: <anything the dev needs>

## Coverage
Checked: <columns / threads / capabilities>.
Not checked (and why): <honest list>.
```

## The assembled report

- Opens with a **coverage statement** (apps covered, checklist items run,
  explicit gaps).
- A **rollup table**: per-app counts by bucket and by severity.
- Findings grouped by app, blockers first.
- A **cross-app** section for anything spanning apps (identity/reference
  integrity).
- Closes with the **top escalations** — the 3–5 things the dev should fix first.

## Round-to-round comments

When re-verifying after a fix, append (never overwrite) a dated, round-tagged
note to QA comments:

```
R2: re-ran realname_scan on rebuilt stack — snippets 513→0, subjects 37→0,
attachment payloads still ~52%. Partially Fixed.
```

The verdict word comes from the 6-value dropdown; the note carries the evidence
of *why* that verdict.

## What never appears in a report

- Unverified detector output (everything is FP-gated first).
- Full, unredacted real PII (always masked in the write-up).
- Vague severity or vague counts ("some", "a lot").
- Claims of completeness the pass didn't achieve.
