# The 19 checks — expanded, with concrete detection

The skill's `references/checklist.md` maps each check to an owner, method, and
default bucket. This document goes one level deeper: for each check, *how to
actually detect it* (SQL / regex / procedure), the common false positives, and
what good evidence looks like. Build each of these into the agent as a discrete
detector with its FP guard.

Legend — **Bucket**: data-bug (D) / redaction-bug (R) / feature-gap (G).
**Method**: auto / hybrid / manual.

---

## Temporal integrity (1–3) — Chronologist · auto · D

### 1. "Modified" never predates "created"
```sql
SELECT count(*) FROM t WHERE modified_at < created_at;
```
Evidence: `<table>.<pk>` with the two timestamps. FP: none — this is a hard
invariant. If a table legitimately lacks `modified`, skip it, don't fudge.

### 2. Nothing after "today", nothing before persona start
```sql
SELECT count(*) FROM t WHERE created_at > :today;       -- future violation
SELECT count(*) FROM t WHERE created_at < :persona_start; -- pre-join violation
```
**Critical FP — legitimate future dates.** Separate *creation/modification*
timestamps (violations) from *target/scheduled/due* fields (content): pricing
calendars, OKR target dates, invoice due dates, opportunity close dates,
scheduled meetings. Classify by field semantics, never by value. (See
`DETECTION-PATTERNS.md` §4.)

### 3. Referenced events in sane order
Nothing is shared/linked before it existed. A message at T mentions an artifact
created at T+n. Requires joining the reference to the referent and comparing
timestamps. Evidence: the message, the artifact, both timestamps.

---

## Narrative & voice (4, 5, 9) — Chronologist / Voice Critic · manual · D

### 4. Genuine tool switch has a cutover; a sourcing substitution doesn't
The tell: does the environment *narrate* the change (cutover date, decision doc,
announcement, visible before/after)? If records just exist in both tools with no
explanation, it's a sourcing substitution dressed as a migration. Manual.

### 5. Tone/vocabulary match stated seniority and role
A senior persona writes about tradeoffs, risk, unblocking — not line-level
implementation detail, not board strategy. Sample ≥10 long-form records/app.
Mismatch = data-bug. Manual (an LLM reviewer can score this).

### 9. Conversations read like conversations
Questions get answered; decisions have an owner and a date; there's
interruption, disagreement, someone going quiet. Generated threads drift toward
everyone agreeing pleasantly in turn. Manual.

---

## Redaction quality (6, 7, 10, 14, 15, 16) — Scrubber · auto/hybrid · R

### 6. No broken sentences from a dropped redaction token
A scrub removed a span mid-sentence. Detect: sentences ending on a preposition/
article/colon, doubled punctuation, `  ` double-spaces where a token was.
```python
re.search(r'\b(the|a|an|to|of|for|with|at|on)\s*[.!?]', text)   # dangling
re.search(r'\s{2,}[.,;:]', text)                                 # gap before punct
```
A visibly broken redaction is a bug **even when no PII leaked** (check 15).

### 7. Domain vocabulary not over-scrubbed
The scrubber ate believable domain terms along with PII → gibberish
substitutions. Detect with the morpheme inventory (≥2 morphemes = over-scrub).
See `overscrub_scan.py`. FP: single-morpheme pseudonyms, base64 noise.

### 10. Leftover placeholders
```python
PLACEHOLDERS = [r'\bTBD\b', r'Masked\s+Address', r'<[a-z_]+>', r'\bnull\b',
                r'example\.com', r'lorem ipsum', r'\bXXXX+\b', r'\[REDACTED\]',
                r'\bFIXME\b', r'\bTODO\b', r'\{\{.*?\}\}', r'test@test']
```
Any hit is a redaction-bug. FP: `null` as a legitimate data value in a JSON
column — check the surrounding context.

### 14. No real PII survives — text, filenames, metadata, images
The big one. Names (word-boundary, `realname_scan.py`), emails, phones, tax IDs,
bank codes, addresses (`pii_scan.py`), **and** filenames, file metadata
(`exiftool`), and text baked into images (OCR). Hybrid: script narrows, human
confirms via FP-gate.

### 15. A visibly broken redaction is still a bug
Even with no leak, a sentence that ends on "the." fails the demo. Overlaps #6;
file as `redaction-bug / major`, never waive.

### 16. No real outside company / vendor / product name
```sql
SELECT ... WHERE body LIKE '%<RealVendor>%';   -- from the config's forbidden list
```
Maintain a forbidden-real-vendor list in the config. FP: a vendor name that is
explicitly allowed by the brief (e.g. the real cloud provider the scenario runs
on). Word-boundary match to avoid substrings.

---

## Identity & substitution (8, 11) — Identity Auditor · hybrid · R

### 8. Replacement fits what it replaced (company ≠ person ≠ programme)
A substitution must preserve entity *category*. "Northgate Systems" (company)
must not become a person's name. The script catches obvious grammatical frames
("X said", "X joined"); read the rest.

### 11. Nonsense name substitutions in running text
Gibberish where a name should be. Overlaps the over-scrub detector but aimed at
the *name* slots specifically. FP: metonymy ("Northgate said…" is normal
English, not a broken substitution) — the check is tuned to over-report; read
each before filing.

**Plus the cross-app identity invariant** (not numbered but essential): one
human = one identity (display name, email, handle) across *every* app. Drift is
the most visible demo bug. And the **email-join de-id defeat**: if the email is a
stable key but the pseudonym differs per app, de-identification is defeatable —
`redaction-bug / blocker`. (See `DETECTION-PATTERNS.md` §5.)

---

## Capability & coverage (12, 13, 17, 18, 19) — UI Prober / Cartographer / Editor

### 12. In-app search actually filters — **GATE**, feature-gap
Search a term you *know* is present. If it returns everything/nothing regardless
of input, search is broken: a **feature-gap**, and every prior "found nothing"
is void. Do this *before* any search-based investigation. Manual (browser).

### 13. Every offered attachment opens and isn't empty — data-bug
Open every attachment; report what wouldn't open, opened empty, or was the wrong
content type. Manual (browser). Also scan attachment *payloads* for surviving
PII — they're frequently un-scrubbed (check 14 territory).

### 17. Every brief app is present with content, or its absence is accepted
```
set(brief.apps) - set(apps_with_records)   # missing apps
```
Missing + undocumented = data-bug. Missing + documented/accepted = fine.

### 18. Every claimed capability is backed by evidence in ≥1 app
For each capability keyword from the brief, find a record that demonstrates it.
Unbacked claim = data-bug (or feature-gap if the app structurally can't).

### 19. Missing app features are feature-gaps, not data-bugs — the bucketing gate
The discipline that underlies everything: *if the data were perfect, would this
still be broken?* Yes → feature-gap (owner: environment builder). No → data-bug
(owner: data generator). Getting this wrong sends findings to the wrong team.

---

## Coverage matrix

Track which checks ran against which apps, with the result. An honest matrix
(including "not checked, because…") is part of the deliverable — see
`check_coverage.py` and `REPORTING-STYLE.md`.

| | App A | App B | App C | … |
|---|---|---|---|---|
| 1 temporal | ✓ | ✓ | ✓ | |
| 14 PII | ✓ | ✓ | ⚠ partial | |
| 12 search | ✓ | n/a | ✗ not checked | |
