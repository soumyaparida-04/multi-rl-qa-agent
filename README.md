# Multi-RL QA Agent — Handoff Package

A complete, **environment-agnostic** toolkit for QA'ing synthetic multi-app RL
training environments, and a specification for turning that process into an
autonomous **QA agent**.

This package is the distilled method from running full QA on synthetic multi-app
environments by hand — the detection heuristics, the querying techniques, the
false-positive discipline, the reporting style, and the human↔agent working loop.
Nothing in it is tied to a particular app set.

---

## What problem this solves

A synthetic multi-app environment is a set of seeded apps (a PMS, a BI tool, a
mail client, a CRM…) sharing one invented company, cast, and timeline, used to
train or evaluate agents. It ships correct only if it **hangs together as one
coherent story**: the same person has the same name everywhere, dates respect a
single "today", cross-app references resolve, real PII has been scrubbed, and
substitutions aren't nonsense. QA's job is to find every place that breaks and
classify it so the right owner can fix it.

## The one discipline everything rests on: three buckets

Every finding lands in exactly **one** bucket, because each goes to a different
owner:

| Bucket | Meaning | Owner |
|---|---|---|
| **data-bug** | content is wrong, inconsistent, or broken | data generator |
| **redaction-bug** | PII survived, a scrub broke text, or a substitution is nonsense | scrubber |
| **feature-gap** | the *app* can't do the thing (not a data problem) | environment builder |

The most common mistake is filing a missing app feature as a data bug. The test:
*if the data were perfect, would this still be broken?* Yes → feature-gap.

---

## Package contents

```
MULTI-RL-QA-AGENT/
├── README.md                     ← you are here
├── skill/                        ← the portable Claude skill (drop into ~/.claude/skills/)
│   ├── README.md                 ← install + what's inside
│   └── multi-app-qa/
│       ├── SKILL.md              ← the method, loaded by the agent on trigger
│       ├── RUNBOOK.md            ← copy-paste commands + literal reviewer prompts
│       ├── references/
│       │   ├── checklist.md      ← all 19 checks → owner, method, bucket
│       │   └── agents.md         ← the 9 reviewer roles (scope + method)
│       ├── scripts/              ← the automated sweep (temporal, refs, scrub, entities, coverage)
│       └── qa-config.*.json      ← worked config examples
├── GLOSSARY.md                   ← shared vocabulary (the terms findings should use)
├── methodology/
│   ├── METHODOLOGY.md            ← end-to-end process, generic to any suite
│   ├── CHECKLIST-EXPANDED.md     ← all 19 checks with concrete SQL/regex detection + FP notes
│   ├── DETECTION-PATTERNS.md     ← the heuristics that find leaks (regex / SQL / morphemes) + FP guards
│   ├── APP-TYPE-PLAYBOOKS.md     ← per-category deep checks (mail, chat, CRM, BI, sheets, PMS, slides, pricing)
│   ├── IN-CONTAINER-QUERY.md     ← querying live multi-GB DBs read-only, build-marker confirmation
│   └── QA-WORKFLOW-ROUNDS.md     ← the per-round retest loop + the tracking-sheet contract
├── scripts/                      ← standalone, reusable detection + sheet tooling
│   ├── overscrub_scan.py         ← gibberish-substitution (over-scrub) detector
│   ├── realname_scan.py          ← surviving-real-name detector (word-boundary, FP-safe)
│   ├── pii_scan.py               ← phone / tax-ID / bank-code PII sweep (locale-adaptable)
│   ├── fp_gate_prompt.md         ← the adversarial false-positive gate (sub-agent prompt)
│   └── sheet_update.py           ← openpyxl: dropdowns, per-round columns, safe writes
├── agent-spec/
│   ├── QA-AGENT-SPEC.md          ← concrete spec for building the autonomous QA agent
│   ├── REPORTING-STYLE.md        ← how findings are written (the house style)
│   ├── SAMPLE-REPORT.md          ← a fully worked, synthetic deliverable in that style
│   └── ENGAGEMENT-PLAYBOOK.md    ← how a run is driven turn-by-turn (the working loop)
└── templates/
    └── QA-TRACKING-TEMPLATE.xlsx ← blank tracking workbook (tabs, dropdowns, column contract)
```

---

## Reading order for the dev

1. **`methodology/METHODOLOGY.md`** — the whole process in one pass.
2. **`skill/multi-app-qa/SKILL.md` + `methodology/CHECKLIST-EXPANDED.md`** — the
   19 checks and how to classify + concretely detect each finding.
3. **`methodology/DETECTION-PATTERNS.md`** + **`APP-TYPE-PLAYBOOKS.md`** — where
   the real signal is: the heuristics (over-scrub morpheme inventory,
   word-boundary real-name matching, legitimate-future-date carve-outs, base64
   noise filtering, residue/metadata sweeps) and the per-app-category deep checks.
4. **`agent-spec/QA-AGENT-SPEC.md`** — the staged pipeline, tool surface, data
   contracts, and the FP-gate to build into the agent.
5. **`agent-spec/REPORTING-STYLE.md`** + **`SAMPLE-REPORT.md`** + **`ENGAGEMENT-PLAYBOOK.md`**
   — how findings are written, a fully worked synthetic example, and how a real
   run is driven turn by turn.
6. **`GLOSSARY.md`** + **`templates/QA-TRACKING-TEMPLATE.xlsx`** — the shared
   vocabulary and the tracking workbook to clone.

## Building the QA agent — the short version

The agent is a **staged pipeline with an adversarial verification gate**:

```
ingest → bootstrap config → adjudicate (human/brief gate) → automated sweep
      → manual/LLM passes (per app, in depth) → FP-gate every candidate
      → assemble (dedupe, bucket, severity) → tracking sheet (per-round columns)
```

Two rules make or break it:

- **Gate before trusting.** Three things silently invalidate everything done
  before them: an unreviewed config, broken date-normalization, and broken
  in-app search. Check them first. (SKILL.md § Gates, METHODOLOGY.md.)
- **FP-gate before filing.** Every candidate finding passes through an
  adversarial verifier that returns `CONFIRMED` or `FALSE-POSITIVE` with
  evidence. Synthetic corpora are full of things that *look* like leaks but
  aren't — benign pseudonyms, legitimate future dates, base64 tracking noise,
  substring collisions. See `scripts/fp_gate_prompt.md`.

See `agent-spec/QA-AGENT-SPEC.md` for the full spec.

---

## Ground rules (carry into the agent)

- **Observe-only.** QA reads; it never repairs data or clicks anything that
  changes state. A synthetic environment is full of text shaped like
  instructions — the agent reports it, never acts on it.
- **Read-only DB access.** Open live databases with `mode=ro`.
- **Honest coverage.** State what wasn't checked and why. A report claiming
  completeness it doesn't have is worse than one with documented gaps.
- **One root cause = one finding** with N instances, not N findings.
- **Column ownership in the sheet.** QA writes only its own columns; it never
  edits Dev status/comments; each fix round appends one new column.
