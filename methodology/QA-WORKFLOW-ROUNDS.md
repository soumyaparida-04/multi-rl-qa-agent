# The tracking sheet & the per-round retest contract

How findings are tracked across the QA ↔ dev loop, and the rules that keep the
sheet trustworthy when multiple people edit it over multiple fix rounds.

---

## The sheet shape

One workbook. **One tab per app**, plus a `Summary` tab and a `Cross-app` tab.
Each finding is one row. Original column layout:

| Col | Header | Owner | Notes |
|---|---|---|---|
| A | Bug Summary | QA | prefix with a stable id tag, e.g. `[OL2] …` |
| B | Path | QA | where it is (app → table.column, or UI path) |
| C | Reference | QA | evidence / sample |
| D | Type | QA | **data-bug / redaction-bug / feature-gap** |
| E | Reported by | QA | reviewer name |
| F | Assigned to | QA | dev name |
| G | **Dev Status** | **DEV** | QA never writes here |
| H | **Dev Comments** | **DEV** | QA never writes here |
| I | QA Status | QA | round-1 verdict (dropdown) |
| J | QA comments | QA | round-1 evidence |
| K | QA Status R2 | QA | round-2 verdict (dropdown) — **added at the end** |
| … | QA Status R3, R4 … | QA | each new round = one new column at the end |

**Hard rule: QA only ever writes its own columns (D–F at intake; I, J, and the
per-round K, L… columns). QA never touches Dev Status / Dev Comments.** This is
the rule that got violated once (a silent tab-switch wrote app A's values onto
app B's tab) — see the safe-write guard below.

## The QA Status vocabulary (dropdown, every round column)

Use a fixed 6-value list as an Excel data-validation dropdown so verdicts stay
comparable across rounds:

```
Verified
Mostly Fixed
Partially Fixed
Reopened
Not a Bug (by design)
Open (new finding)
```

Mapping free-text → vocabulary (for normalizing older rows):

- starts with "open" → **Open (new finding)**
- "reopen" → **Reopened**
- "verified" / "fixed & verified" → **Verified**
- "mostly" → **Mostly Fixed**
- "partial" → **Partially Fixed**
- "closed" / "by design" / "not a bug" / "accepted" → **Not a Bug (by design)**

## The per-round retest loop

1. **Confirm the build is live** (marker delta, not timestamp — see
   `IN-CONTAINER-QUERY.md`). Don't start until a known marker moved.
2. **Add one new column at the end** for this round (`QA Status R<n>`), with the
   same dropdown. Never overwrite a prior round's column — history is the point.
3. **Go app by app, one app at a time.** For each finding:
   - re-run the detector against the *rebuilt* env
   - set the new round's QA Status from the 6-value list
   - append a `R<n>: <evidence>` note to QA comments
   - **leave every already-solved thing and every Dev column untouched**
4. **Add new findings** discovered during retest as new rows (Status =
   `Open (new finding)`).
5. **Update the Summary tab** with a per-round rollup (per-app counts by status).

## Safe-write guard (learned the hard way)

When writing per-tab with openpyxl, a wrong active-sheet reference silently
writes onto the wrong tab. Assert the target before every write:

```python
ws = wb["MS Excel"]
assert ws.title == expected_tab, f"wrong tab: {ws.title} != {expected_tab}"
# only write within QA columns
assert col_letter in QA_WRITABLE_COLS, f"refusing to write dev col {col_letter}"
ws[f"{col_letter}{row}"] = value
```

Keep `QA_WRITABLE_COLS = {"D","E","F","I","J","K",...}` — the Dev columns `G`/`H`
are *not* in it, so an accidental write refuses instead of corrupting dev data.

See `scripts/sheet_update.py` for the openpyxl helpers (dropdown creation,
adding a round column, finding a row by its `[id]` tag, safe write).

---

## Why the discipline matters

The sheet is the shared contract between QA and dev across many rounds. If QA
overwrites dev status, or clobbers a prior round, trust is gone and the loop
breaks. Append-only per round, strict column ownership, and a verdict dropdown
are what let the two sides iterate dozens of findings without stepping on each
other.
