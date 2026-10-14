# The checklist, mapped

19 checks. Each has an owner, a method, and a default bucket. "Auto" means a
script decides; "manual" means a person or an agent reads and judges; "hybrid"
means the script narrows the field and a human rules on what it surfaces.

| # | Check | Owner | Method | Default bucket |
|---|---|---|---|---|
| 1 | "Modified" never predates "created" | Chronologist | auto | data-bug |
| 2 | Nothing after environment "today," nothing before persona start | Chronologist | auto | data-bug |
| 3 | Referenced events in sane order — nothing shared before it existed | Chronologist | auto | data-bug |
| 4 | Genuine tool switch has an explicit cutover date; a sourcing substitution does not | Chronologist | manual | data-bug |
| 5 | Tone and vocabulary match stated seniority and role | Voice Critic | manual | data-bug |
| 6 | No broken sentences from a redaction token dropped mid-sentence | Scrubber | auto | redaction-bug |
| 7 | Domain vocabulary not over-scrubbed along with real PII | Scrubber | hybrid | redaction-bug |
| 8 | Replacement names fit what they replaced (company ≠ person ≠ programme) | Identity Auditor | hybrid | redaction-bug |
| 9 | Conversations read like conversations — questions answered, decisions owned | Voice Critic | manual | data-bug |
| 10 | Sweep for leftover placeholders (TBD, Masked Address, `<name>`, null, example.com) | Scrubber | auto | redaction-bug |
| 11 | Sweep for nonsense name substitutions in running text | Identity Auditor | hybrid | redaction-bug |
| 12 | Confirm in-app search actually filters before trusting a "found nothing" | UI Prober | manual | feature-gap |
| 13 | Every offered attachment opens and isn't empty — report what you couldn't open | UI Prober | manual | data-bug |
| 14 | No real names, emails, phones, addresses or IDs survive — text, filenames, metadata, images | Scrubber | hybrid | redaction-bug |
| 15 | A visibly broken redaction is still a bug, even when no PII leaked | Scrubber | auto | redaction-bug |
| 16 | No real outside company, vendor or product name left in by accident | Scrubber | auto | redaction-bug |
| 17 | Every app in the brief is present with content, or its absence is documented and accepted | Cartographer | auto | data-bug |
| 18 | Every capability the brief claims is backed by evidence in at least one app | Cartographer | auto | data-bug |
| 19 | Missing app features logged as feature gaps, not data bugs | Editor-in-Chief | manual | feature-gap |

## Notes on the tricky ones

**#4 — tool switch vs sourcing substitution.** The tell is whether the
environment *narrates* the change. A real migration has a cutover date, a
decision doc, a Slack announcement, and a visible before/after in the data. A
sourcing substitution has none of that — records simply exist in both tools with
no explanation. If you can't find the cutover, it isn't a migration.

**#7 vs #14 — the scrubber pulls in two directions.** Under-scrubbing leaks PII.
Over-scrubbing destroys the domain vocabulary that makes the environment
believable. Check both on the same pass; a scrubber tuned aggressively enough to
pass #14 usually fails #7.

**#12 — search is a gate, not a check.** Verify search works *before* running
any search-based investigation. If it doesn't filter, every "I found nothing"
you collected is void and must be re-run by other means.

**#19 — the bucketing discipline.** Ask: if the data were perfect, would this
still be broken? Yes → feature gap, and it belongs to whoever builds the app.
No → data bug, and it belongs to whoever generates the data. Getting this wrong
sends findings to the wrong team and wastes a cycle.
