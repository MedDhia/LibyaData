#!/usr/bin/env python3
"""
Find Libyan places in Arabic text, and name the shabiya they sit in.

Shared by the gazette and municipal-council extractors, because both read
Arabic published by Libyan institutions and both must resolve a place name the
same way or their outputs will not join.

The gazetteer is built from this repository's own concordance rather than an
external list, so a place resolved here is a place the rest of the repository
already knows: the 22 shabiyat, the municipalities the concordance placed in
one, and the mahallas whose name occurs in exactly one shabiya. Mahalla names
that repeat nationally are left out, because a name that could mean two
provinces is worse than no name.

Four defences against inventing geography, each of which was put in after the
matching produced something false:

  * **Minimum length.** A folded key shorter than four characters matches only
    when it is one of the 22 shabiyat. سرت and غات are real and unambiguous;
    بدر, بشر and درج are ordinary Arabic words that happen also to be mahallas.
  * **The marker rule.** Outside the 22 shabiyat a place counts only when a
    place-signalling word (بلدية, مدينة, منطقة, محلة, شعبية) stands immediately
    before it. Without it المحكمة العليا matches العليا, a mahalla in Jabal al
    Gharbi, and national court decisions acquire a province.
  * **The definite article.** Libyan sources write the same municipality with
    and without ال: HNEC's decisions name الصياد, the concordance has صياد. Each
    name therefore gets its opposite-article form as an alias, but only where
    that form is not already another place and does not point at two. One
    collision exists over the 663 names, حمدة in Marj and الحمدة in Nuqat al
    Khams, and it is dropped rather than resolved.
  * **The anagram fallback.** Libyan institutional PDFs embed fonts that
    transpose letters inside a word: طبرق prints as طربق, المغربية as املغربية,
    مجلس as جملس. Character folding cannot repair an ordering error, so a phrase
    that fails the exact match is retried on its letters sorted. The 663 names
    yield 655 anagram keys; the handful that collide are excluded, so the
    fallback never chooses between two provinces.
"""

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import normalise_name  # noqa: E402

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"

# A place name shorter than this matches only if it is a shabiya.
MIN_KEY = 4
# Words after which a place name is a place and not a coincidence.
PLACE_MARKERS = ("بلدية", "مدينة", "منطقة", "محلة", "شعبية", "بلديات", "مدن")


def fold(text):
    """Fold spelling drift and the fonts' letter substitutions.

    The same fold `build_concordance.join_key` uses, minus the article strip:
    alef and ya variants, ta marbuta, spacing, and lam-alef written the wrong
    way round.
    """
    text = normalise_name(str(text))
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"[ىي]", "ي", text)
    text = text.replace("ة", "ه")
    text = re.sub(r"\s+", "", text)
    return text.replace("لا", "ال")


def anagram(text):
    """Letters of the folded form, sorted, to survive letter transposition."""
    return "".join(sorted(fold(text)))


def gazetteer():
    """Return (places, shabiya keys, anagram index) keyed on the folded name."""
    def read(name):
        path = PROCESSED / name
        if not path.exists():
            sys.exit(f"missing {path}. Run scripts/build_concordance.py first.")
        with path.open() as fh:
            return list(csv.DictReader(fh))

    places = {}
    for row in read("concordance_shabiya.csv"):
        places[fold(row["shabiya_ar"])] = (row["shabiya_ar"], row["shabiya_en"],
                                           row["codab_pcode"], "shabiya")
    by_arabic = {p[0]: p for p in places.values()}

    for row in read("concordance_baladiya.csv"):
        parent = by_arabic.get(row["shabiya_ar"])
        if parent:
            places.setdefault(fold(row["baladiya_ar"]), parent[:3] + ("baladiya",))

    mahallas = read("concordance_mahalla.csv")
    repeated = Counter(fold(r["mahalla_ar"]) for r in mahallas)
    for row in mahallas:
        key = fold(row["mahalla_ar"])
        parent = by_arabic.get(row["shabiya_ar"])
        if repeated[key] == 1 and parent:
            places.setdefault(key, parent[:3] + ("mahalla",))

    shabiya_keys = {k for k, v in places.items() if v[3] == "shabiya"}

    by_anagram = defaultdict(set)
    for key, value in places.items():
        by_anagram[anagram(key)].add(value[0])
    scrambled = {}
    for key, value in places.items():
        code = anagram(key)
        if len(by_anagram[code]) == 1:
            scrambled.setdefault(code, value)

    # Alias each name to its opposite-article form, after the anagram index, so
    # an alias can never displace a real name there. An alias that is already a
    # place of its own, or that two places would claim, is dropped.
    aliases = defaultdict(set)
    for key, value in places.items():
        other = key[2:] if key.startswith("ال") else "ال" + key
        if other and other not in places:
            aliases[other].add(value)
    for other, claimants in aliases.items():
        if len({c[0] for c in claimants}) != 1:
            continue
        places[other] = claimants.pop()
        if places[other][3] == "shabiya":
            shabiya_keys.add(other)

    return places, shabiya_keys, scrambled


def usable(key, shabiya_keys):
    """Is this folded key long enough to trust?"""
    return len(key) >= MIN_KEY or key in shabiya_keys


def resolve(phrase, places, shabiya_keys, scrambled=None):
    """Resolve one already-isolated place name, with no marker required.

    For text that is known to be a place: a municipality in brackets, or the
    city in a signature block.
    """
    key = fold(phrase)
    if not usable(key, shabiya_keys):
        return None
    return places.get(key) or (scrambled or {}).get(anagram(phrase))


def locate(text, places, shabiya_keys, scrambled=None, require_marker=True):
    """Find a place inside free Arabic text.

    Longest phrase first, so وادي الشاطئ is not shadowed by وادي.
    """
    scrambled = scrambled or {}
    words = [w for w in re.split(r"[\s،,./()\"'“”]+", str(text)) if w]
    for size in range(4, 0, -1):
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start:start + size])
            key = fold(phrase)
            if not usable(key, shabiya_keys):
                continue
            found = places.get(key) or scrambled.get(anagram(phrase))
            if not found:
                continue
            if (key in places and key in shabiya_keys) or not require_marker:
                return found, phrase
            before = fold(words[start - 1]) if start else ""
            if any(fold(marker) in before for marker in PLACE_MARKERS):
                return found, phrase
    return None, ""
