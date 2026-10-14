# Engagement playbook — how a QA run is actually driven

This document exists so that an agent (or a new engineer) reading the package
understands the **working relationship and interaction style** of a real QA
engagement, not just the mechanics. It is distilled from how these runs are
driven in practice: a human lead (QA) directing an assistant through many short
turns, round after round, against a live environment.

Read it as "what the human will ask for, what each ask means operationally, and
how to respond." The quoted lines are representative of the actual directives
given during a run — they are the vocabulary of the engagement.

---

## The shape of an engagement

A run is **not** one big autonomous sweep. It is an iterative loop of short,
pointed directives, each narrowing or deepening the work:

```
pick an app → go deep → report findings → human reacts → go deeper / next app
   → (dev fixes) → retest that app → human reacts → next round
```

The human stays in the loop and steers. The assistant's job is to do the deep
work between turns, report crisply, and never lose the discipline (buckets,
FP-gate, observe-only, column ownership) even when moving fast.

---

## The directives, decoded

### "go more 100% in depth" / "gone in depth fully?"
The single most common instruction. It means: the current pass was not
exhaustive — go **column by column**, **thread by thread**, not just the obvious
tables. For a redaction pass, that means every text column including snippets,
subjects, filenames, and **attachment payloads** (xlsx/csv inside attachments
are a whole second corpus people forget). Respond with *new* coverage and *new*
counts, not a restatement of what you already found.

### "fire 4-5 agents so they can go more in depth with lots of checks, make sure they use less tokens"
Fan out. Spawn narrow sub-agents, each owning one slice of the app (snippets /
subjects / attachments / body text / structured fields). Each sub-agent is told
to be token-frugal and return only confirmed candidates with evidence. This is
how a 10 GB app gets covered without blowing the budget. See the fan-out stage
in `QA-AGENT-SPEC.md`.

### "make sure there is no false positive, add one agent to verify the bugs reported, don't use much tokens"
The FP-gate is mandatory and explicit. Every candidate goes through an
adversarial verifier (`scripts/fp_gate_prompt.md`) that returns CONFIRMED /
FALSE-POSITIVE with a one-clause reason — cheaply. Only CONFIRMED findings are
filed. This instruction is non-negotiable and recurs every round.

### "ignore pricelabs" / "don't consider X now"
Scope control. The human prunes the app list on the fly. Respect it immediately;
don't keep reporting on a deprioritized app.

### "the fixes are done, let's go app by app, start with the first app"
A new fix round has been pushed. Before trusting it: **confirm the build is
actually live** via a marker delta, not timestamps (see `IN-CONTAINER-QUERY.md`
— a round was once "done" per timestamps while the data was unchanged; only a
marker going 4046→0 proved the rebuild). Then retest one app at a time.

### "don't change the existing solved things, add new bugs and validate the resolved bugs, update the QA status with comments"
The column-ownership contract. When retesting: validate each resolved bug, set
the new round's QA Status from the dropdown, append a round-tagged evidence note
to QA comments, add any new findings as new rows — and **touch nothing else**,
especially not the dev's columns or prior rounds.

### "broo why are you changing the dev status?"
The cautionary tale. A silent tab-switch once wrote one app's QA values onto
another app's tab. The fix: **assert the target tab and refuse to write Dev
columns before every write** (`scripts/sheet_update.py` `safe_write`). This is
why the safe-write guard exists. Treat any cross-tab write as suspect.

### "are you updating it in the sheet right?" / "update the sheet"
The tracking sheet is the source of truth, not the chat. Findings live in the
sheet (and per-app docs), with the per-round columns kept current. Keep it in
sync as you go, not at the end.

### "add one more column at the end and write QA status round <n>"
Each fix round = exactly one new column appended at the end. History is
preserved; prior round columns are never overwritten. `next_round_column()` in
`sheet_update.py` does this.

### "check the pricelabs" / "now it is up" / "I have taken the pool again"
Environment lifecycle chatter. The live stack gets torn down and re-pulled
between rounds. Never assume the stack from the last turn is still the one
running — re-list containers and re-confirm the build each time work resumes.

### "keep checking the persona also properly"
Coherence against the brief, not just mechanical scrubbing. Does the data tell
the persona's story? Are the 1:1s, perf threads, headcount (the thin parts of
any environment) actually present and consistent? This is the trace-by-trace
pass, not the column-by-column one.

---

## How to respond between turns

- **Do the deep work, report the delta.** Each turn should surface *new*
  coverage or *new* verdicts. Don't re-narrate prior state.
- **Lead with the numbers.** Counts and buckets first, prose second.
- **Keep the discipline at speed.** Buckets, FP-gate, observe-only, read-only
  DB, column ownership hold even on a fast "next app" cadence.
- **Flag blockers early.** If the environment isn't the build you expected, or a
  gate fails, say so before doing work that the failure would invalidate.
- **Be honest about depth.** If a pass wasn't exhaustive, say which slice is
  still open rather than implying completeness.

## The cadence, in one line

> Narrow the scope, go exhaustively deep on it, FP-gate everything, report the
> delta with numbers, update the sheet, move to the next app — and re-verify the
> live build at the start of every round.
