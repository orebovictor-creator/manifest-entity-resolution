"""
Stage 3 - memory: keep every decision so a customer keeps the SAME standard
name month after month, and let a human override any decision.

customer_master.csv  (one row per raw spelling ever seen)
    standard_name, raw_name, cleaned_name, match_score, occurrences, first_seen, manual

Edit `standard_name` by hand and set `manual` to "yes": the edit is kept
forever and new spellings of that customer will join your name.
"""

from __future__ import annotations

import csv
import os
from collections import Counter
from datetime import date
from typing import Iterable

from . import rules as R
from .cleaning import basic, clean_name
from .matching import Grouper, group_names, match_key

MASTER_COLS = ["standard_name", "raw_name", "cleaned_name", "match_score",
               "occurrences", "first_seen", "manual"]


def load_master(path: str) -> dict:
    master = {}
    if path and os.path.exists(path):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                master[r["raw_name"]] = r
    return master


def save_master(master: dict, path: str):
    rows = sorted(master.values(), key=lambda r: (r["standard_name"], r["raw_name"]))
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=MASTER_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_review(new_raw: list, master: dict, path: str):
    """The spellings first seen in this run, grouped by standard name -
    the file a human skims after each run."""
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["standard_name", "raw_name", "cleaned_name", "match_score", "occurrences"])
        for r in sorted(new_raw, key=lambda x: (master[x]["standard_name"], x)):
            v = master[r]
            w.writerow([v["standard_name"], r, v["cleaned_name"], v["match_score"],
                        v["occurrences"]])


def standardize(raw_counts: Counter, master: dict, count_known: bool = True) -> list:
    """Give every raw name in `raw_counts` ({basic(raw): rows}) a standard name.

    Names already in `master` keep theirs. New names are cleaned and grouped
    against the master's standard names (manual ones first, then by volume)
    and added to `master` in place. Returns the list of new raw names."""
    g = Grouper()
    known = sorted(master.values(),
                   key=lambda r: (r.get("manual", "").lower() != "yes",
                                  -int(r.get("occurrences") or 0)))
    for r in known:
        if r["standard_name"]:
            g.add_leader(r["standard_name"], match_key(r["standard_name"]))
    for r in known:
        if r["standard_name"] and r["cleaned_name"]:
            g.remember(match_key(r["cleaned_name"]), r["standard_name"])

    new_raw = [r for r in raw_counts if r not in master]
    cleaned_of = {r: clean_name(r) for r in new_raw}
    freq = Counter()
    for r in new_raw:
        if cleaned_of[r]:
            freq[cleaned_of[r]] += raw_counts[r]

    existing_std = {r["standard_name"] for r in master.values()}
    existing_vol = Counter()
    for r in master.values():
        if r["standard_name"] and r["standard_name"] != R.UNIDENTIFIED:
            existing_vol[r["standard_name"]] += int(r.get("occurrences") or 0)
    std_of_clean = group_names(freq, g, existing_std, existing_vol)

    today = date.today().isoformat()
    for r in new_raw:
        c = cleaned_of[r]
        std, score = std_of_clean.get(c, (R.UNIDENTIFIED, 0))
        master[r] = {"raw_name": r, "cleaned_name": c, "standard_name": std,
                     "match_score": score, "first_seen": today,
                     "occurrences": raw_counts[r], "manual": ""}
    if count_known:
        for r, n in raw_counts.items():
            if r not in cleaned_of:
                master[r]["occurrences"] = int(master[r].get("occurrences") or 0) + n
    return new_raw


def resolve(names: Iterable, master: dict | None = None) -> dict:
    """Convenience API: {raw name: standard name} for a list of raw values.

    >>> resolve(["Acme Trading Ltd", "ACME TRADING LIMITED P.O BOX 1 KAMPALA"])
    {'Acme Trading Ltd': 'ACME TRADING LTD', 'ACME TRADING LIMITED P.O BOX 1 KAMPALA': 'ACME TRADING LTD'}
    """
    names = [n for n in names if n is not None and str(n).strip()]
    counts = Counter(basic(n) for n in names)
    master = {} if master is None else master
    standardize(counts, master)
    return {n: master[basic(n)]["standard_name"] for n in names}
