# Methodology — QA'ing a synthetic multi-app RL environment

Environment-agnostic. Works for any suite (dev tools, ops, sales, support)
because every check is about *internal coherence* and *redaction quality*, not
about any specific app.

---

## 0. Mental model

The environment is one invented company told through N apps. It is correct iff:

- **One timeline.** Every app respects a single "today" (`environment_today`)
  and a single start (`persona_start`). Nothing is created before the persona
  joined; nothing is dated after today except legitimately-future records
  (pricing calendars, goal targets, invoice due dates, opportunity close dates).
- **One cast.** A person has the same display name, email, and role in every
  app they appear in. Email joins across apps must resolve to the *same*
  pseudonym (if they don't, de-identification is defeatable by joining on email).
- **Resolvable references.** Cross-app mentions (a booking ID in an email, a
  deal in a deck, a report linked from chat) point at something that exists.
- **Clean redaction.** No surviving real PII (names, phones, tax IDs, bank
  codes); no scrub that turned text into gibberish; no substitution that is
  contextually absurd.
- **Claimed capabilities exist.** If the brief says the suite can do X, the app
  can actually do X. If it can't, that's a feature-gap, not a data bug.

---

## 1. Get the data out (cheapest first)

1. **Seed files baked into the image** — cheapest, most faithful.
2. **Database dump / live DB** — each app typically has its own SQLite/Postgres.
   For multi-GB live DBs, **do not copy** — query in place, read-only. See
   `IN-CONTAINER-QUERY.md`.
3. **App APIs** — when there's no DB access.
4. **UI scrape** — last resort, and the only way to catch UI-only behaviour.

Name export subfolders after the apps (`export/<app>/…`). The normalizer infers
the app from the export's own structure, so any suite works.

## 2. Bootstrap the config, then adjudicate it — **GATE**

`bootstrap_config.py` derives apps, date window, cast (with entity kinds),
email domains, cross-app vocab, and candidate capabilities. Everything uncertain
lands in `_confirm`.

Two values **must** be set by a human from the brief, or the whole run is void:

- **`persona_start` / `environment_today`** are inferred from the data's own min
  and max — so an out-of-window record silently *widens the window it was
  supposed to violate*. Set them from the brief.
- **Roster `kind`** left as `unknown` makes the category-mismatch check inert.

Why this is a gate: a config nobody reviewed measures the environment *against
itself*. It can only find internal contradictions, never a divergence from what
was promised.

## 3. Run the automated sweep

`check_temporal` (items 1–3), `check_references` (cross-app integrity),
`check_scrub` (6,7,10,14,15,16), `check_entities` (8,11), `check_coverage`
(17–19). Covers roughly half the checklist — everything mechanical. Writes
`REPORT.md`, `findings.csv`, `coverage-matrix.csv`.

**Two more gates here:**

- **Normalization fidelity.** If `created` dates didn't map, temporal findings
  are meaningless. `normalize.py` prints how many records lack a date — over a
  few percent, add the real field name to `FIELD_ALIASES` and re-run.
- **In-app search.** Search a term you *know* is present. If search doesn't
  filter, every "found nothing" so far is void — and broken search is itself a
  feature-gap.

## 4. Manual / LLM passes — go deep, app by app

Scripts can't judge tone, conversational realism, whether a substitution is
*contextually* absurd, or anything UI-only. Assign these to reviewer roles
(`references/agents.md`): Chronologist, Voice Critic, Scrubber, Identity
Auditor, UI Prober.

**Trace-by-trace beats app-by-app** for story coherence: pick threads that
should span apps (a feature, a meeting, an incident, a booking) and follow each
end to end. But for *redaction depth*, go **column by column** through each
app's DB — that's where surviving PII hides (see `DETECTION-PATTERNS.md`).

Fan out: for a dense app, spawn 4–5 narrow sub-agents each owning a slice
(snippets, subjects, attachments, body text, structured fields), each told to
use few tokens and return only confirmed hits.

## 5. FP-gate every candidate — **before it becomes a finding**

Synthetic corpora are adversarially full of near-misses. Never file a raw regex
hit. Each candidate goes through an adversarial verifier (`fp_gate_prompt.md`)
that returns `CONFIRMED` / `FALSE-POSITIVE` with a reason. Known traps:

- **Benign pseudonyms** — the substitution *is* the anonymized value; not a leak.
- **Legitimate future dates** — pricing calendars, goal targets, due/close dates.
- **Base64 / tracking noise** — e.g. Mandrill tracking blobs in `body_html` /
  `file_data` decode to strings that contain morpheme fragments; not leaks.
- **Substring collisions** — `shah` inside `Shahbaz`, `das` inside `Dash`. Use
  word boundaries.
- **App / code residue** — library names, enum values, template tokens.

## 6. Assemble, calibrate, deliver

Merge and dedupe (one root cause in six apps = one finding, six instances).
Severity tracks demo impact: noticeable in a five-minute walkthrough → blocker.
State coverage honestly, including gaps. Deliver per-app findings + a
consolidated tracking sheet (`QA-WORKFLOW-ROUNDS.md`).

## 7. Retest per fix round

When the dev pushes fixes, retest **app by app**, one app at a time. Validate
each resolved bug against the *live rebuilt* environment (confirm the build
actually changed — timestamps alone lie; verify a known marker delta). Add a new
per-round QA column; never touch the dev's columns. Full contract in
`QA-WORKFLOW-ROUNDS.md`.

---

## The three gates, in one place

These invalidate everything done before them. Check early.

1. **Config adjudication** — an unreviewed config only finds self-contradiction.
2. **Normalization fidelity** — unmapped dates make temporal findings noise.
3. **In-app search** — broken search voids every "found nothing".
