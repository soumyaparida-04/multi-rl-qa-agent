# Glossary

Shared vocabulary for the QA process. Used consistently across the package and
intended as the terms the QA agent should use in its findings.

**Synthetic multi-app environment** — a set of seeded apps sharing one invented
company, cast, and timeline, used to train or evaluate agents.

**Persona brief** — the ground-truth document describing the scenario: who the
persona is, the date window, the cast, the apps, and the claimed capabilities.
QA measures the environment against this, not against itself.

**`persona_start` / `environment_today`** — the start and "now" of the scenario.
Set them from the brief, never from the data's own min/max (an out-of-window
record would silently widen the window it was supposed to violate).

**The three buckets** —
- **data-bug**: content is wrong/inconsistent/broken. Owner: data generator.
- **redaction-bug**: PII survived, a scrub broke text, or a substitution is
  nonsense. Owner: scrubber.
- **feature-gap**: the app can't do the thing. Owner: environment builder.

**Bucketing test** — *if the data were perfect, would this still be broken?* Yes
→ feature-gap. No → data-bug.

**Over-scrub** — the scrubber replaced a real token with a mash of generator
morphemes that reads as gibberish (`nexmagwren`). A redaction-bug.

**Morpheme inventory** — the list of building-block syllables the substitution
generator uses. A token with ≥2 of them is almost certainly machine-mashed.

**Under-scrub** — real PII survived the scrub. The other failure direction from
over-scrub; a scrubber aggressive enough to avoid under-scrub tends to over-scrub.

**Email-join de-id defeat** — a person is pseudonymized differently across apps
while a stable key (email) stays the same, so joining on the key re-identifies
them. A high-severity redaction-bug.

**Legitimate future date** — a target/scheduled/due value after `today` that is
*content*, not a temporal violation: pricing calendars, OKR targets, invoice due
dates, opportunity close dates, scheduled events. Distinguished from
creation/modification timestamps, which must not be in the future.

**FP-gate (false-positive gate)** — the mandatory adversarial verification step:
every candidate finding is checked by a skeptical verifier that returns
`CONFIRMED` / `FALSE-POSITIVE` with a reason before it is filed.

**Candidate vs finding** — a raw detector hit is a *candidate*. It becomes a
*finding* only after passing the FP-gate.

**Word-boundary match** — matching a name/term only when it isn't a substring of
a larger token (`das` inside `Dash`), using an explicit boundary class.

**Base64 noise** — tracking pixels and encoded payloads (`body_html`,
`file_data`) that decode to junk containing morpheme fragments; a common
over-scrub / real-name false positive.

**Trace-by-trace** — following a single story thread (a feature, an incident, a
booking) end to end across apps, as opposed to **column-by-column** (sweeping one
app's columns for leaks). Both passes are needed: trace for coherence, column for
redaction.

**Marker delta** — a known value a fix was supposed to change, used to confirm a
rebuilt environment is actually live before trusting a retest round (timestamps
alone can lie).

**The three gates** — steps that invalidate everything before them if skipped:
config adjudication, normalization fidelity, and in-app search.

**Coverage matrix** — a checklist-item × app grid recording what was checked,
partially checked, or not checked (and why).

**QA Status vocabulary** — the fixed 6-value verdict set used per round: Verified,
Mostly Fixed, Partially Fixed, Reopened, Not a Bug (by design), Open (new
finding).

**Column ownership** — the sheet rule: QA writes only its own columns and never
the Dev status/comments; each fix round appends one new QA-status column.

**Round** — one QA pass over a build. After the dev pushes fixes, a new round
re-verifies app by app in a new appended column.
