import pytest

from manifest_er import clean_name, match_key
from manifest_er.rules import UNIDENTIFIED  # noqa: F401  (documented constant)


@pytest.mark.parametrize("raw, expected", [
    # legal forms and country tags
    ("Sunrise Plastics Industries (U) Limited", "SUNRISE PLASTICS INDUSTRIES (U) LTD"),
    ("SUNRISE PLASTICS INDUSTRIES ( U ) LTD.", "SUNRISE PLASTICS INDUSTRIES (U) LTD"),
    ("ZAWADI GENERAL TRADING CO.,LTD", "ZAWADI GENERAL TRADING CO LTD"),
    ("ZAWADI GENERAL TRADING COMPANY LIMITED", "ZAWADI GENERAL TRADING CO LTD"),
    ("IMARA CEMENT UGANDA-SMC LIMITED", "IMARA CEMENT UGANDA SMC LTD"),
    # address / contact tails
    ("TWIGA AUTO SPARES LTD P.O. BOX 1234 KAMPALA", "TWIGA AUTO SPARES LTD"),
    ("TWIGA AUTO SPARES LTD, PLOT 45 JINJA ROAD", "TWIGA AUTO SPARES LTD"),
    ("NYOTA PHARMA TEL: +256 772 123456", "NYOTA PHARMA"),
    ("NYOTA PHARMA KAMPALA, UGANDA", "NYOTA PHARMA"),
    # town that belongs to the name is kept when a legal suffix follows
    ("NAIROBI ENTERPRISES (U) LTD", "NAIROBI ENTERPRISES (U) LTD"),
    # prefixes and titles
    ("M/S. MAWE FOAM INDUSTRIES LTD", "MAWE FOAM INDUSTRIES LTD"),
    ("CONSIGNEE: MAWE FOAM INDUSTRIES LTD", "MAWE FOAM INDUSTRIES LTD"),
    ("MR. PETER MUGISHA P.O BOX 77 GULU", "PETER MUGISHA"),
    # agents: the real customer comes after "jointly with" / "on behalf of"
    ("SWIFTLINE FREIGHT LTD JOINTLY AND SEVERALLY WITH LAKESIDE BEVERAGES LTD",
     "LAKESIDE BEVERAGES LTD"),
    ("SWIFTLINE FREIGHT ON BEHALF OF LAKESIDE BEVERAGES LTD", "LAKESIDE BEVERAGES LTD"),
    # the place IS the name
    ("BANK OF UGANDA", "BANK OF UGANDA"),
    ("TO THE ORDER OF BANK OF UGANDA", "BANK OF UGANDA"),
    # acronyms
    ("WFP SOUTH SUDAN P.O BOX 440 JUBA", "WORLD FOOD PROGRAMME (WFP)"),
    ("UN WORLD FOOD PROGRAMME", "WORLD FOOD PROGRAMME (WFP)"),
    ("UNITED NATIONS MISSION IN SOUTH SU", "UNITED NATIONS MISSION IN SOUTH SUDAN (UNMISS)"),
])
def test_clean_name(raw, expected):
    assert clean_name(raw) == expected


@pytest.mark.parametrize("raw", [
    "TO ORDER", "TO ORDER .", "TO ORDER P.O. BOX 10679 KAMPALA", "TO ORDER JUBA, SOUTH SUDAN",
    "N/A", "NIL", "SAME AS CONSIGNEE", "", None,
])
def test_no_usable_name(raw):
    assert clean_name(raw) == ""


def test_to_order_with_a_company_keeps_the_company():
    assert clean_name("TO ORDER ACME TRADING LTD P.O BOX 1") == "ACME TRADING LTD"


@pytest.mark.parametrize("a, b", [
    ("SUNRISE PLASTICS INDUSTRIES (U) LTD", "SUNRISE PLASTICS INDUSTRIES UGANDA LIMITED"),
    ("OLIVE FOODS LTD", "OLIVE FOODS UGNDA LTD"),           # misspelt country is noise
    ("ACME CORP", "ACME CORPORATON"),                       # misspelt legal word is noise
])
def test_same_match_key(a, b):
    assert match_key(clean_name(a)) == match_key(clean_name(b))


@pytest.mark.parametrize("a, b", [
    ("BANK OF UGANDA", "BANK OF TANZANIA"),                 # place after OF is meaningful
    ("UGANDA GLASSWORKS LTD", "TANZANIA GLASSWORKS LTD"),     # place as first word too
    ("L.E.M INTERNATIONAL LTD", "L.M INTERNATIONAL LTD"),   # E inside initials is kept
])
def test_different_match_key(a, b):
    assert match_key(clean_name(a)) != match_key(clean_name(b))
