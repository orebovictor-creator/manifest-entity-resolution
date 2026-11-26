import os
import sys

import openpyxl
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from manifest_er.excel import clean_workbook  # noqa: E402


def _manifest(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Imports"
    ws.append(["Row Labels", "Sum of TEUs"])          # pivot block above the header
    ws.append(["UG", 10])
    ws.append([])
    ws.append(["Bill Of Lading", "Dest.", "Customer:", "TEUs"])
    for raw in ["TWIGA AUTO SPARES LTD", "Twiga Auto Spares Limited P.O BOX 1 KAMPALA",
                "TO ORDER", "PETER MUSISI", "MUSISI PETER"]:
        ws.append(["BL1", "UG", raw, 1])
    wb.create_sheet("Notes").append(["no customer column here"])
    wb.save(path)


def test_excel_round_trip(tmp_path):
    src = tmp_path / "manifest.xlsx"
    _manifest(src)
    res = clean_workbook(str(src), master={}, log=lambda *_: None)

    wb = openpyxl.load_workbook(res.output)
    assert wb.sheetnames == ["Imports", "Notes", "Customer Summary"]
    rows = list(wb["Imports"].values)
    assert rows[3] == ("Bill Of Lading", "Dest.", "Customer:", "Standard Customer", "TEUs")
    std = [r[3] for r in rows[4:]]
    assert std[0] == std[1] == "TWIGA AUTO SPARES LTD"
    assert std[2] == "UNIDENTIFIED (TO ORDER)"
    assert std[3] == std[4]
    assert rows[4][4] == 1                            # columns after the insert are shifted
    assert list(wb["Notes"].values) == [("no customer column here",)]
    assert res.cells == 5 and res.standard_names == 3


def test_benchmark_quality_does_not_regress():
    """Guard rail for future rule changes: the synthetic benchmark must stay high."""
    import evaluate
    truth = os.path.join(ROOT, "data", "ground_truth.csv")
    raws, true = evaluate.load_truth(truth)
    p, r, f = evaluate.bcubed(evaluate.this_tool(raws), true)
    assert p >= 0.98 and r >= 0.95 and f >= 0.97


def _sheet(path, rows):
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(path)


def test_header_skips_title_rows_and_code_columns(tmp_path):
    from manifest_er.excel import find_header
    rows = [["Customer manifest June 2024"], [],
            ["BL", "Customer Code", "Customer Name", "TEUs"],
            ["BL1", "C001", "ACME TRADING LTD", 1]]
    assert find_header(rows) == (2, 2)


def test_failed_file_is_not_remembered(tmp_path):
    src = tmp_path / "m.xlsx"
    _sheet(src, [["BL", "Customer:"], ["BL1", "ACME TRADING LTD"]])
    blocked = tmp_path / "out_is_a_folder"
    blocked.mkdir()
    master = {}
    try:
        clean_workbook(str(src), master, output=str(blocked), log=lambda *_: None)
    except Exception:
        pass
    else:
        raise AssertionError("saving onto a folder should fail")
    assert master == {}          # its spellings stay new, so they will be reviewed


def test_known_spellings_are_counted(tmp_path):
    src = tmp_path / "m.xlsx"
    _sheet(src, [["BL", "Customer:"]] + [["BL1", "ACME TRADING LTD"]] * 3)
    master = {}
    clean_workbook(str(src), master, log=lambda *_: None)
    clean_workbook(str(src), master, log=lambda *_: None)
    assert int(master["ACME TRADING LTD"]["occurrences"]) == 6
