#!/usr/bin/env python3
"""
openpyxl helpers for the QA tracking sheet.

Enforces the column-ownership contract:
  * QA writes ONLY its own columns (Type, Reported/Assigned, QA Status/comments,
    per-round QA Status columns).
  * QA NEVER writes Dev Status (G) / Dev Comments (H).
  * Each new fix round adds ONE new column at the end; prior rounds are never
    overwritten.
  * Every write asserts the target tab, so a stray active-sheet reference can't
    silently corrupt another app's tab (this bug happened once -- guard added).

See methodology/QA-WORKFLOW-ROUNDS.md for the full contract.
"""
import re
import openpyxl
from openpyxl.worksheet.datavalidation import DataValidation

QA_VOCAB = [
    "Verified", "Mostly Fixed", "Partially Fixed",
    "Reopened", "Not a Bug (by design)", "Open (new finding)",
]
DV_FORMULA = '"' + ",".join(QA_VOCAB) + '"'

# Dev columns are intentionally NOT in the writable set.
DEV_COLS = {"G", "H"}


def add_status_dropdown(ws, col_letter, max_row=None):
    """Attach the 6-value validation to a whole QA-status column."""
    assert col_letter not in DEV_COLS, f"refusing dropdown on dev col {col_letter}"
    dv = DataValidation(type="list", formula1=DV_FORMULA, allow_blank=True)
    ws.add_data_validation(dv)
    max_row = max_row or ws.max_row
    dv.add(f"{col_letter}2:{col_letter}{max_row}")


def next_round_column(ws, header_row=1):
    """Append one new 'QA Status R<n>' column at the end; return its letter."""
    headers = [c.value for c in ws[header_row]]
    existing = [h for h in headers if isinstance(h, str) and h.startswith("QA Status R")]
    n = 1 + max([int(re.search(r"R(\d+)", h).group(1)) for h in existing], default=1)
    col_idx = len(headers) + 1
    col_letter = openpyxl.utils.get_column_letter(col_idx)
    ws.cell(row=header_row, column=col_idx, value=f"QA Status R{n}")
    add_status_dropdown(ws, col_letter)
    return col_letter, n


def find_row_by_id(ws, finding_id, summary_col="A"):
    """Row whose Bug Summary starts with [finding_id]. Returns row index or None."""
    for r in range(2, ws.max_row + 1):
        v = ws[f"{summary_col}{r}"].value or ""
        m = re.match(r"\[(\w+)\]", str(v))
        if m and m.group(1) == finding_id:
            return r
    return None


def safe_write(ws, expected_tab, col_letter, row, value):
    """Write a QA cell with two guards: right tab, QA-owned column only."""
    assert ws.title == expected_tab, f"wrong tab: {ws.title} != {expected_tab}"
    assert col_letter not in DEV_COLS, f"refusing to write dev col {col_letter}"
    ws[f"{col_letter}{row}"] = value


def append_comment(ws, expected_tab, comment_col, row, note):
    """Append a '\\nR<n>: ...' note without clobbering prior comments."""
    assert ws.title == expected_tab
    assert comment_col not in DEV_COLS
    cur = ws[f"{comment_col}{row}"].value or ""
    ws[f"{comment_col}{row}"] = (cur + ("\n" if cur else "") + note).strip()


# --- normalize free-text verdicts into the fixed vocabulary -------------------
def normalize_status(text: str) -> str:
    t = (text or "").strip().lower()
    if t.startswith("open"):
        return "Open (new finding)"
    if "reopen" in t:
        return "Reopened"
    if "verified" in t:
        return "Verified"
    if "mostly" in t:
        return "Mostly Fixed"
    if "partial" in t:
        return "Partially Fixed"
    if any(k in t for k in ("closed", "by design", "not a bug", "accepted")):
        return "Not a Bug (by design)"
    return text  # leave as-is if unrecognized


if __name__ == "__main__":
    import sys
    wb = openpyxl.load_workbook(sys.argv[1])
    for ws in wb.worksheets:
        if ws.title in ("Summary",):
            continue
        col, n = next_round_column(ws)
        print(f"{ws.title}: added QA Status R{n} at column {col}")
    wb.save(sys.argv[1])
    print("saved")
