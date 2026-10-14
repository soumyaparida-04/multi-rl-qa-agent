# Detection patterns — the heuristics that actually find leaks

This is the core IP of the QA process. These are the patterns that separate
genuine redaction/data bugs from the enormous volume of near-misses a synthetic
corpus throws off. Build every one of these into the QA agent, each paired with
its false-positive carve-out.

> Golden rule: **a raw regex hit is a *candidate*, never a finding.** Everything
> here feeds the FP-gate (`scripts/fp_gate_prompt.md`) before it's filed.

---

## 1. Over-scrub detection (gibberish substitutions) → redaction-bug

**Symptom:** the scrubber replaced a real token with a mash of morphemes that
reads as nonsense — `pathbright`, `hydracryo`, `nexmag wren`. A human reading
the app sees obvious garbage.

**Method — morpheme inventory.** Maintain a list of the substitution
generator's building-block morphemes. A token containing **≥ 2** of them is
almost certainly a machine-mashed pseudonym:

```
path, bright, hydra, cryo, nex, mag, wren, kep, pol, gen, zen,
(extend by eyeballing the actual generator's vocabulary in your env)
```

```python
MORPHS = ["path","bright","hydra","cryo","nex","mag","wren","kep","pol","gen","zen"]
def overscrub_score(tok: str) -> int:
    t = tok.lower()
    return sum(t.count(m) for m in MORPHS)
# flag when score >= 2 AND token is not a known-benign pseudonym
```

**FP carve-outs (critical):**
- A *single* morpheme is just a normal pseudonym syllable — not a leak.
- **Base64 noise:** morpheme fragments appear inside base64 blobs (email
  tracking pixels, `file_data`, `body_html`). Decode or length/charset-filter
  first. Example: the string `zolo` showing up thousands of times inside
  `attachments.file_data` was Mandrill tracking base64, **not** a leak.
- App/library/enum residue that legitimately contains a syllable.

See `scripts/overscrub_scan.py`.

---

## 2. Surviving real-name detection → redaction-bug

**Symptom:** a real person's name survived the scrub in a snippet, subject,
filename, or structured field.

**Method — word-boundary match against a real-name list.** The trap is
substrings: naive `LIKE '%shah%'` matches `Shahbaz`, `%das%` matches `Dash`.
Always anchor on word boundaries:

```python
import re
# NOT \b — many corpora mix scripts/punctuation; use an explicit boundary class
def hits(text, surname):
    return re.findall(rf'(^|[^A-Za-z]){re.escape(surname)}([^A-Za-z]|$)', text)
```

In SQL, pre-filter cheaply with `LIKE` then re-check in Python with the regex —
never trust the `LIKE` count. In one app a loose `LIKE` reported 487 hits;
word-boundary re-check reduced it to 66 real ones.

**Where to look (column by column, not just body text):**
- message/thread **snippets** and **subjects** (highest yield — often scrubbed
  less aggressively than bodies)
- **attachment filenames** and **attachment payloads** (xlsx/csv inside
  attachments are frequently un-scrubbed — a whole second corpus)
- recipient/display-name fields, user tables
- structured BI dataset rows (`rows_json` etc.)

**FP carve-outs:** benign pseudonyms that happen to collide with a real surname;
the persona's *own* name if it's meant to be present. Keep the real-name list
curated (actual regional surnames), not a dictionary.

See `scripts/realname_scan.py`.

---

## 3. Structured-PII sweep → redaction-bug

Region-specific identifiers survive scrubbing constantly because they don't look
like names. For an India-flavoured corpus:

| PII | Pattern | Note |
|---|---|---|
| Phone (10-digit) | `(?<!\d)[6-9]\d{9}(?!\d)` | **Fakes often end in `0000`** — a number *not* ending 0000 is a stronger leak signal. |
| PAN | `[A-Z]{5}\d{4}[A-Z]` | tax ID |
| GSTIN | `\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]` | tax ID; these survive in bulk inside serialized BI dataset columns |
| IFSC | `[A-Z]{4}0[A-Z0-9]{6}` | bank branch code; `HDFC0…` style |

Count **distinct** values and locate by column. A high count in one column =
one systemic finding, not thousands of findings. Adapt the table to the
environment's locale:

| Locale | Identifiers to add |
|---|---|
| US | SSN `\d{3}-\d{2}-\d{4}`, EIN `\d{2}-\d{7}`, routing `\b\d{9}\b`, phone `\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}` |
| EU | IBAN `[A-Z]{2}\d{2}[A-Z0-9]{11,30}`, VAT `[A-Z]{2}\d{8,12}` |
| UK | NINO `[A-Z]{2}\d{6}[A-Z]`, sort code `\d{2}-\d{2}-\d{2}` |
| Generic | email `[\w.+-]+@[\w-]+\.[\w.-]+`, credit card (Luhn), IPv4, MAC |

See `scripts/pii_scan.py`.

---

## 3b. Residue & placeholder sweep → redaction-bug

Beyond names and IDs, scrubbers leave two other classes of residue:

**Leftover placeholders / template tokens** (check 10):
```python
PLACEHOLDERS = [r'\bTBD\b', r'Masked\s+Address', r'<[a-z_]+>', r'\bnull\b',
                r'example\.com', r'lorem ipsum', r'\bX{4,}\b', r'\[REDACTED\]',
                r'\{\{.*?\}\}', r'Click to add', r'FIXME', r'\bTODO\b']
```

**Infrastructure / source residue** — URLs and paths that leak the real source
environment: `drive.google.com`, `docs.google.com`, `*.sharepoint.com`, internal
file paths, S3 URLs, real corporate domains. Often found in spreadsheet cells,
BI connection strings, and mail bodies. FP: a URL the brief explicitly allows.

**Real outside vendor/company names** (check 16): match against a forbidden-list
in the config, word-boundary. FP: vendors the brief says are allowed.

---

## 3c. Metadata & non-text channels → redaction-bug

PII hides outside the text columns, where SQL can't see it:
- **File metadata** — `exiftool` over every attachment (author, company,
  last-modified-by, GPS).
- **Image-baked text** — OCR screenshots/inline images for names and numbers.
- **Spreadsheet named ranges / defined names** — identities leak in cell *names*.
- **Document speaker notes & embedded chart data** — scrubbed less than body text.

---

## 3d. Broken-redaction / over-scrub text damage → redaction-bug

A scrub that dropped a span mid-sentence is a bug even when nothing leaked:
```python
re.search(r'\b(the|a|an|to|of|for|with|at|on)\s*[.!?]', text)  # dangling word
re.search(r'\s{2,}[.,;:]', text)                               # gap before punct
re.search(r'\b(\w+)\s+\1\b', text)                             # doubled word
```

---

## 4. Temporal integrity → data-bug

**After-today violations:** records created after `environment_today`.

```sql
SELECT count(*) FROM t WHERE created_at > :environment_today;
```

**Before-join violations:** records created before `persona_start`.

**FP carve-outs — legitimate future dates (do NOT flag):**
- pricing / rate calendars (room ADR, airline fares, SKU prices)
- scorecard / OKR **goal target** dates
- CRM **opportunity close** dates
- invoice / PO **due** dates
- scheduled meetings and future calendar events
- data-migration / seed `goals` tables

The way to tell: a *creation/modification* timestamp after today is a violation;
a *target/scheduled/due* field after today is content. Separate the two by field
semantics, not by value.

---

## 5. Cross-app referential & identity integrity → data-bug / redaction-bug

**Email-join de-id defeat (redaction-bug, high severity):** if person P is
pseudonymised differently across apps but the *email* is the same (or vice
versa), an attacker joins on the stable key and re-identifies. Check: for each
email, is the display-name pseudonym consistent across every app? For each
person, is the email consistent? (Seen in a production run as a cross-app finding —
Salesforce/Power BI initially carried a different pseudonym than the other apps
for the same email; fixed in round 2.)

**Dangling references (data-bug):** booking IDs, deal IDs, report links,
ticket numbers mentioned in one app that don't exist in the owning app.

---

## 6. Capability / feature-gap detection → feature-gap

For every capability the brief claims, prove the app can do it:
- the table/entity exists and is populated (e.g. a "calendar" capability with an
  empty calendar table = gap)
- in-app search actually filters
- links/exports/attachments actually resolve

If the data were perfect and it'd still be broken → feature-gap, owner is the
environment builder.

---

## Quick reference — the FP traps that cost the most time

| Looks like | Actually | Guard |
|---|---|---|
| name substring in a pseudonym | collision | word-boundary regex |
| morphemes in `file_data`/`body_html` | base64 tracking noise | decode / charset filter |
| date after today | legit future content | classify by field semantics |
| thousands of `LIKE` hits | few real ones | re-check in Python, count distinct |
| gibberish token | normal 1-morpheme pseudonym | require ≥2 morphemes |
| different pseudonym per app | sometimes intended per-app aliasing | confirm the email key is shared first |
