"""
Domain rules: everything the cleaner and the matcher "know" about the data.

The patterns were tuned on ~172,000 distinct raw customer spellings from
East African transit cargo manifests (2022-2026). They are plain data:
add a pattern to a list to teach the tool something new - no code changes.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
#  Tuning knobs
# --------------------------------------------------------------------------- #
FUZZY_THRESHOLD = 90      # 0-100: minimum similarity for a typo-level merge
FAMILY_SHARE = 0.70       # a "family" merge needs one name to own 70% of the rows
UNIDENTIFIED = "UNIDENTIFIED (TO ORDER)"   # rows with no usable consignee name

# --------------------------------------------------------------------------- #
#  Aliases: organisations written either as an acronym or in full.
#  Pattern is matched at the start of the cleaned name -> fixed standard name.
# --------------------------------------------------------------------------- #
_ALIASES = [
    (r"WFP\b|(?:UNITED\s+NATIONS?\W*|UN\s+)?WORLD\s*FOOD\s*PROG", "WORLD FOOD PROGRAMME (WFP)"),
    # the field is often cut ("...MISSION IN SOUTH SU", "...IN THE REPUB")
    (r"UNMISS\b|UNITED\s+NATIONS?\W*(?:MISSIONS?|MISSON|UNMISS)\b"
     r"(?!.*\b(?:CONGO|MONUSCO|ABYEI|UNISFA|DRC)\b)",
     "UNITED NATIONS MISSION IN SOUTH SUDAN (UNMISS)"),
    (r"UNHCR\b|UNITED\s+NATIONS\s+HIGH\s+COMM", "UNHCR"),
    (r"UNICEF\b|UNITED\s+NATIONS\s+CHILDREN", "UNICEF"),
    (r"IOM\b|INTERNATIONAL\s+ORGANI[SZ]ATION\s+FOR\s+MIGRATION",
     "INTERNATIONAL ORGANIZATION FOR MIGRATION (IOM)"),
    (r"ICRC\b|INTERNATIONAL\s+COMMITTEE\s+OF\s+(?:THE\s+)?RED\s+CROSS",
     "INTERNATIONAL COMMITTEE OF THE RED CROSS (ICRC)"),
    (r"UNDP\b|UNITED\s+NATIONS?\W*DEVELOPMENT", "UNITED NATIONS DEVELOPMENT PROGRAMME (UNDP)"),
    (r"UNFPA\b|UNITED\s+NATIONS\s+POPULATION\s+FUND", "UNFPA"),
    (r"UNOPS\b|UNITED\s+NATIONS\s+OFFICE\s+FOR\s+PROJECT", "UNOPS"),
    (r"UNISFA\b|UNITED\s+NATIONS?\s+INTERIM\s+SECUR", "UNISFA"),
    (r"MONUSCO\b|UNITED\s+NATIONS?\s+ORGANI[SZ]ATION\s+STABILI", "MONUSCO"),
    (r"FAO\b|FOOD\s+(?:AND|&)\s+AGRICULTUR\w*\s+ORGANI", "FOOD AND AGRICULTURE ORGANIZATION (FAO)"),
    (r"WHO\b|WORLD\s+HEALTH\s+ORGANI", "WORLD HEALTH ORGANIZATION (WHO)"),
    (r"MSF\b|MEDECINS\s+SANS\s+FRONTIERES|DOCTORS\s+WITHOUT\s+BORDERS",
     "MEDECINS SANS FRONTIERES (MSF)"),
]
ALIASES = [(re.compile(p), name) for p, name in _ALIASES]
ALIAS_NAMES = {name for _, name in ALIASES}

# --------------------------------------------------------------------------- #
#  Cleaning
# --------------------------------------------------------------------------- #

# Labels, titles and honorifics written in front of the real name
LEADING_JUNK = [
    r"TO\s+THE\s+ORDER\s+OF", r"TO\s+ORDER\s+OF", r"THE\s+ORDER\s+OF", r"ORDER\s+OF",
    r"FOR\s+AND\s+ON\s+BEHALF\s+OF", r"ON\s+BEHALF\s+OF",
    r"COMPANY\s*NAME", r"COMPANY", r"CO\s*NAME", r"CUSTOMER\s*NAME", r"CONSIGNEE\s*NAME",
    r"IMPORTER\s*NAME", r"EXPORTER\s*NAME", r"FULL\s*NAME", r"NAME", r"KIND\s+ATTN",
    r"CONSIGNEE", r"CONSIGNE", r"CNEE", r"NOTIFY\s*PARTY", r"NOTIFY", r"SHIPPER",
    r"EXPORTER", r"IMPORTER", r"BUYER", r"CUSTOMER", r"RECEIVER", r"ATTN",
    r"ATTENTION", r"TO", r"MESSRS", r"MESSERS", r"M\s*/\s*S", r"MRS", r"MR", r"MS",
    r"MISS", r"MADAM", r"MDM", r"DR", r"DOCTOR", r"ENGR", r"ENG", r"PROF", r"HON",
    r"REV", r"SIR", r"SHEIKH", r"SHK", r"HAJJI", r"HAJI", r"HAJAT", r"CAPT", r"THE",
    r"MANAGER", r"M\s+S(?=\s+[A-Z]{3})",
]
LEAD_RE = re.compile(r"^(?:" + "|".join(LEADING_JUNK) + r")(?:\s*[.:;,\-/]+\s*|\s+)")

# "FORWARDER X JOINTLY AND SEVERALLY WITH Y" / "X ON BEHALF OF Y": the customer is Y
BEHALF_RE = re.compile(
    r"\b(?:JO?I?NTLY\s+(?:AND\s+)?(?:SEVERALLY\s+)?WITH|J\s*/\s*S\s+WITH|"
    r"(?:FOR\s+AND\s+)?ON\s+BEHALF\s+OF|O\s*/\s*B\s+OF|A\s*/\s*C\s+OF)\s+")

# "(UGANDA BRANCH)", "KENYA BRANCH"
BRANCH_RE = re.compile(r"\(?\s*\b(?:UGANDA|TANZANIA|ETHIOPIA|SOUTH\s+SUDAN|KENYA|EA)?"
                       r"\s*BRANCH\b\s*\)?")

# Legal words: spelling mistakes and truncations seen in the data -> one form
_SUFFIX_FIX = [
    (r"\bLIMITED\b|\bLIMITE\b|\bLIMIT\b|\bLIMI\b|\bLIMTED\b|\bLIMITTED\b|\bLMITED\b|"
     r"\bLIMTD\b|\bLTD\.?|\bL\.T\.D\.?", "LTD"),
    (r"\bCOMPANY\b|\bCOMPANEY\b|\bCOMAPNY\b|\bCOMPNAY\b|\bCOMPANI\b|\bCOMPAN\b|\bCOMP\b", "CO"),
    (r"\bCO\.", "CO"),
    (r"\bCORPORATION\b|\bCORPORATIO\b|\bCORPORAT\b", "CORP"),
    (r"\bINCORPORATED\b", "INC"),
    (r"\bP\.\s*L\.\s*C\.?|\bPLC\.", "PLC"),
    (r"\bS\.\s*M\.\s*C\.?|\bSMC\.|\bSINGLE\s+MEMBER\s+CO\b", "SMC"),
    (r"\(\s*U\s*\)|\(\s*UG\s*\)", "(U)"), (r"\(\s*T\s*\)", "(T)"), (r"\(\s*E\s*\)", "(E)"),
    (r"\bINT'?L\b|\bINTL\b", "INTERNATIONAL"),
    (r"\bENTERPRISE\b", "ENTERPRISES"),
    (r"\s*&\s*", " & "),
]
SUFFIX_FIX = [(re.compile(p), r) for p, r in _SUFFIX_FIX]

# A legal suffix ends the name; (U)/(T)/LTD/SMC/PLC chains right after it are kept
LEGAL_RE = re.compile(r"\b(LTD|PLC|LLC|INC|GMBH|SARL|CORP|PTE|PVT)\b")
LEGAL_CHAIN_RE = re.compile(r"^(?:\s*(?:\(U\)|\(T\)|\(E\)|LTD|PLC|SMC|CO\s+LTD))+")
# legal words before normalisation (used on "TO ORDER <name>" values)
LEGAL_RAW_RE = re.compile(r"\b(?:LTD|LIMITED|LIMI\w*|LIM|PLC|LLC|INC|SMC|SARL|SPRL|CORP\w*|"
                          r"GMBH|PVT)\b")
HAS_LEGAL_RE = re.compile(r"\b(?:LTD|PLC|LLC|INC|GMBH|SARL|SPRL|CORP|PTE|PVT|SMC|LLP|SA)\b")

# Where an address / contact tail starts
ADDRESS_MARKERS = [
    r"P\s*\.?\s*O\s*\.?\s*B(?:OX)?\b", r"\bPOB\b", r"\bP\s*\.?\s*B\.?\s*\d", r"\bBOX\b",
    r"\bB\.?P\.?\s*\d", r"\bPRIVATE\s+BAG\b", r"\bPLOT\b", r"\bPLT\b",
    r"\bTEL\b", r"\bTEL\s*[:.]", r"\bTELEPHONE\b", r"\bPHONE\b", r"\bMOB(?:ILE)?\b",
    r"\bCELL\b", r"\bFAX\b", r"\bTIN\b", r"\bTIN\s*[:.]", r"\bVAT\b", r"\bVRN\b",
    r"\bE-?MAIL\b", r"\bADD(?:RESS|R)?\b", r"\bFULL\s+ADDRESS\b", r"\bSTREET\b",
    r"\bROAD\b", r"\bRD\b", r"\bAVENUE\b", r"\bAVE\b", r"\bFLOOR\b", r"\bBUILDING\b",
    r"\bHOUSE\s+NO\b", r"\bKEBELE\b", r"\bWOREDA\b", r"\bSUB\s*CITY\b", r"\bZONE\b",
    r"\bINDUSTRIAL\s+AREA\b", r"\bC\s*/\s*O\b", r"\bCONTACT\b", r"\bOPPOSITE\b",
    r"\bOPP\b", r"\bNEAR\b", r"\bVILLAGE\b", r"\bWARD\b", r"\bDISTRICT\b",
    r"\bDIVISION\b", r"\bMUNICIPALITY\b", r"\bTOWN\s+COUNCIL\b", r"\bBLOCK\b",
    r"\bBKG\b", r"\bBOOKING\b", r"\bSEE\s+ABOVE\b", r"\bADRESS\b", r"\bLOCATION\b",
    r"\bDUMMY\b", r"\b\w*\d{5,}", r"-\s*[A-Z]{2,5}\d",
    r"\bLOCATED\b", r"\bMARKET\b", r"\bMALL\b", r"\bARCADE\b", r"\bPLAZA\b",
    r"\bEMPORIUM\b", r"\bSHOP\s*(?:NO|\d)", r"\bNEXT\s+TO\b", r"\bPARISH\b", r"\bHIGHWAY\b",
    r"\bLANE\b", r"\bT/A\b", r"\bT\s+A\b", r"\bP\.?O\.?\s*\d",
    r"\bNAKASERO\b", r"\bNAKIVUBO\b", r"\bKISENYI\b", r"\bMENGO\b", r"\bKATWE\b",
    r"\bNATETE\b", r"\bOWINO\b", r"\bLUZIRA\b", r"\bKAWEMPE\b", r"\bMAKINDYE\b",
    r"\bRUBAGA\b", r"\bBWAISE\b", r"\bKAFUMBE\b", r"\bKIKUUBO\b", r"\bKARIAKOO\b",
    r"\bKINONDONI\b", r"\bILALA\b", r"\bTEMEKE\b", r"\bBOLE\b", r"\bMERKATO\b",
    r"\bTONG\s*PI?NG\b", r"\bMUNUKI\b", r"\bKONYO\s*KONYO\b", r"\bREG(?:ISTRA\w*)?\b\s*NO",
    r"\bNO\s*[.:]?\s*\d", r"#\s*\d", r"\b\d+\s*(?:ST|ND|RD|TH)\b", r"\+\s*\d",
    r"\b\d{4,}\b", r"@", r"\bWWW\.", r"\bTIN\d",
    # towns / areas that start an address tail
    r"\bKAMPALA\b", r"\bENTEBBE\b", r"\bJINJA\b", r"\bJINJIA\b", r"\bMBARARA\b",
    r"\bGULU\b", r"\bMUKONO\b", r"\bWAKISO\b", r"\bNAMANVE\b", r"\bKOLOLO\b",
    r"\bNTINDA\b", r"\bNAKAWA\b", r"\bBUGOLOBI\b", r"\bNAGURU\b", r"\bKYADONDO\b",
    r"\bKYAGG?WE\b", r"\bHOIMA\b", r"\bMASAKA\b", r"\bMBALE\b", r"\bLIRA\b",
    r"\bARUA\b", r"\bTORORO\b", r"\bBUSIA\b", r"\bKASESE\b", r"\bJUBA\b",
    r"\bNIMULE\b", r"\bDAR\s*ES\s*SAL+AAM\b", r"\bDSM\b", r"\bARUSHA\b", r"\bMWANZA\b",
    r"\bMOSHI\b", r"\bDODOMA\b", r"\bADDIS\b", r"\bMOMBASA\b", r"\bNAIROBI\b",
    r"\bREPUBLIC\s+OF\b", r"\bUNITED\s+REPUBLIC\b",
]
ADDR_RE = re.compile("|".join(ADDRESS_MARKERS))
# towns that may legitimately appear INSIDE a company name before its suffix
# ("NAIROBI ENTERPRISES (U) LTD")
TOWN_IN_NAME_RE = re.compile(r"\b(KAMPALA|NAIROBI|JUBA|ARUSHA|ADDIS|MOMBASA|JINJA|MUKONO|"
                             r"MASAKA|MBALE|GULU|LIRA|HOIMA|DSM|KASESE)\b")

# Building / area words. Only applied to names WITHOUT a legal suffix,
# so "TWIN TOWERS LTD" stays intact while "ACME HOLDINGS TWIN TOWERS" is cut.
SOFT_MARKERS = [
    r"\bTOWERS?\b", r"\bHAI\s+[A-Z]", r"\bMALAKI(?:A|YA)\b", r"\bKATOR\b", r"\bGUDELE\b",
    r"\bTOMPING\b", r"\bJEBEL\b", r"\bMETERS\b", r"\bALONG\b", r"\bBEHIND\b",
    r"\bCOMPOUND\b", r"\bLEVEL\s*\d", r"\bCOURTS\b", r"\bXXX\b", r"\bUN\s*HOUSE\b",
    r"\bCOMPLEX\b", r"\bHQ\b", r"\bMOVEMENT\s+CONTROL\b", r"\bDIRECTOR\s+OF\b",
]
SOFT_RE = re.compile("|".join(SOFT_MARKERS))

# Address right at the start: what is left of "TO ORDER PO BOX ..."
ADDR_START_RE = re.compile(r"^(?:P\s*\.?\s*O\b|BOX\b|PLOT\b|PLT\b|TEL\b|ADD(?:RESS|R)?\b|"
                           r"TIN\b|\d)")

# Country / town words at the END of a name are an address tail ("... LTD UGANDA")
TRAILING_PLACE = re.compile(
    r"(?:\s+(?:UGANDA|UGAND|UGAN|UGNDA|UGANADA|TANZANIA|TANZANI|TANZAN|ETHIOPIA|ETHIOPI|"
    r"SOUTH\s+SUDAN|SOUTH|SUDAN|KENYA|RWANDA|BURUNDI|KAMPALA|JUBA|ARUSHA|ADDIS\s+ABABA|"
    r"U|T|E|EAST\s+AFRICA|EA|E\.A))+\s*$"
)
# ...but keep it when the place IS the name: "BANK OF UGANDA", "EMBASSY OF INDIA"
KEEP_PLACE_RE = re.compile(r"(?:^|\s)(?:OF|FOR|IN|DE|DU|BANK|EMBASSY|GOVERNMENT|REPUBLIC)$")

NOT_A_NAME = re.compile(
    r"^(?:N\s*/?\s*A|NIL|NONE|NULL|UNKNOWN|TBA|TBC|SAME\s+AS\s+CONSIGNEE|SAME|ORDER|"
    r"TO\s+ORDER|BANK|CONSIGNEE|CUSTOMER|NAME|DUMMY|[A-Z])$"
)

# --------------------------------------------------------------------------- #
#  Matching
# --------------------------------------------------------------------------- #

# ignored when comparing two names
NOISE_WORDS = {"LTD", "CO", "PLC", "SMC", "INC", "LLC", "CORP", "GMBH", "SARL",
               "PVT", "PTE", "PTY", "THE", "&", "AND", "(U)", "(T)", "(E)"}
# misspelt legal words: LIMIITED, COLTD, CORPORATON ...
LEGAL_TYPO_RE = re.compile(r"^(?:CO)?LI?M+I*U?T*E*D+[A-Z]?$|^IMITED$|^COLTD$|^LTD[A-Z]{0,2}$|"
                           r"^COMPANY?$|^CORPN?$|^CORPORA\w*$|^COPRO\w*$|^LIMI\w*$")
# country words are ignored only when they are NOT the first word, so
# "UGANDA GLASSWORKS" and "TANZANIA GLASSWORKS" stay different
PLACE_WORDS = {"UGANDA", "TANZANIA", "ETHIOPIA", "SOUTH", "SUDAN", "EAST", "AFRICA",
               "EA", "KENYA", "U", "T", "E", "UG", "TZ", "SA", "RWANDA"}
PLACE_LONG = ("UGANDA", "TANZANIA", "ETHIOPIA", "SUDAN", "KENYA", "AFRICA", "RWANDA")

# single words too generic to stand for one company (family-merge guard)
COMMON_WORDS = {
    "AFRICA", "AFRICAN", "AFRO", "AGRO", "ALPHA", "AMERICAN", "ASIA", "ASIAN", "BEST", "BLUE",
    "CAPITAL", "CENTRAL", "CHINA", "CHINESE", "CITY", "COMMODITY", "COMMODITIES", "CROWN",
    "DIAMOND", "DOUBLE", "DREAM", "EAGLE", "EAST", "EASTERN", "ELITE", "EMPIRE", "EURO",
    "EVERY", "FIRST", "FUTURE", "GENERAL", "GLOBAL", "GOLD", "GOLDEN", "GRAND", "GREAT",
    "GREEN", "GULU", "HAPPY", "HOPE", "IMPACT", "INDIA", "INDIAN", "INTERNATIONAL", "JUBA",
    "KAMPALA", "KING", "KINGS", "LIBERTY", "LION", "MEGA", "MODERN", "MOUNT", "NATIONAL",
    "NEW", "NILE", "NORTH", "NORTHERN", "OCEAN", "PEARL", "PREMIER", "PRIME", "QUALITY",
    "RED", "ROYAL", "SILVER", "SKY", "SOUTH", "SOUTHERN", "STAR", "SUN", "SUPER", "SUPREME",
    "TOP", "TOTAL", "TRUST", "UGANDA", "UNION", "UNITED", "UNIVERSAL", "VICTORIA", "VILLA",
    "VISION", "WEST", "WESTERN", "WORLD", "ZION", "JINJA", "MBALE", "MBARARA", "ARUA",
    "LIRA", "MASAKA", "HOIMA", "KASESE", "TORORO", "ENTEBBE", "ANKOLE", "BUSOGA", "KIGEZI",
    "ELGON", "RWENZORI", "TANZANIA", "ETHIOPIA", "KENYA", "SUDAN", "NAIROBI", "MOMBASA",
    "DUBAI", "BEIJING", "SHANGHAI", "TRADING", "TRADERS", "INVESTMENTS", "ENTERPRISES",
    "SOLUTIONS", "SUPPLIES", "SERVICES", "MOTORS", "AUTO", "FAMILY", "BROTHERS", "SONS",
}
