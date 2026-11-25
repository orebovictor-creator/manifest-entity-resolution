"""
Command line:

    python -m manifest_er clean  FILE.xlsx [FILE2.xlsx ...]   write FILE_clean.xlsx
    python -m manifest_er clean                               pick files in a dialog
    python -m manifest_er explain "M/S Acme Trading Ltd P.O Box 1 Kampala"
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings

from .cleaning import basic, clean_name
from .excel import clean_workbook
from .matching import match_key
from .memory import load_master, save_master, write_review

warnings.filterwarnings("ignore", module="openpyxl")


def _pick_files() -> list:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return []
    root = tk.Tk()
    root.withdraw()
    files = filedialog.askopenfilenames(title="Choose Excel file(s) to clean",
                                        filetypes=[("Excel files", "*.xlsx *.xlsm")])
    root.destroy()
    return list(files)


def cmd_clean(args) -> int:
    files = args.files or _pick_files()
    if not files:
        print("No file chosen.")
        return 1
    print(f"Loading memory: {args.master}")
    master = load_master(args.master)
    new_all, failed = [], 0
    for f in files:
        f = os.path.abspath(f.strip('"'))
        if f.lower().endswith("_clean.xlsx"):
            print(f"Skipping {os.path.basename(f)} (already cleaned)")
            continue
        print(f"\n{os.path.basename(f)}")
        try:
            r = clean_workbook(f, master, args.column)
        except Exception as e:                       # keep going with the next file
            print(f"  ERROR: {e}")
            failed += 1
            continue
        new_all += r.new_spellings
        print(f"  {r.cells:,} customer cells | {r.spellings:,} spellings -> "
              f"{r.standard_names:,} standard names | {len(r.new_spellings):,} new "
              f"| {r.seconds:.1f}s")
        print(f"  saved {r.output}")
    if new_all and not args.no_learn:
        save_master(master, args.master)
        review = os.path.join(os.path.dirname(os.path.abspath(args.master)),
                              "review_new_names.csv")
        write_review(sorted(set(new_all)), master, review)
        print(f"\n{len(set(new_all)):,} new spellings remembered -> {review}")
    return 1 if failed else 0


def cmd_explain(args) -> int:
    raw = " ".join(args.name)
    c = clean_name(raw)
    print(f"raw      : {raw}")
    print(f"basic    : {basic(raw)}")
    print(f"cleaned  : {c or '(no usable name)'}")
    if c:
        print(f"match key: {match_key(c)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="manifest_er",
                                 description="Standardize customer names in Excel files.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("clean", help="add a 'Standard Customer' column to Excel files")
    c.add_argument("files", nargs="*")
    c.add_argument("--column", help="header of the name column if not 'Customer...'")
    c.add_argument("--master", default="customer_master.csv",
                   help="memory file (default: ./customer_master.csv)")
    c.add_argument("--no-learn", action="store_true",
                   help="do not save new spellings to the memory file")
    c.set_defaults(func=cmd_clean)

    e = sub.add_parser("explain", help="show how one raw value is cleaned")
    e.add_argument("name", nargs="+")
    e.set_defaults(func=cmd_explain)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
