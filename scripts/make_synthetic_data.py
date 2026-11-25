"""
Generate a synthetic cargo manifest with messy customer names AND the truth.

Real manifests cannot be published, so this script recreates the kinds of
mess found in ~172k real spellings - with fictional customers:

  * legal-form variants      LIMITED / LTD / LTD. / CO.,LTD / COMPANY LIMITED
  * country tags             (U) / (UGANDA) / UGANDA / U / none
  * address & contact tails  P.O. BOX 1234 KAMPALA, PLOT 45 ..., TEL: +256 ...
  * prefixes                 M/S, MESSRS, CONSIGNEE:, TO THE ORDER OF, MR.
  * typos                    swapped, dropped, doubled letters
  * spacing                  SUNRISEPLASTICS, double spaces
  * truncation               the source system cuts the field at 70 characters
  * acronyms                 WFP / WORLD FOOD PROGRAMME
  * agents                   FORWARDER X JOINTLY AND SEVERALLY WITH <customer>
  * no consignee             TO ORDER / TO ORDER P.O. BOX ...
  * look-alikes (traps)      SUNRISE vs SUNSET PLASTICS, GROUP 18 vs GROUP 21,
                             PETER MUGISHA vs PETER MUSISI, BANK OF UGANDA vs TANZANIA

Outputs
  data/sample_manifest.xlsx   manifest-style workbook (pivot block above the header)
  data/ground_truth.csv       sheet, row, raw customer value, true entity id

All names are generated; any resemblance to a real business is coincidental.
"""

from __future__ import annotations

import csv
import os
import random
import string

import openpyxl
from openpyxl.styles import Font

SEED = 7
N_ROWS = 12_000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# --------------------------------------------------------------------------- #
#  Fictional customers
# --------------------------------------------------------------------------- #
FIRST = ["ZAWADI", "AMANI", "NURU", "BARAKA", "TWIGA", "NYOTA", "MAWE", "PAMOJA",
         "UMOJA", "MVUA", "KARIBU", "ZURI", "IMARA", "FARAJA", "NEEMA", "TUMAINI",
         "UPENDO", "BAHATI", "JABALI", "MWANGA", "RAFIKI", "TAJI", "USHINDI", "WEMA",
         "ZIWA", "KILELE", "PWANI", "SAUTI", "TULIA", "FURAHA", "HODARI", "NGUVU",
         "AMANA", "MAJANI", "KESHO", "MBEGU", "JIWE", "MSITU", "NDOTO", "BAOBAB"]
INDUSTRY = ["PLASTICS INDUSTRIES", "AUTO SPARES", "GENERAL TRADING", "COFFEE EXPORTERS",
            "FLOUR MILLERS", "STEEL MILLS", "PHARMA", "TEXTILE MILLS", "PACKAGING",
            "HARDWARE", "FOAM INDUSTRIES", "BEVERAGES", "TILES & CERAMICS", "AGRO INPUTS",
            "MOTORS", "SOLAR SOLUTIONS", "FISHERIES", "COSMETICS", "CEMENT", "LOGISTICS"]
TAGS = ["", "", "(U)", "(U)", "UGANDA", "(T)"]
LEGAL = ["LTD", "LTD", "LTD", "CO LTD", "SMC LTD"]

# look-alike pairs: different customers that a naive fuzzy matcher merges
TRAPS = [
    ("SUNRISE PLASTICS", "(U)", "LTD"), ("SUNSET PLASTICS", "(U)", "LTD"),
    ("ROADTECH ENGINEERING GROUP 18", "", "LTD"), ("ROADTECH ENGINEERING GROUP 21", "", "LTD"),
    ("KAMBA COFFEE EXPORTERS", "", "LTD"), ("KAMBA TEA EXPORTERS", "", "LTD"),
    ("TWIGA FLOUR MILLERS", "", "LTD"),          # shares TWIGA with a generated company
    ("NOVA TRADING", "", "LTD"), ("NOVO TRADING", "", "LTD"),
]
PERSONS = ["PETER MUGISHA", "PETER MUSISI", "GRACE ATIENO", "JOSEPH OKELLO",
           "AISHA NAMUGGA", "DAVID SSEMPALA", "SARAH NAKATO", "MOSES WANYAMA"]
ORGS = {
    "ORG:WFP": ["WFP", "WORLD FOOD PROGRAMME", "WORLD FOOD PROGRAMME - SOUTH SUDAN",
                "UN WORLD FOOD PROGRAMME", "WFP SOUTH SUDAN P.O BOX 440 JUBA",
                "WORLD FOOD PROGRAMME (WFP) JEBEL ROAD JUBA"],
    "ORG:UNICEF": ["UNICEF", "UNICEF UGANDA", "UNITED NATIONS CHILDREN'S FUND",
                   "UNICEF SOUTH SUDAN P.O BOX 45 JUBA"],
    "ORG:UNHCR": ["UNHCR", "UNHCR REPRESENTATION IN UGANDA",
                  "UNITED NATIONS HIGH COMMISSIONER FOR REFUGEES", "UNHCR KAMPALA"],
    "ORG:UNMISS": ["UNMISS", "UNITED NATIONS MISSION IN SOUTH SUDAN (UNMISS)",
                   "UNITED NATIONS MISSION IN SOUTH SU", "UNMISS TOMPING SITE JUBA",
                   "UNITED NATIONS MISSION IN THE REPUB"],
    "ORG:BOU": ["BANK OF UGANDA", "TO THE ORDER OF BANK OF UGANDA", "BANK OF UGANDA KAMPALA"],
    "ORG:BOT": ["BANK OF TANZANIA", "TO THE ORDER OF BANK OF TANZANIA"],
}
TO_ORDER = ["TO ORDER", "TO ORDER .", "TO THE ORDER OF", "TO ORDER P.O. BOX {n} KAMPALA",
            "TO ORDER PLOT {n} {road} ROAD, KAMPALA UGANDA", "TO ORDER JUBA, SOUTH SUDAN",
            "TO ORDER TEL: +256 7{d8}", "TO ORDER KONYO KONYO MARKET JUBA"]
FORWARDER = "SWIFTLINE FREIGHT LTD JOINTLY AND SEVERALLY WITH "

ROADS = ["JINJA", "BOMBO", "ENTEBBE", "LUTHULI", "NKRUMAH", "KAMPALA", "MALAKIA", "HAI NEEM"]
ADDRESSES = [
    "P.O. BOX {n} KAMPALA", "P.O BOX {n}, KAMPALA UGANDA", "PO BOX {n} JUBA SOUTH SUDAN",
    "PLOT {n} {road} ROAD", "PLOT NO. {n}, INDUSTRIAL AREA, KAMPALA",
    "TEL: +256 7{d8}", "TEL +211 9{d8}", "TIN: 100{d7}", "EMAIL: INFO@{w}.CO.UG",
    "KAMPALA, UGANDA", "JUBA SOUTH SUDAN", "DAR ES SALAAM TANZANIA", "NAMANVE INDUSTRIAL PARK",
]
PREFIXES = ["M/S ", "M/S. ", "MESSRS ", "CONSIGNEE: ", "TO THE ORDER OF ", "COMPANY NAME: "]
PERSON_PREFIXES = ["MR ", "MR. ", "MRS ", "DR. ", "HAJI ", "ENG. "]


def build_entities(rng: random.Random) -> list:
    """[(entity_id, kind, data)]"""
    ents = []
    industries = INDUSTRY * 3
    rng.shuffle(industries)
    for i, first in enumerate(FIRST):
        core = f"{first} {industries[i]}"
        ents.append((f"C:{core}", "company", (core, rng.choice(TAGS), rng.choice(LEGAL))))
    for core, tag, legal in TRAPS:
        ents.append((f"C:{core}", "company", (core, tag, legal)))
    for p in PERSONS:
        ents.append((f"P:{p}", "person", p))
    for eid, variants in ORGS.items():
        ents.append((eid, "org", variants))
    ents.append(("TO_ORDER", "to_order", TO_ORDER))
    return ents


# --------------------------------------------------------------------------- #
#  Mess generators
# --------------------------------------------------------------------------- #
def fill(t: str, rng) -> str:
    return t.format(n=rng.randint(10, 99999), road=rng.choice(ROADS),
                    d8="".join(rng.choices(string.digits, k=8)),
                    d7="".join(rng.choices(string.digits, k=7)),
                    w="".join(rng.choices(string.ascii_uppercase, k=6)))


def typo(word: str, rng) -> str:
    if len(word) < 5:
        return word
    i = rng.randint(1, len(word) - 2)
    op = rng.choice(["swap", "drop", "double", "sub"])
    if op == "swap":
        return word[:i] + word[i + 1] + word[i] + word[i + 2:]
    if op == "drop":
        return word[:i] + word[i + 1:]
    if op == "double":
        return word[:i] + word[i] + word[i:]
    return word[:i] + rng.choice("AEIOU") + word[i + 1:]


def legal_variant(legal: str, rng) -> str:
    if legal == "CO LTD":
        return rng.choice(["CO LTD", "CO. LTD", "CO.,LTD", "COMPANY LIMITED", "COMPANY LTD",
                           "CO LIMITED", "COLTD"])
    if legal == "SMC LTD":
        return rng.choice(["SMC LTD", "SMC LIMITED", "-SMC LIMITED", "S.M.C LTD", "LTD"])
    return rng.choice(["LTD", "LTD", "LIMITED", "LIMITED", "LTD.", "LIMTED", ""])


def tag_variant(tag: str, rng) -> str:
    if tag in ("(U)", "UGANDA"):
        return rng.choice(["(U)", "(U)", "(UGANDA)", "UGANDA", "U", "( U )", ""])
    if tag == "(T)":
        return rng.choice(["(T)", "TANZANIA", "(TANZANIA)", ""])
    return ""


def company_variant(core: str, tag: str, legal: str, rng, bare_ok: bool) -> str:
    words = core.split()
    if bare_ok and rng.random() < 0.03:                     # bare first word: "TWIGA"
        return words[0]
    if rng.random() < 0.10:                                 # one typo (not the 1st letter)
        j = rng.randrange(len(words))
        words[j] = typo(words[j], rng)
    if len(words) >= 2 and rng.random() < 0.03:             # glued words
        words[:2] = [words[0] + words[1]]
    name = " ".join(w for w in [" ".join(words), tag_variant(tag, rng),
                                legal_variant(legal, rng)] if w)
    if rng.random() < 0.08:
        name = rng.choice(PREFIXES) + name
    if rng.random() < 0.40:
        sep = rng.choice([" ", ", ", " - ", "  "])
        name += sep + fill(rng.choice(ADDRESSES), rng)
        if rng.random() < 0.3:
            name += " " + fill(rng.choice(ADDRESSES), rng)
    return name


def person_variant(p: str, rng) -> str:
    first, last = p.split()
    if rng.random() < 0.10:
        last = typo(last, rng)
    name = f"{first} {last}" if rng.random() < 0.8 else f"{last} {first}"
    if rng.random() < 0.35:
        name = rng.choice(PERSON_PREFIXES) + name
    if rng.random() < 0.35:
        name += " " + fill(rng.choice(ADDRESSES), rng)
    return name


def finish(s: str, rng) -> str:
    """Case, stray spaces and the 70-character field limit."""
    r = rng.random()
    if r < 0.08:
        s = s.title()
    elif r < 0.11:
        s = s.lower()
    if rng.random() < 0.05:
        s = s.replace(" ", "  ", 1)
    return s[:70]


def render(ent, rng, bare_ok_ids) -> str:
    eid, kind, data = ent
    if kind == "company":
        core, tag, legal = data
        s = company_variant(core, tag, legal, rng, eid in bare_ok_ids)
    elif kind == "person":
        s = person_variant(data, rng)
    elif kind == "org":
        s = rng.choice(data)
    else:
        s = fill(rng.choice(data), rng)
    return finish(s, rng)


# --------------------------------------------------------------------------- #
def main():
    rng = random.Random(SEED)
    ents = build_entities(rng)
    # a bare first word is only a fair test when no other customer shares it
    firsts = [e[2][0].split()[0] for e in ents if e[1] == "company"]
    bare_ok = {e[0] for e in ents if e[1] == "company" and firsts.count(e[2][0].split()[0]) == 1}

    # volumes follow a long tail, like real customers
    order = ents[:]
    rng.shuffle(order)
    weights = [1 / (i + 1) ** 0.8 for i in range(len(order))]
    to_order = next(e for e in order if e[0] == "TO_ORDER")
    weights[order.index(to_order)] = weights[2]

    # each customer has a few habitual spellings (templates reused by its
    # clerks) plus occasional one-off variants
    habits = {e[0]: [render(e, rng, bare_ok) for _ in range(rng.randint(2, 6))] for e in order}
    forwarded = [e for e in order[:15] if e[1] == "company"][:3]

    rows = []
    for _ in range(N_ROWS):
        e = rng.choices(order, weights)[0]
        if e in forwarded and rng.random() < 0.04:
            core, tag, legal = e[2]
            raw = finish(FORWARDER + f"{core} {tag} {legal}".replace("  ", " "), rng)
        elif rng.random() < 0.75:
            raw = rng.choice(habits[e[0]])
        else:
            raw = render(e, rng, bare_ok)
        rows.append((e[0], raw))

    os.makedirs(DATA, exist_ok=True)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    header = ["Bill Of Lading", "Container No", "Origin", "Dest.", "Commodity Description",
              "Weight (Kgs)", "TEUs", "Customer:"]
    truth = []
    split = int(len(rows) * 0.8)
    for title, part, pivot in (("Imports", rows[:split], True), ("Exports", rows[split:], False)):
        ws = wb.create_sheet(title)
        if pivot:                       # real files carry a pivot table above the data
            ws.append(["Row Labels", "Sum of TEUs"])
            for c, v in (("UG", 812), ("SS", 233), ("TZ", 97)):
                ws.append([c, v])
            ws.append([])
        ws.append(header)
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
        for i, (eid, raw) in enumerate(part):
            origin, dest = ("CN", rng.choice(["UG", "UG", "UG", "SS", "TZ"])) if title == "Imports" \
                else (rng.choice(["UG", "UG", "TZ"]), "NL")
            ws.append([f"BL{rng.randint(10**7, 10**8 - 1)}",
                       "".join(rng.choices(string.ascii_uppercase, k=4)) + str(rng.randint(10**6, 10**7 - 1)),
                       origin, dest, rng.choice(["Plastics", "Coffee", "Steel", "Machinery", "Foodstuff"]),
                       rng.randint(1000, 28000), rng.choice([1, 1, 2]), raw])
            truth.append((title, ws.max_row, raw, eid))
        ws.column_dimensions["H"].width = 70
    wb.save(os.path.join(DATA, "sample_manifest.xlsx"))

    with open(os.path.join(DATA, "ground_truth.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sheet", "row", "raw_customer", "true_entity"])
        w.writerows(truth)

    n_spell = len({r for _, r in rows})
    print(f"{len(rows):,} rows | {n_spell:,} distinct spellings | {len(ents)} true customers")
    print(f"-> {os.path.join(DATA, 'sample_manifest.xlsx')}")


if __name__ == "__main__":
    main()
