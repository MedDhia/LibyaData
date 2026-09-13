#!/usr/bin/env python3
"""
Code HNEC's municipal council decisions, and geocode them.

Input is the post collection gathered by `scripts/download_hnec_municipal.py`.

## Why this is the subnational half of the officeholder record

The Official Gazette records appointments to national offices and, as
`data/processed/gazette/` reports, resolves to no Libyan province at all. The
municipal councils are the opposite: every decision names a baladiya, so this is
where the officeholder record acquires geography.

HNEC runs the municipal rounds in numbered groups (المجموعة الأولى, الثانية,
الثالثة) and publishes each step as a numbered council decision. The one that
constitutes a council is `تشكيل المجلس البلدي (X)`, and those are the
appointments; the rest are the electoral process around them, kept because a
council's formation date means little without the polling day and the results
adoption it followed.

## What is missing, and why it is recorded as missing

The **names of the elected members are not here**. HNEC publishes each decision
as a page scan, a JPG in the post body or a PDF with no text layer: the group 1
and group 2 final results run to 57 and 35 scanned pages. Reading them needs
optical character recognition of Arabic, which this repository has already tried
and failed at on gridded Libyan documents. `members_listed` is 0 on every row
and `scan_url` points at the image, so the gap is stated and addressable rather
than papered over.

## Geocoding

Municipalities are taken from the bracketed span of the title, which is where
HNEC puts them, singly or as a list separated by dashes. Each is resolved
through `scripts/libya_places.py` against this repository's own concordance, so
a municipality named here is one the mahalla and baladiya concordances already
know. A bracket holding a group name rather than a place simply resolves to
nothing.

One municipality does not resolve and is left empty rather than guessed:
الجديدة, whose name occurs as a mahalla in more than one shabiya, is excluded
from the gazetteer for exactly that reason.

Outputs, under data/processed/municipal/:
  municipal_decisions.csv   one row per HNEC decision, coded and dated
  municipal_councils.csv    one row per council formed, with its shabiya
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import normalise_name  # noqa: E402
from libya_places import gazetteer, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hnec" / "municipal_posts.json"
OUT = ROOT / "data" / "processed" / "municipal"

DECISION = re.compile(r"قرار\s*(?:مجلس\s*المفوضية\s*)?ر(?:قم|فم)\s*\(?\s*(\d{1,4})\s*\)?"
                      r"(?:\s*لسنة\s*(\d{4}))?")
# HNEC puts the municipalities in brackets, singly or as a dashed list.
BRACKET = re.compile(r"[(（]([^)）]{2,120})[)）]")
SPLIT = re.compile(r"\s*[–—\-،,]\s*|\s+و(?=\S)")
GROUP = re.compile(r"المجموعة\s*/?\s*(الأولى|الاولى|الثانية|الثالثة|الرابعة)")
# Brackets hold more than municipalities: a decision number, a year, a group, a
# count of municipalities, or an ordinal as in التمديد (الثاني).
NOT_A_PLACE = re.compile(r"^(?:[\d\W_]+|المجموعة.*|ال?(?:أول|اول|ثاني|ثالث|رابع)"
                         r"(?:ة|ى)?)$")
ORDINAL = {"الأولى": 1, "الاولى": 1, "الثانية": 2, "الثالثة": 3, "الرابعة": 4}

# Act taxonomy, most specific first: a final-results decision also contains the
# word "نتائج", so order decides.
ACTS = [
    ("تشكيل المجلس البلدي", "council_formation"),
    ("النتائج النهائية", "final_results"),
    ("النتائج الأولية", "preliminary_results"),
    ("حجب", "results_withheld"),
    ("القرعة", "tie_break_draw"),
    ("استبعاد", "candidate_exclusion"),
    ("القائمة النهائية", "final_candidate_list"),
    ("القوائم النهائية", "final_candidate_list"),
    ("القائمة الأولية", "preliminary_candidate_list"),
    ("القوائم الأولية للمترشحين", "preliminary_candidate_list"),
    ("القوائم الأولية للناخبين", "preliminary_voter_list"),
    ("حملات الدعاية", "campaign_start"),
    ("يوم الاقتراع", "polling_day"),
    ("تسجيل الناخبين", "voter_registration"),
    ("تعليق", "suspension"),
    ("تنفيذ انتخابات", "round_launch"),
    ("اللائحة التنفيذية", "regulation_amendment"),
]


def act_of(title):
    for phrase, label in ACTS:
        if phrase in title:
            return phrase, label
    return "", ""


def municipalities(title, places, shabiya_keys, scrambled):
    """Places named in the title's brackets, resolved to a shabiya."""
    found = []
    for span in BRACKET.findall(title):
        for piece in SPLIT.split(span):
            piece = normalise_name(piece.strip(" .:؛"))
            if len(piece) < 3 or GROUP.search(piece) or NOT_A_PLACE.match(piece):
                continue
            place = resolve(piece, places, shabiya_keys, scrambled)
            if place:
                found.append((piece, place))
            else:
                found.append((piece, None))
    # Keep the order but drop repeats.
    seen, out = set(), []
    for name, place in found:
        if name not in seen:
            seen.add(name)
            out.append((name, place))
    return out


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if not RAW.exists():
        sys.exit(f"missing {RAW}. Run scripts/download_hnec_municipal.py first.")
    collection = json.loads(RAW.read_text())
    places, shabiya_keys, scrambled = gazetteer()
    print(f"gazetteer: {len(places)} Arabic keys, article variants included")

    decisions, councils = [], []
    for post in collection["posts"]:
        title = post["title"]
        numbered = DECISION.search(title)
        if not numbered:
            continue
        phrase, act = act_of(title)
        group = GROUP.search(title)
        named = municipalities(title, places, shabiya_keys, scrambled)
        scan = (post["pdfs"] or post["images"] or [""])[0]

        record = {
            "decision_number": numbered.group(1),
            "decision_year": numbered.group(2) or post["date"][:4],
            "decided": post["date"][:10],
            "act_ar": phrase,
            "act_en": act,
            "electoral_group": ORDINAL.get(group.group(1), "") if group else "",
            "municipalities_named": len([n for n, p in named if p]),
            "municipalities_ar": ";".join(n for n, _ in named),
            "title": title,
            "post_id": post["id"],
            "link": post["link"],
            "decision_text_available": 0,
            "scan_url": scan,
            "publishing_authority": "High National Elections Commission",
        }
        decisions.append(record)

        if act != "council_formation":
            continue
        for name, place in named:
            councils.append({
                "baladiya_ar": name,
                "shabiya_ar": place[0] if place else "",
                "shabiya_en": place[1] if place else "",
                "shabiya_pcode": place[2] if place else "",
                "matched_level": place[3] if place else "unresolved",
                "decision_number": record["decision_number"],
                "decision_year": record["decision_year"],
                "formed": record["decided"],
                "electoral_group": record["electoral_group"],
                "members_listed": 0,
                "scan_url": scan,
                "post_id": post["id"],
                "link": post["link"],
                "publishing_authority": record["publishing_authority"],
            })

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "municipal_decisions.csv", decisions)
    write(OUT / "municipal_councils.csv", councils)
    report(collection, decisions, councils)


def write(path, rows):
    if not rows:
        print(f"{path.name:30s} no rows")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:30s} {len(rows):5d} rows")


def report(collection, decisions, councils):
    print(f"\n{len(collection['posts'])} posts, {len(decisions)} numbered decisions, "
          f"{decisions[0]['decided']} to {decisions[-1]['decided']}")
    print("acts:   ", dict(Counter(d["act_en"] or "(uncoded)"
                                   for d in decisions).most_common()))
    print("groups: ", dict(Counter(d["electoral_group"] or "(none)"
                                   for d in decisions).most_common()))
    placed = [c for c in councils if c["shabiya_en"]]
    print(f"\ncouncils formed: {len(councils)}, {len(placed)} resolved to a shabiya")
    print("  by shabiya:", dict(Counter(c["shabiya_en"] for c in placed)))
    unresolved = [c["baladiya_ar"] for c in councils if not c["shabiya_en"]]
    if unresolved:
        print("  unresolved:", unresolved)
    print(f"\nevery council carries members_listed=0: the decisions are page scans")
    print("next: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
