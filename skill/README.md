# The `multi-app-qa` skill

This folder is a self-contained Claude skill. It packages the method, the
checklist, the reviewer roles, and the automated sweep so an agent loads the
whole QA discipline on trigger.

## Install

Copy the skill folder into your Claude skills directory:

```bash
cp -R multi-app-qa ~/.claude/skills/
```

Then it triggers automatically when a request matches its description (QA'ing /
validating / auditing a synthetic multi-app or RL environment, checking
redaction/scrubbing quality, verifying data flows between apps), or invoke it
explicitly with `/multi-app-qa`.

## What's inside

| File | Purpose |
|---|---|
| `SKILL.md` | the method the agent follows on trigger (three buckets, workflow, gates) |
| `RUNBOOK.md` | copy-paste commands and the literal reviewer-agent prompts |
| `references/checklist.md` | all 19 checks → owner, method, bucket |
| `references/agents.md` | the 9 reviewer roles (scope + method) |
| `scripts/bootstrap_config.py` | derives ground truth (apps, window, cast, capabilities) |
| `scripts/check_temporal.py` | checklist items 1–3 |
| `scripts/check_references.py` | cross-app referential integrity |
| `scripts/check_scrub.py` | items 6, 7, 10, 14, 15, 16 |
| `scripts/check_entities.py` | items 8, 11 |
| `scripts/check_coverage.py` | items 17–19 |
| `scripts/normalize.py` | maps records to a common schema (date field aliases) |
| `scripts/run_all.py` + `qa.sh` | orchestrates the full sweep |
| `qa-config.example.json`, `qa-config.em.json` | worked config shapes |

## Quick start

```bash
bash qa.sh ./export                       # discover everything, write a draft config
bash qa.sh ./export brief.md              # discover, with the persona brief as ground truth
bash qa.sh ./export brief.md qa-config.json  # full sweep → REPORT.md, findings.csv, coverage-matrix.csv
```

## Relationship to the rest of this package

The skill covers the **mechanical half** of the method (temporal, references,
scrub, entities, coverage). The `methodology/` and `scripts/` folders at the
package root add the **deep manual/LLM half**: the detection heuristics that find
surviving PII in real corpora, the in-container querying of live multi-GB DBs,
the false-positive gate, and the per-round tracking-sheet discipline. The
`agent-spec/` folder ties both halves into a buildable autonomous agent.
