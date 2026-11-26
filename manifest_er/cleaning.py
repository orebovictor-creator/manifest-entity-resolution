"""
Stage 1 - cleaning: one raw "Customer" cell -> a clean display name.

    'M/S. Sunrise Plastics Industries (U) Limited, P.O. Box 1234 Kampala'
        -> 'SUNRISE PLASTICS INDUSTRIES (U) LTD'

Returns '' when the cell holds no usable name (e.g. 'TO ORDER P.O BOX 77').
"""

from __future__ import annotations

import re
import unicodedata

from . import rules as R


def basic(s) -> str:
    """Upper-case ASCII with single spaces. Used as the lookup key of a raw value."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.upper()).strip()


def _strip_leading(s: str) -> str:
    """Remove labels / titles in front of the name, repeatedly:
    'CONSIGNEE: M/S. MR JOHN DOE' -> 'JOHN DOE'. A title in front of a
    company name with a legal suffix is part of the name: 'MR PRICE LTD'."""
    for _ in range(10):
        before = s
        s = re.sub(r"^[^A-Z]+", "", s)                  # must start with a letter
        s = R.LEAD_RE.sub("", s, count=1)
        m = R.TITLE_RE.match(s)
        if m:
            rest = s[m.end():]
            lg = R.LEGAL_RAW_RE.search(rest)
            # "MR PRICE LTD": a one- or two-word company named with a title
            if not (lg and len(re.findall(r"[A-Z]+", rest[:lg.start()])) <= 2):
                s = rest
        if s == before:
            break
    return s


def _drop_repeat(s: str) -> str:
    """'ACME TRADING LTD ACME TRADING LTD PO BOX 1' -> 'ACME TRADING LTD'."""
    toks = s.split()
    if len(toks) >= 4:
        head = " ".join(toks[:2])
        i = s.find(" " + head + " ", len(head))
        if i < 0 and s.endswith(" " + head):
            i = len(s) - len(head) - 1
        if i > 0:
            return s[:i]
    return s


FIELD_CUT = 60      # raw values this long may have been cut by the ~70-char field


def _fix_suffixes(s: str, raw_len: int) -> str:
    # legal words glued to neighbours: COLTD, ACMELIMITED, LTDPLOT, ACME-SMC
    s = re.sub(r"\bCO\.?LTD\b", "CO LTD", s)
    s = re.sub(r"([A-Z]{3,})(LIMITED|LTD|COMPANY)\b", r"\1 \2", s)
    s = re.sub(r"\b(LIMITED|LTD)(ADD\w*|PLOT\w*|P\.?\s*O\b|TIN\w*|TEL\w*|HOUSE\w*|[A-Z]{3,})",
               r"\1 \2", s)
    s = re.sub(r"(?:\s*-\s*|(?<=[A-Z]{3}))SMC\b", " SMC", s)
    s = re.sub(r"\bL\s+TD\b|\bL\.\s*T\.\s*D\b", "LTD", s)
    # legal word cut off at the end of the ~70-character field. LIMI/LIMIT/
    # LIMITE are never names; L/LT/LI/LIM can be ("ZHANG LI", "TAN LIM"), so
    # those are only repaired when the raw value was long enough to be cut.
    s = re.sub(r"\s(?:LIMI|LIMIT|LIMITE|LTDA)$", " LTD", s)
    if raw_len >= FIELD_CUT:
        s = re.sub(r"\s(?:L|LT|LI|LIM)$", " LTD", s)
    for rx, rep in R.SUFFIX_FIX:
        s = rx.sub(rep, s)
    return re.sub(r"\s+", " ", s)


def _cut_address(s: str) -> str:
    m = R.LEGAL_RE.search(s)
    if m and m.start() >= 2:
        # a legal suffix ends the name (this keeps town words that belong to
        # the name: "MOMBASA SAFARI WEAR (U) LTD")
        end = m.end()
        chain = R.LEGAL_CHAIN_RE.match(s[end:])
        if chain:
            end += chain.end()
        s = s[:end]
        # ...unless a definite address marker comes BEFORE it ("ACME P.O BOX 1 LTD").
        # Ordinary words never cut here: "ACME BUILDING MATERIALS LTD",
        # "LION PLAZA LTD", "MOMBASA SAFARI WEAR (U) LTD" stay whole.
        a = R.HARD_ADDR_RE.search(s)
        if a and a.start() >= 3:
            s = s[:a.start()]
    else:
        cuts = [x.start() for x in (R.ADDR_RE.search(s), R.SOFT_RE.search(s))
                if x and x.start() >= 3]
        if cuts:
            s = s[:min(cuts)]
    return s


def _tidy(s: str) -> str:
    s = re.sub(r"[\"'`*]", "", s)
    s = re.sub(r"[,;:\\|_]+", " ", s)
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\.(?=\s|$)", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for _ in range(3):
        t = R.TRAILING_PLACE.sub("", s)
        if not R.KEEP_PLACE_RE.search(t.strip()) and len(t.strip()) >= 2:
            s = t
        s = re.sub(r"[\s\-.,&(/]+$", "", s)
        # dangling connector words left by a cut; CO is kept ("SMITH AND CO")
        s = re.sub(r"\s+(?:AND|OF|THE|AT|IN|FOR)$", "", s)
    s = re.sub(r"\(\s*$", "", s).strip()
    s = _strip_leading(s)
    if s.count("(") > s.count(")"):
        s = s.replace("(", "").strip()
    return s


def clean_name(raw) -> str:
    """Raw customer cell -> cleaned display name ('' if no usable name)."""
    if raw is None:
        return ""
    s = basic(raw)
    # "TO THE ORDER OFSTANDARD BANK ..." (missing space after OF)
    # ("ORDER OFFICE NO. 358 ..." is an address, not "OF" + "FICE")
    s = re.sub(r"^(?:TO\s+)?(?:THE\s+)?ORDER\s+OF(?!F)(?=[A-Z]{3})", "", s)

    # "FORWARDER X JOINTLY AND SEVERALLY WITH ACME LTD" -> the customer is ACME LTD
    m = None
    for m in R.BEHALF_RE.finditer(s):
        pass
    if m and len(s) - m.end() >= 4:
        s = s[m.end():]

    s = _strip_leading(s)

    # what is left of "TO ORDER ...": keep a company ("ORDER ACME TRADING LTD"),
    # an address alone ("ORDER P.O BOX 1 / ORDER JUBA SOUTH SUDAN") is no name
    m = re.match(r"ORDER\b[\s.:;,\-]*", s)
    if m:
        rest = s[m.end():]
        a, lg = R.ADDR_RE.search(rest), R.LEGAL_RAW_RE.search(rest)
        if lg and (not a or lg.start() < a.start()):
            s = _strip_leading(rest)
        else:
            return ""
    if not s or R.ADDR_START_RE.match(s):
        return ""

    s = _drop_repeat(s)
    s = R.BRANCH_RE.sub(" ", s).strip()
    s = _fix_suffixes(s, len(basic(raw)))
    s = _cut_address(s)
    s = _tidy(s)

    if len(s) < 2 or R.NOT_A_NAME.match(s):
        return ""
    for rx, name in R.ALIASES:
        if rx.match(s):
            return name
    return s
