# App-type playbooks — what to check, by category of app

The generic checklist applies to every app, but each *category* of app has its
own high-yield spots where bugs hide. These playbooks are app-agnostic within a
category: a "mail app" is a mail app whether it's Outlook, Gmail, or Superhuman.
Map each app in your environment to a category and run the matching playbook on
top of the 19 checks.

For every app, first identify: its database tables, its primary entities, its
text columns (where PII hides), its timestamp columns (temporal checks), and its
cross-app keys (email, IDs, links).

---

## Mail / messaging (Outlook, Gmail, …)

**Entities:** messages, threads, recipients, attachments, folders.
**Highest-yield leaks:** `snippet` and `subject` columns — scrubbed *less*
aggressively than bodies. Then **attachment payloads** (xlsx/csv/pdf inside
attachments are a whole second, usually un-scrubbed, corpus).

Deep checks:
- Real names in `messages.snippet`, `threads.snippet`, `*.subject`,
  `attachments.filename`, `message_recipients.recipient_name`. Word-boundary.
- Attachment payloads: extract and scan every xlsx/csv for PII.
- Structured PII in bodies: phones (fakes often end `0000`), tax IDs, bank codes.
- `conversation_index` / threading set and consistent (a threading field that's
  null everywhere = feature-gap in the thread view).
- Base64 noise FP: tracking pixels in `body_html` / `file_data` decode to junk
  containing morpheme fragments — not leaks.
- Duplicate attachment filenames across unrelated messages (sourcing artifact).
- Temporal: `sent_at` within window; no message references a later artifact.

## Chat / collaboration (Teams, Slack, …)

**Entities:** channels, messages, members, reactions, files.
**Deep checks:**
- Register realism: chat is clipped/lowercase; uniform formal register = finding.
- Conversational realism (#9): questions answered, decisions owned, someone goes
  quiet. Generated threads over-agree.
- Cross-app references resolve: a message citing a ticket/booking/deal → it
  exists in the owning app.
- @-mentions map to real roster identities, same pseudonym as elsewhere.
- Over-scrub in short messages (gibberish is more visible in terse text).

## CRM (Salesforce, HubSpot, …)

**Entities:** accounts, contacts, opportunities, leads, activities, cases.
**Deep checks:**
- Contact identity consistency with every other app (email = stable key).
- **email-join de-id defeat**: CRM often carries a *different* pseudonym than the
  rest of the suite for the same email → blocker.
- Opportunity `close_date` in the future is *content*, not a temporal violation.
- Stage/amount/probability internally consistent (closed-won with 10% prob = D).
- PII in `description` / notes / `case` text (reserved word — quote `"case"`).
- Reserved-word tables need quoting in SQL.

## BI / analytics (Power BI, Tableau, Looker, …)

**Entities:** datasets, reports, dashboards, rows (often serialized JSON).
**Highest-yield leaks:** serialized row blobs (`rows_json`, `dataset_table_data`)
— real names and **tax IDs survive here in bulk** because scrubbers skip opaque
JSON columns.
**Deep checks:**
- Parse every serialized dataset column and scan the *values*, not just the blob.
- Structured PII at scale (count distinct — one column with 8k tax IDs is ONE
  systemic finding).
- Measure/aggregate sanity: totals that don't match their rows (data-bug).
- Gateway/connection `name` fields leaking real infra or people.
- Goal/target dates in the future = content.

## Spreadsheet (Excel, Sheets, …)

**Entities:** workbooks, sheets, cells, named ranges, formulas.
**Deep checks:**
- PII in cell values (tax IDs, phones) and in **named ranges / defined names**
  (cell *names* leak identities people forget to scrub).
- Residue in cells: Google-Drive URLs, `@domain` emails, file paths.
- Formula references that point at deleted/renamed sheets (data-bug).
- Hidden sheets/columns with un-scrubbed source data.

## PMS / booking / ops (Oracle PMS, Booking.com, order systems, …)

**Entities:** reservations/orders, guests/customers, rooms/SKUs, rates, invoices.
**Deep checks:**
- Guest/customer identity + PII (phone, email, ID doc numbers).
- Reservation IDs referenced from mail/chat/CRM actually exist.
- Date sanity: check-in < check-out; no reservation created after its own stay
  in the past; **future reservations are legitimate** (don't flag).
- Rate/price calendars extend into the future legitimately (content).
- Invoice `due_date` future = content; invoice `issued_at` future = violation.
- Status machine sanity (checked-out before checked-in = data-bug).

## Slides / docs (PowerPoint, Google Slides, Docs, …)

**Entities:** decks/documents, slides/sections, shapes, speaker notes.
**Highest-yield leaks:** **speaker notes** and chart *data* embedded in slides —
scrubbed less than visible body text.
**Deep checks:**
- PII and real-vendor names in notes, chart data, and image-baked text (OCR).
- Figures in a deck match the source app they claim to summarize (cross-app).
- Template/placeholder residue (`Click to add text`, `{{company}}`).

## Pricing / rate tools (Pricelabs, revenue optimizers, …)

**Entities:** rate rules, calendars, competitors, recommendations.
**Deep checks:**
- Future-dated rate calendars are the *product* — never flag as temporal
  violations. This app type generates the most legitimate-future-date FPs.
- Competitor names: are they fictional, or real businesses left unscrubbed (#16)?
- Recommendation logic internally consistent with the inputs (data-bug).

---

## How to use these in the agent

1. Detect each app's category from its tables/entities (or the brief).
2. Run the 19 checks + the matching category playbook.
3. The playbook tells the fan-out sub-agents *which columns to prioritize* — that
   priority list is what makes a 10 GB app tractable (see `ENGAGEMENT-PLAYBOOK.md`
   "fire 4-5 agents").
