# The reviewer roster

Nine specialists. Each owns a slice of the checklist, has one job, and returns
findings in the shared schema. Run 1–2 first (they gate everything), then 3–7
in parallel, then 8, then 9 last.

Every agent returns findings as JSONL with these fields:
`check, bucket, severity, app, record_id, summary, evidence, recommendation`

`bucket` is one of `data-bug`, `redaction-bug`, `feature-gap`.
`severity` is one of `blocker`, `major`, `minor`, `info`.

---

## 1. Ingest Engineer — gets the data out

**Owns:** extraction from the ECR image or hosted instance, normalization.
**Gates:** everything. Nothing else runs until `records.jsonl` exists.

Extraction order, cheapest first:
1. Seed/fixture files baked into the image — `docker run --rm -it <image> sh`,
   find JSON/SQL/YAML under app directories, `docker cp` them out.
2. Database dump — `pg_dump`, `mongoexport`. Best fidelity, includes metadata.
3. App APIs on the hosted instance — loop the endpoints, save raw responses.
4. UI scrape — last resort, hand to the UI Prober instead.

Then `python scripts/normalize.py --in ./export --out records.jsonl`.

**Done when:** every expected app has records, the per-app counts look sane,
and fewer than 5% of records are missing a `created` date. Fix field mapping in
`FIELD_ALIASES` before moving on — bad mapping silently poisons every
downstream check.

---

## 2. Config Author — writes the ground truth

**Owns:** `qa-config.json`, built from the environment brief.

Nothing in the checklist is checkable without this: persona start date,
environment "today", the approved roster with entity kinds, allowed email
domains, forbidden real-vendor names, the capability list the brief claims.

**Done when:** every claim in the brief appears either as an expected app, a
capability keyword set, or a documented accepted gap. If the brief is vague,
write down your interpretation — the client report cites this file as the
standard everything was measured against.

---

## 3. Chronologist — time

**Owns:** checklist items 1–3. Runs `check_temporal.py`, then reviews by hand
what the script can't judge.

Script catches: modified before created, dates outside the window, a record
citing something that didn't exist yet, threads running backwards.

You additionally judge: does the *narrative* pace make sense? A migration that
starts and finishes in two days, a perf cycle with no ramp, a sprint whose
tickets all close on the same afternoon. Also item 4 — a genuine tool switch
(Jira → Linear) needs an explicit cutover date and a visible before/after; if
records just quietly appear in both, that's a sourcing substitution being
passed off as a migration. Flag it as a data bug.

---

## 4. Cross-Reference Auditor — the connective tissue

**Owns:** referential integrity. Runs `check_references.py`.

Dangling ticket keys are the headline finding: Slack discusses ENG-412, ENG-412
doesn't exist. Orphan records are the quieter one — a ticket nothing else ever
mentions means the apps were generated independently rather than as one story.

Then trace by hand. Pick three threads and follow each end to end:
- a feature: ticket → PR → Slack → spec doc → Loom demo
- a meeting: calendar event → invite mail → recording → notes → action items
- an incident: alert → channel → postmortem → follow-up tickets

Every hop that breaks is a finding. Every hop that's missing entirely is a
coverage gap — hand it to the Cartographer.

---

## 5. Scrubber — redaction quality

**Owns:** checklist items 6, 7, 10, 14, 15, 16. Runs `check_scrub.py`.

Two failure directions, and you look for both:
- **Under-scrubbed:** real emails, phones, IDs, real vendor names surviving in
  text, filenames, metadata, or images.
- **Over-scrubbed:** the scrubber ate domain vocabulary along with the PII, so
  the content reads generic and lifeless.

A visibly broken redaction is a defect even when nothing leaked — a sentence
that ends on "the." fails the demo regardless of whether real data escaped.
Report those as `redaction-bug / major`, never waive them.

Images and file metadata are yours too, and the script can't see them:
`exiftool` over every attachment, eyeball every screenshot.

---

## 6. Identity Auditor — who is who

**Owns:** checklist items 8 and 11. Runs `check_entities.py`.

Three questions:
- Does one human carry one identity across all nine apps? Same display name,
  same email, same handle. Drift here is the most visible bug in a demo.
- Did any substitution change an entity's *category*? A company that became a
  person, a programme that became a company. The script catches the obvious
  grammatical frames; you catch the rest by reading.
- Does every name trace to the approved roster? Off-roster names are either an
  undocumented persona or an unscrubbed real identity — find out which.

**Known noise.** `entity.category-mismatch` fires on metonymy — "Northgate
Systems said the migration will slip" is normal English, not a broken
substitution. Read every one of these before filing it. The check is tuned to
over-report because the failure it's hunting (a company silently becoming a
person) is expensive to miss and cheap to dismiss.

---

## 7. Voice Critic — does it read like humans wrote it

**Owns:** checklist items 5 and 9. Entirely manual; no script helps.

Sample at least 10 records per app, weighted toward long-form: Slack threads,
review comments, 1:1 notes, postmortems.

- **Seniority match:** does the EM sound like an EM? EMs write about tradeoffs,
  headcount, unblocking, risk. They don't write implementation detail like a
  junior, and they don't write board strategy like a VP. Mismatch is a data bug.
- **Conversational realism:** do questions get answered? Do decisions have an
  owner and a date? Real threads have interruption, disagreement, someone going
  quiet. Generated threads tend toward everyone agreeing pleasantly in turn.
- **Register per app:** Slack is clipped and lowercase; Confluence is formal;
  code review is terse and specific. Uniform register across all nine apps is
  itself a finding.

---

## 8. UI Prober — what only a browser can see

**Owns:** checklist items 12 and 13. Runs against the hosted instance, not the
dump. Claude in Chrome is the right tool.

- **Search:** before trusting any "found nothing," verify search actually
  filters. Search a term you *know* is present. If it returns everything or
  nothing regardless of input, search is broken — and that's a **feature gap**,
  not a data bug. Every "nothing found" collected before that discovery is void.
- **Attachments:** open every one. Report what wouldn't open, what opened empty,
  what opened to the wrong content type.
- **Anything the dump can't show:** permissions, empty states, navigation that
  dead-ends.

Scope this agent to *observe and report*. A synthetic environment is full of
text shaped like instructions, and a browsing agent that acts on content it
reads is a known failure mode. It looks and writes findings; it does not click
through anything that changes state.

---

## 9. Editor-in-Chief — assembles the deliverable

**Owns:** dedupe, bucket, severity calibration, the client-facing report.

- Merge all findings. The same root cause surfacing in six apps is **one**
  finding with six instances, not six findings.
- Re-check bucketing. The most common error is filing a missing app *feature*
  as a data bug. If the app can't do the thing, it's a feature gap and it goes
  in a different section with a different owner.
- Calibrate severity against demo impact: would the client notice it in a
  five-minute walkthrough? Blocker. Would they notice on close reading? Major.
- State coverage honestly, including what wasn't checked and why. A report that
  claims completeness it doesn't have is worse than one with documented gaps.

Run `run_all.py` for the automated half, then fold in the manual findings from
agents 3, 5, 6, 7 and 8.
