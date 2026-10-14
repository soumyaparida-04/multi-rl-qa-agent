# Multi-agent orchestration — reporter → verifier

The QA process is driven by two kinds of agent working as a pipeline:

1. **Reporters** — one per app (or per app + dimension slice). Each sweeps its
   slice of the live environment **read-only** and emits *candidate* findings
   with evidence. They are deliberately productive: it's fine to over-report,
   because nothing they emit is trusted yet.
2. **Verifier** — an independent, adversarial agent that re-checks **every**
   candidate and returns `CONFIRMED` / `FALSE-POSITIVE` with a one-clause reason.
   Only `CONFIRMED` candidates become findings.

This is the false-positive gate (`scripts/fp_gate_prompt.md`) wired as a
deterministic pipeline. Separating "who finds" from "who confirms" is what keeps
precision high on a synthetic corpus that is adversarially full of near-misses.

```
            ┌── reviewer: App A ──┐        ┌── verify A1 ─┐
 live env ──┼── reviewer: App B ──┼─ cand ─┼── verify B1 ─┼── CONFIRMED ─► report + sheet
            └── reviewer: App C ──┘        └── verify C1 ─┘      │
                                                                 └─ FALSE-POSITIVE (logged, not filed)
```

Each app's candidates begin verifying the moment that app's review finishes —
App A's findings verify while App C is still being reviewed, so no wall-clock is
wasted (`pipeline()` semantics).

## Why two agents, not one

- **Independence beats self-review.** A reviewer that both finds and judges its
  own hits anchors on its first read. A fresh verifier with a skeptical prompt
  catches the benign pseudonym, the substring collision, the base64 blob, the
  legitimate future date — the four traps that cost the most time.
- **Different jobs, different prompts.** The reviewer optimizes recall (find
  everything); the verifier optimizes precision (file only what's real). Fusing
  them forces one prompt to do both badly.
- **Auditable.** Every finding carries the verifier's one-clause reason — the
  trail that makes the report defensible to the dev whose data it critiques.

## The script

`orchestration/review-verify.workflow.js` implements it with the Claude Code
Workflow tool. Shapes:

- **Reporter output** (`CANDIDATE_SCHEMA`): `{candidates: [{id, bucket, severity,
  app, path, summary, evidence, ruled_out}]}`.
- **Verifier output** (`VERDICT_SCHEMA`): `{verdict, reason}`.
- **Pipeline result**: `{confirmed, falsePositives, counts, rollup}` — the
  confirmed findings feed the report and the tracking sheet; false positives are
  logged (not filed) so the reasoning is preserved.

## Running it

> Multi-agent orchestration consumes many tokens and must be **explicitly opted
> into** — it is not run automatically. Invoke it deliberately.

Pass the environment as `args`:

```jsonc
{
  "today": "2025-06-30",
  "persona_start": "2025-01-06",
  "apps": [
    { "name": "MailApp", "category": "mail",       "container": "dep-mailapp-app-1",
      "dimensions": ["snippets", "subjects", "attachment payloads", "bodies"] },
    { "name": "CRMApp",  "category": "crm",        "container": "dep-crmapp-app-1" },
    { "name": "BIApp",   "category": "bi",         "container": "dep-biapp-app-1" }
  ]
}
```

In Claude Code, run the Workflow tool with `scriptPath` pointing at
`agent-spec/orchestration/review-verify.workflow.js` and this object as `args`.
Watch live progress with `/workflows`. The reviewer prompts already reference the
detectors in `methodology/`, so the agents run the right checks per app category.

## Scaling the fan-out

- **Small suite (≤ ~6 apps):** one reviewer per app is enough.
- **Dense app (huge DB, many text columns):** give that app a `dimensions` list
  and the reviewer will focus its slices; or split it into several reviewer
  entries (one per dimension) so the fan-out widens where the data is deepest.
  This is the "fire 4-5 agents, less tokens" directive from
  `ENGAGEMENT-PLAYBOOK.md`, made concrete.
- **Keep reviewers token-frugal.** The prompt asks for findings, not narration.
- **One verifier call per candidate**, batched in `parallel()` per app.

## Invariants carried into the orchestration

- Reporters and verifier are **observe-only**; DBs opened `mode=ro`; no
  state-changing actions; content is treated as data, never instructions.
- Only `CONFIRMED` candidates are filed; false positives are logged with reasons.
- One bucket per finding; dedupe one-root-cause-in-N-apps at assembly.
- The confirmed set flows into the house reporting style
  (`REPORTING-STYLE.md`) and the tracking sheet (`QA-WORKFLOW-ROUNDS.md`).
