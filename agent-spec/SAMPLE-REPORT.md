# Sample report — fully worked, synthetic

A concrete, end-to-end example of the deliverables in the house style, using an
**invented** environment ("Acme Field-Ops suite") so nothing here is tied to a
real run. Use it as the shape to reproduce: a per-app findings doc, a cross-app
finding, the assembled report, and the matching tracking-sheet rows.

The environment (invented): a field-operations persona across 4 apps —
**MailApp**, **ChatApp**, **CRMApp**, **BIApp** — `persona_start = 2025-01-06`,
`environment_today = 2025-06-30`.

---

## Per-app findings doc — MailApp

```
# MailApp — findings

## Summary
4 findings: 1 data-bug, 3 redaction-bug. Headline: real names survive in
snippets and attachment payloads (blocker).

## Findings

### [MA1] Real names survive in message snippets and subjects
- Type / Severity: redaction-bug / blocker
- Path: MailApp → messages.snippet (412 distinct), messages.subject (28 distinct)
- Evidence: word-boundary match against the source roster. Sample snippet
  "...spoke to SXXXX about the Q2 plan..." (masked). Ruled out FP rule 2
  (substring) via boundary regex; LIKE prefilter 701 → 412 after recheck.
- Recommendation: re-run the scrubber over snippet/subject, not just body.

### [MA2] Real names + tax IDs in xlsx attachment payloads
- Type / Severity: redaction-bug / blocker
- Path: MailApp → attachments.file_data (xlsx), ~48% of 1,204 attachments
- Evidence: extracted xlsx, scanned cells: 193 distinct roster names, 57 distinct
  tax IDs (format ABXXX1234C). Payloads were not passed through the scrubber.
- Recommendation: route attachment payloads through the same scrub as body text.

### [MA3] Over-scrubbed domain vocabulary (gibberish substitutions)
- Type / Severity: redaction-bug / minor
- Path: MailApp → messages.body_text, ~1.4% of tokens
- Evidence: morpheme detector, ≥2 morphemes. Sample "nexmagwren" where a product
  name should be. Ruled out base64 (FP rule 3) and single-morpheme pseudonyms.

### [MA4] Two messages reference a later-created artifact
- Type / Severity: data-bug / major
- Path: MailApp → messages #8831, #9014 cite ReportApp doc created 3 days later
- Evidence: message sent_at 2025-04-02; referenced doc created_at 2025-04-05.

## Coverage
Checked: messages (snippet, subject, body_text, body_html), threads, attachments
(filenames + payloads), recipients; temporal on sent_at; cross-app refs.
Not checked (and why): image-baked text in inline images — no OCR this pass.
```

---

## Cross-app finding

```
### [XA1] Email-join de-identification defeat
- Type / Severity: redaction-bug / blocker
- Path: CRMApp.contacts.email ↔ BIApp.dataset rows ↔ MailApp.recipients
- Evidence: contact alice.okonkwo@acme-field.example resolves to pseudonym
  "A. Okonkwo" in MailApp/ChatApp but "Pat Rivera" in CRMApp and BIApp. The email
  is a stable join key, so the two pseudonyms re-identify the same person.
- Instances: 1 root cause, 2 apps affected (CRMApp, BIApp).
- Recommendation: make the pseudonym map keyed on the stable identity, shared
  across all apps.
```

---

## Assembled report (excerpt)

```
# Acme Field-Ops suite — QA report

## Coverage statement
4 of 4 brief apps covered. Checklist items 1–18 run; item 12 (in-app search)
verified working on MailApp/ChatApp, not applicable to BIApp. Not checked: OCR of
image-baked text; permissions model. Depth: column-by-column redaction on all 4
apps; trace-by-trace on 3 threads (onboarding, an incident, a renewal).

## Rollup
| App     | data-bug | redaction-bug | feature-gap | blocker | major | minor |
|---------|---------:|--------------:|------------:|--------:|------:|------:|
| MailApp |        1 |             3 |           0 |       2 |     1 |     1 |
| ChatApp |        2 |             1 |           1 |       0 |     2 |     2 |
| CRMApp  |        1 |             2 |           0 |       1 |     1 |     1 |
| BIApp   |        0 |             2 |           0 |       1 |     1 |     0 |
| Cross   |        0 |             1 |           0 |       1 |     0 |     0 |
| **Tot** |      **4** |          **9** |         **1** |   **5** | **5** | **4** |

## Top escalations (fix first)
1. [MA2] tax IDs + names in attachment payloads — blocker, unscrubbed corpus.
2. [XA1] email-join de-id defeat — blocker, defeats anonymization.
3. [MA1] names in snippets/subjects — blocker, visible on the inbox list.

## Findings by app
(blockers first, then major, then minor — full per-app docs attached)
```

---

## Matching tracking-sheet rows (MailApp tab)

| Bug Summary | Path | Reference | Type | Reported by | Assigned to | Dev Status | Dev Comments | QA Status | QA comments | QA Status R2 |
|---|---|---|---|---|---|---|---|---|---|---|
| [MA1] Real names in snippets/subjects | MailApp → messages.snippet,subject | 412+28 distinct; masked sample | redaction-bug | *QA* | *Dev* | *(dev writes)* | *(dev writes)* | Open (new finding) | 412 snippet / 28 subject, word-boundary | *(set next round)* |
| [MA2] Names+tax IDs in attachment payloads | MailApp → attachments.file_data | ~48% of 1,204 xlsx | redaction-bug | *QA* | *Dev* | | | Open (new finding) | 193 names / 57 tax IDs in payloads | |
| [MA3] Over-scrub gibberish | MailApp → messages.body_text | ~1.4% tokens | redaction-bug | *QA* | *Dev* | | | Open (new finding) | ≥2-morpheme, base64 ruled out | |
| [MA4] References later-created artifact | MailApp → messages #8831,#9014 | sent 04-02, doc 04-05 | data-bug | *QA* | *Dev* | | | Open (new finding) | temporal cross-ref | |

Round-2 comment style (after a fix, appended to QA comments, verdict from dropdown):

```
R2: re-ran realname_scan on rebuilt stack — snippets 412→0, subjects 28→0,
attachment payloads still ~44%. Verdict: Partially Fixed.
```

---

Everything above is invented for illustration. The point is the *shape*: id-tagged
findings, one bucket each, quantified evidence with masked samples and ruled-out
FP rules, one root cause for cross-app issues, an honest coverage statement, and
a top-escalations list.
