"""
Stage 2 - matching: group cleaned names that refer to the same customer.

Every cleaned name is reduced to a *match key* (no legal words, no country
tags, no punctuation). Keys are then clustered with a leader algorithm:
names are processed from most to least frequent, and each one either joins
an existing standard name or becomes a new one.

A key joins an existing standard name when, in this order:
  1. the key is identical                     ACME TRADING  = ACME TRADING
  2. it is identical without spaces           ACMETRADING   = ACME TRADING
  3. it is a longer version of a known key    ACME TRADING KISENYI BRANCH
  4. it is a cut-off version of a known key   SUNRISE PLASTICS INDUS
  5. it is a typo-level variant (guarded)     ACME TRADNIG
Afterwards a guarded "family" pass folds bare first words into the dominant
company (TWIGA -> TWIGA AUTO SPARES LTD).

Every rule is biased towards precision: wrongly merging two different
customers corrupts every number built on top, while a missed merge is
visible in the review file and fixed in seconds.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from rapidfuzz import fuzz, process
from rapidfuzz.distance import OSA

from . import rules as R


def _is_place(t: str) -> bool:
    """UGANDA and its typos (UGNDA, UGANADA, UGAND ...)."""
    if t in R.PLACE_WORDS:
        return True
    return len(t) >= 5 and any(OSA.distance(t, p) <= 1 or p.startswith(t) for p in R.PLACE_LONG)


def match_key(name: str) -> str:
    """The part of a name that identifies the customer.
    'SUNRISE PLASTICS INDUSTRIES (U) LTD' -> 'SUNRISE PLASTICS INDUSTRIES'."""
    s = re.sub(r"[^A-Z0-9&() ]", " ", name)
    s = re.sub(r"[()]", " ", s.replace("(U)", " ").replace("(T)", " ").replace("(E)", " "))
    s = re.sub(r"\bA Z\b", "A TO Z", s)        # "A-Z HARDWARE" = "A TO Z HARDWARE"
    # a country glued to the word before it: "COUGANDA", "ENTERPRISESUGANDA"
    s = re.sub(r"\b([A-Z]{2,})(" + "|".join(R.PLACE_LONG) + r")\b", r"\1 \2", s)
    toks = [t for t in s.split() if t not in R.NOISE_WORDS and not R.LEGAL_TYPO_RE.match(t)]
    # "AND" glued to a generic word: "FORWARDING ANDCLEARING"
    toks = [t[3:] if t.startswith("AND") and t[3:] in R.GENERIC_WORDS else t for t in toks]

    def in_initials(i):           # keep U / T / E inside initials: "L E M", "A T C"
        return len(toks[i - 1]) == 1 or (i + 1 < len(toks) and len(toks[i + 1]) == 1)

    # Place words are noise only at the END of a name ("... PLASTICS UGANDA",
    # "... U"). In the middle they are part of the name ("NORTH EAST LOGISTICS"),
    # and they are kept as first word or after OF/IN ("BANK OF UGANDA").
    while len(toks) > 1:
        i = len(toks) - 1
        t = toks[i]
        if toks[i - 1] in ("OF", "IN") or not _is_place(t) or (len(t) == 1 and in_initials(i)):
            break
        toks.pop()
    return " ".join(toks) if toks else " ".join(s.split())


def squash(k: str) -> str:
    return k.replace(" ", "")


def is_generic(key: str) -> bool:
    """A short key (1-2 words) made only of generic business words:
    'GENERAL TRADING', 'UNITED NATIONS'. Such a name does not identify one
    customer, so it never absorbs longer names on its own."""
    toks = key.split()
    return len(toks) <= 2 and all(t in R.GENERIC_WORDS for t in toks)


def _noise_extra(toks: list) -> bool:
    """Extra words that add nothing: JOINTLY, GROUP, OFFICE, numbers, places."""
    return all(t in R.EXTRA_NOISE or len(t) <= 2 or re.search(r"\d", t) or _is_place(t)
               for t in toks)


def person_like(name: str) -> bool:
    """Could be a personal name: no legal suffix and no business word."""
    return not R.HAS_LEGAL_RE.search(name) and \
        not any(t in R.GENERIC_WORDS for t in re.findall(r"[A-Z]+", name))


def word_order_key(k: str) -> str | None:
    """Sorted words of a 2-3 word key without digits: 'MUSISI PETER' and
    'PETER MUSISI' -> 'MUSISI PETER'. Only used for personal names (see
    person_like), which are often written surname-first."""
    toks = k.split()
    if 2 <= len(toks) <= 3 and all(len(t) >= 3 for t in toks) and not re.search(r"\d", k):
        return " ".join(sorted(toks))
    return None


def typo_only(a: str, b: str) -> bool:
    """True when keys a and b differ only by typo-sized edits in each word.
    Blocks look-alikes such as SUNRISE TRADING / SUNSET TRADING,
    PETER MUGISHA / PETER MUSISI, ROADTECH GROUP 18 / ROADTECH GROUP 21 and
    JOHN OKELLO / JOHN B OKELLO."""
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return False
    ta, tb = a.split(), b.split()
    if len(ta) == len(tb):
        return _words_typo(ta, tb)
    if abs(len(ta) - len(tb)) != 1:
        return False
    # one word written as two ("KAMBA COFFEE" / "KAMBACOFFEE" + a typo): join a
    # neighbouring pair of real words and compare word by word. Initials are
    # never joined, so an extra initial or word is a different name.
    longer, shorter = (ta, tb) if len(ta) > len(tb) else (tb, ta)
    for i in range(len(longer) - 1):
        if len(longer[i]) >= 2 and len(longer[i + 1]) >= 2:
            joined = longer[:i] + [longer[i] + longer[i + 1]] + longer[i + 2:]
            if _words_typo(joined, shorter):
                return True
    return False


def _words_typo(ta: list, tb: list) -> bool:
    if fuzz.ratio(ta[0], tb[0]) < 75:
        return False
    for x, y in zip(ta, tb):
        if x == y:
            continue
        n = max(len(x), len(y))
        allowed = 0 if n <= 3 else 1 if n <= 8 else 2 if n <= 12 else 3
        if OSA.distance(x, y) > allowed:          # swapped letters count as 1 edit
            return False
        if n <= 6 and x[0] != y[0]:
            return False
    return True


class Grouper:
    """Leader clustering over match keys with several indexes for speed
    (172k names cluster in ~10 s)."""

    def __init__(self):
        self.leader_of_key: dict[str, str] = {}       # key -> standard name
        self.squash_idx: dict[str, str] = {}          # squashed key -> std
        self.blocks: dict[str, list] = defaultdict(list)   # first letter -> leader keys
        self.block_std: dict[str, list] = defaultdict(list)
        self.prefix_idx: dict[str, str] = {}          # character prefix of a leader key -> std
        self.token_idx: dict[str, str] = {}           # leader key -> std
        self.leader_squash: dict[str, str] = {}       # squashed leader key -> std
        self.order_idx: dict[str, str] = {}           # word-order key -> std
        self.order_blocks: dict[str, list] = defaultdict(list)
        self.order_std: dict[str, list] = defaultdict(list)

    @staticmethod
    def _block(k: str) -> str:
        return squash(k)[:1]

    def add_leader(self, std: str, key: str):
        if key in self.token_idx:
            return
        self.token_idx[key] = std
        self.leader_squash.setdefault(squash(key), std)
        ok = word_order_key(key) if person_like(std) else None
        if ok and ok not in self.order_idx:
            self.order_idx[ok] = std
            self.order_blocks[ok[:1]].append(ok)
            self.order_std[ok[:1]].append(std)
        self.leader_of_key.setdefault(key, std)
        self.squash_idx.setdefault(squash(key), std)
        b = self._block(key)
        self.blocks[b].append(key)
        self.block_std[b].append(std)
        if len(key) >= 12:
            for n in range(12, len(key)):
                self.prefix_idx.setdefault(key[:n], std)

    def remember(self, key: str, std: str):
        self.leader_of_key.setdefault(key, std)
        self.squash_idx.setdefault(squash(key), std)

    def find(self, key: str, cleaned: str | None = None):
        """Return (standard name, score) or (None, 0)."""
        if key in self.leader_of_key:
            return self.leader_of_key[key], 100
        sq = squash(key)
        if sq in self.squash_idx:
            return self.squash_idx[sq], 99
        toks = key.split()
        # longer version of a known name (also with different spacing); a
        # generic name ("GENERAL TRADING") never absorbs longer names
        for n in range(len(toks) - 1, 1, -1):
            p = " ".join(toks[:n])
            if len(p) >= 10 and (not is_generic(p) or _noise_extra(toks[n:])):
                if p in self.token_idx:
                    return self.token_idx[p], 95
                if squash(p) in self.leader_squash:
                    return self.leader_squash[squash(p)], 94
        # cut-off version of a known name
        if len(key) >= 12 and key in self.prefix_idx and not is_generic(key):
            return self.prefix_idx[key], 95
        # same 2-3 words in another order (+ a typo): MUSISI PETER = PETER MUSISI,
        # for personal names only (GOLD RIVER LTD and RIVER GOLD LTD stay apart)
        ok = word_order_key(key) if person_like(cleaned or key) else None
        if ok:
            if ok in self.order_idx:
                return self.order_idx[ok], 93
            cands = self.order_blocks.get(ok[:1])
            if cands:
                for other, score, idx in process.extract(ok, cands, scorer=fuzz.ratio,
                                                         score_cutoff=R.FUZZY_THRESHOLD, limit=3):
                    if min(len(ok), len(other)) >= 9 and typo_only(ok, other):
                        return self.order_std[ok[:1]][idx], int(score)
        # typo-level spelling difference, guarded word by word
        b = self._block(key)
        cands = self.blocks.get(b)
        if cands:
            for other, score, idx in process.extract(key, cands, scorer=fuzz.ratio,
                                                     score_cutoff=R.FUZZY_THRESHOLD, limit=5):
                if typo_only(key, other) and (min(len(key), len(other)) >= 9 or score >= 96):
                    return self.block_std[b][idx], int(score)
        return None, 0

    def assign(self, cleaned: str):
        key = match_key(cleaned)
        if cleaned in R.ALIAS_NAMES:                  # fixed names from rules.ALIASES
            self.add_leader(cleaned, key)
            self.leader_of_key[key] = cleaned
            return cleaned, 100
        std, score = self.find(key, cleaned)
        if std is None:
            self.add_leader(cleaned, key)
            return cleaned, 100
        self.remember(key, std)
        return std, score


def pick_display(members: Counter) -> str:
    """Choose the standard spelling for a group of cleaned names: the most
    frequent one, preferring its full legal form when that is nearly as common,
    or a shorter complete form when that is itself common."""
    top = max(members.items(), key=lambda x: (x[1], -len(x[0])))[0]
    if R.LEGAL_RE.search(top):
        return top
    top_n = members[top]
    top_key = match_key(top).split()
    legal = [(n, m) for m, n in members.items()
             if R.LEGAL_RE.search(m) and match_key(m).split() == top_key and n >= 0.4 * top_n]
    if legal:
        return max(legal)[1]
    best = None
    for name, n in members.items():
        k = match_key(name).split()
        if 2 <= len(k) < len(top_key) and top_key[:len(k)] == k and n >= 0.25 * top_n:
            if best is None or len(k) < len(match_key(best).split()) or \
                    (len(k) == len(match_key(best).split()) and n > members[best]):
                best = name
    if best:
        bk = match_key(best)
        same = {m: c for m, c in members.items() if match_key(m) == bk}
        return max(same.items(), key=lambda x: x[1])[0]
    return top


def family_merges(vol: Counter, keep: set) -> dict:
    """Fold bare / shortened variants into the dominant company that shares
    their first word: TWIGA -> TWIGA AUTO SPARES LTD.
    Guards: one key must be a word-for-word prefix of the other; the main name
    must own FAMILY_SHARE of the family's rows (so CHINA..., GENERAL...
    families never merge); a name with its own legal suffix is a complete
    company, not a fragment; generic single words never merge; extra words
    must not contain numbers. Names in `keep` are never renamed."""
    keyof = {s: match_key(s).split() for s in vol}
    fams = defaultdict(list)
    for s, k in keyof.items():
        if k and len(k[0]) >= 3:
            fams[k[0]].append(s)
    out = {}
    for fam in fams.values():
        if len(fam) < 2:
            continue
        tot = sum(vol[s] for s in fam)
        dom = max(fam, key=lambda s: (vol[s], s in keep))
        if vol[dom] < R.FAMILY_SHARE * tot:
            continue
        dk = keyof[dom]
        for s in fam:
            if s == dom or s in keep or vol[s] > vol[dom] or R.HAS_LEGAL_RE.search(s):
                continue
            k = keyof[s]
            short, long_ = (k, dk) if len(k) <= len(dk) else (dk, k)
            if long_[:len(short)] != short:
                continue
            if len(short) == 1 and (len(short[0]) < 4 or short[0] in R.COMMON_WORDS):
                continue                             # bare "ANKOLE", "GULU", "GLOBAL"
            if is_generic(" ".join(short)) and not _noise_extra(long_[len(short):]):
                continue                             # GLOBAL, UNITED NATIONS ...
            if any(re.search(r"\d", w) for w in long_[len(short):]):
                continue
            out[s] = dom
    return out


def group_names(freq: Counter, g: Grouper, existing_std: set = frozenset(),
                existing_vol: Counter | None = None) -> dict:
    """{cleaned name: rows} -> {cleaned name: (standard name, score)}.
    Standard names already known (existing_std) are never renamed."""
    res = {}
    for c, _ in sorted(freq.items(), key=lambda x: (-x[1], len(x[0]))):
        res[c] = g.assign(c)
    vol = Counter(existing_vol or {})
    for c, (std, _) in res.items():
        vol[std] += freq[c]
    fm = family_merges(vol, set(existing_std) | R.ALIAS_NAMES)
    if fm:
        res = {c: ((fm[s], min(sc, 90)) if s in fm else (s, sc)) for c, (s, sc) in res.items()}
    members = defaultdict(Counter)
    for c, (std, _) in res.items():
        if std not in existing_std:
            members[std][c] += freq[c]
    renames = {}
    for std, mem in members.items():
        if std in R.ALIAS_NAMES:
            continue
        disp = pick_display(mem)
        if disp != std:
            renames[std] = disp
    if renames:
        res = {c: (renames.get(s, s), sc) for c, (s, sc) in res.items()}
    return res
