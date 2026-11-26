from collections import Counter

import pytest

from manifest_er import resolve
from manifest_er.matching import typo_only


def same(*names):
    out = resolve(list(names))
    return len(set(out.values())) == 1


@pytest.mark.parametrize("names", [
    ("ZAWADI GENERAL TRADING CO LTD", "ZAWADI GENERAL TRADNIG CO LTD"),        # typo
    ("ZAWADI GENERAL TRADING CO LTD", "ZAWADIGENERAL TRADING CO LTD"),         # glued words
    ("SUNRISE PLASTICS INDUSTRIES LTD",) * 5 + ("SUNRISE PLASTICS INDUS",),    # cut-off field
    ("SUNRISE PLASTICS INDUSTRIES LTD", "SUNRISE PLASTICS INDUSTRIES (UGANDA) LIMITED"),
    ("PETER MUSISI", "MUSISI PETER"),                                          # surname first
    ("WFP", "WORLD FOOD PROGRAMME"),                                           # acronym
])
def test_merges(names):
    assert same(*names)


@pytest.mark.parametrize("names", [
    ("SUNRISE PLASTICS LTD", "SUNSET PLASTICS LTD"),                     # look-alike words
    ("ROADTECH ENGINEERING GROUP 18 LTD", "ROADTECH ENGINEERING GROUP 21 LTD"),  # numbers
    ("PETER MUGISHA", "PETER MUSISI"),                                   # different people
    ("KAMBA COFFEE EXPORTERS LTD", "KAMBA TEA EXPORTERS LTD"),
    ("BANK OF UGANDA", "BANK OF TANZANIA"),
    ("ZAWADI GENERAL TRADING CO LTD", "AMANI GENERAL TRADING CO LTD"),   # shared generic words
])
def test_keeps_apart(names):
    assert not same(*names)


def test_bare_first_word_joins_dominant_company():
    names = ["TWIGA AUTO SPARES LTD"] * 50 + ["TWIGA"] * 3
    out = resolve(names)
    assert out["TWIGA"] == "TWIGA AUTO SPARES LTD"


def test_bare_generic_word_does_not_merge():
    names = ["GLOBAL FREIGHT SERVICES LTD"] * 50 + ["GLOBAL"] * 3
    out = resolve(names)
    assert out["GLOBAL"] != "GLOBAL FREIGHT SERVICES LTD"


def test_most_frequent_spelling_becomes_standard_name():
    names = ["NYOTA PHARMA LTD"] * 10 + ["NYOTA PHARMA LIMITED P.O BOX 4 KAMPALA"] * 3 \
        + ["Nyota Pharma Ltd."] * 2
    assert set(resolve(names).values()) == {"NYOTA PHARMA LTD"}


def test_memory_keeps_names_stable_and_respects_manual_edits():
    master = {}
    resolve(["ACME TRADING LTD"] * 5, master)
    # a human renames the customer in customer_master.csv
    for r in master.values():
        r["standard_name"], r["manual"] = "ACME TRADING GROUP", "yes"
    out = resolve(["ACME TRADING LIMITED P.O BOX 9 KAMPALA"], master)
    assert out["ACME TRADING LIMITED P.O BOX 9 KAMPALA"] == "ACME TRADING GROUP"


def test_typo_only_guards():
    assert typo_only("ZAWADI TRADING", "ZAWADI TRADNIG")
    assert not typo_only("SUNRISE TRADING", "SUNSET TRADING")
    assert not typo_only("GROUP 18", "GROUP 21")


def test_unidentified_rows():
    out = resolve(["TO ORDER", "TO ORDER P.O BOX 5 KAMPALA", "ACME TRADING LTD"])
    assert out["TO ORDER"] == out["TO ORDER P.O BOX 5 KAMPALA"] == "UNIDENTIFIED (TO ORDER)"
    assert Counter(out.values())["ACME TRADING LTD"] == 1


# --- regressions found by code review (v1.1) --------------------------------

@pytest.mark.parametrize("names", [
    ("JOHN OKELLO", "JOHN B OKELLO"),                      # extra initial = other person
    ("A B C TRADING", "A B TRADING"),
    ("GOLD RIVER LTD", "RIVER GOLD LTD"),                      # word order only for people
    ("NORTH EAST LOGISTICS LTD",) * 3 + ("NORTH LOGISTICS LTD",),
    ("GENERAL TRADING CO LTD",) * 5 + ("GENERAL TRADING AND CONTRACTING LTD",),
    ("UNITED NATIONS",) * 5 + ("UNITED NATIONS ENVIRONMENT PROGRAMME",),
    ("GULU SEED GROWERS CO LTD",) * 50 + ("GULU",),   # bare town
])
def test_review_regressions_keep_apart(names):
    assert not same(*names)


@pytest.mark.parametrize("names", [
    ("MBALE CEMENT LTD",) * 9 + ("MBALE CEMENT INDUSTRIES LTD",),   # town + word is distinctive
    ("GLOBAL FREIGHT LOGISTICS LTD",) * 9 + ("GLOBAL FREIGHT LOGISTICS JOINTLY",),
    ("BANK OF UGANDA",) * 9 + ("BANK OF UGANDA 37-45",),
    ("ZAWADI CONSTRUCTION ENGINEERING CO LTD", "ZAWADI CONSTRUCTION ENGINEERI NG CO"),
    ("NURU CLEARING AND FORWARDING LTD", "NURU CLEARING ANDFORWARDING LTD"),
    ("A TO Z HARDWARE LTD",) * 9 + ("A-Z HARDWARE", "ATOZ HARDWARE LTD"),
    ("ACME TRADING CO (U) LTD",) * 9 + ("ACME TRADING COU LTD", "ACME TRADINGCOMPANY (U) LTD"),
])
def test_review_regressions_merge(names):
    assert same(*names)
