"""
Excel in, Excel out.

For every sheet that has a customer column (header starting with "Customer"
or "Consignee", searched in the first 60 rows because real manifests often
carry a pivot table above the data) a "Standard Customer" column is inserted
right after it. Every row and sheet is kept; a "Customer Summary" sheet is
added. The original file is never modified.
"""

from __future__ import annotations

import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass

import openpyxl

from . import rules as R
from .cleaning import basic
from .memory import standardize

HEADER_SCAN_ROWS = 60
OUT_COL = "Standard Customer"


@dataclass
class Result:
    output: str
    cells: int
    spellings: int
    standard_names: int
    new_spellings: list
    seconds: float


def find_header(rows: list, wanted: str | None = None):
    """(header row index, customer column index) or (None, None)."""
    for i, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        for j, c in enumerate(row):
            if not isinstance(c, str):
                continue
            h = c.strip().upper()
            if wanted:
                if h == wanted.strip().upper():
                    return i, j
            elif h.startswith("CUSTOMER") or h.startswith("CONSIGNEE"):
                return i, j
    return None, None


def read_workbook(path: str) -> list:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)]) for ws in wb.worksheets]
    wb.close()
    return sheets


def clean_workbook(path: str, master: dict, column: str | None = None,
                   output: str | None = None, log=print) -> Result:
    t0 = time.time()
    sheets = read_workbook(path)

    layout, raw_counts = {}, Counter()
    for title, rows in sheets:
        hi, ci = find_header(rows, column)
        if hi is None:
            log(f"  sheet '{title}': no customer column - copied unchanged")
            continue
        layout[title] = (hi, ci)
        for row in rows[hi + 1:]:
            if ci < len(row) and row[ci] is not None and str(row[ci]).strip():
                raw_counts[basic(row[ci])] += 1
    if not layout:
        raise ValueError("no sheet has a column starting with 'Customer' or 'Consignee' "
                         "(use --column to give the header)")

    new_raw = standardize(raw_counts, master, count_known=False)
    std_of = {r: master[r]["standard_name"] for r in raw_counts}

    out = output or os.path.splitext(path)[0] + "_clean.xlsx"
    wb = openpyxl.Workbook(write_only=True)
    summary = defaultdict(lambda: [0, set()])
    for title, rows in sheets:
        ws = wb.create_sheet(title[:31])
        if title not in layout:
            for row in rows:
                ws.append(row)
            continue
        hi, ci = layout[title]
        ws.freeze_panes = f"A{hi + 2}"
        for i, row in enumerate(rows):
            row = row + [None] * (ci + 1 - len(row))
            extra = None
            if i == hi:
                extra = OUT_COL
            elif i > hi and row[ci] is not None and str(row[ci]).strip():
                b = basic(row[ci])
                extra = std_of.get(b) or R.UNIDENTIFIED
                summary[extra][0] += 1
                summary[extra][1].add(b)
            # source formulas would point at shifted cells: keep values only
            vals = [None if isinstance(v, str) and v.startswith("=") else v for v in row]
            ws.append(vals[:ci + 1] + [extra] + vals[ci + 1:])

    ws = wb.create_sheet("Customer Summary")
    ws.freeze_panes = "A2"
    ws.append(["Standard Customer", "Rows", "Different spellings"])
    for name, (n, spell) in sorted(summary.items(), key=lambda x: (-x[1][0], x[0])):
        ws.append([name, n, len(spell)])
    try:
        wb.save(out)
    except PermissionError:
        raise PermissionError(f"cannot write {out} - is it open in Excel?") from None

    return Result(out, sum(raw_counts.values()), len(raw_counts), len(summary),
                  new_raw, time.time() - t0)
