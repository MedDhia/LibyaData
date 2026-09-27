#!/usr/bin/env python3
"""
Table II of the 1931 census: Libya by district, transcribed from the page.

Source: Istituto Centrale di Statistica, `VII Censimento generale della
popolazione 1931, Volume V, Colonie e Possedimenti`, Tavola II, `Popolazione
presente in complesso, regnicola, straniera e indigena, secondo il sesso`,
printed page 12 for Tripolitania and page 24 for Cirenaica.

## Why this one is transcribed and not read

`scripts/extract_istat_1931_libya.py` publishes table I of the same two pages
and says table II could not be read: the OCR runs the label and the first two
figures into one string, so a line arrives as `C. R. DI TRIPOLI (2).
81.98638.444 21.47`, and the figures can be split apart but then have no column
to belong to. That was true and stays true. What changed is the method: the
pages were rendered as images and read by eye, which is also how
`libya_annuario_trade.csv` was made.

The transcription is the source here, committed as
`data/raw/istat/libya_1931_table2_*.csv`, and this script validates and
publishes it. It is not a parser and will not recover if the transcription is
wrong; what it does instead is check the transcription against arithmetic the
table itself supplies, and refuse to publish if any of it fails.

## The four checks, which are what makes a hand transcription trustworthy

The table is a hierarchy. A Commissariato Regionale or Comando di Zona contains
Circondari, a Circondario contains Distretti, and every row splits its
population four ways and by sex. So a misread digit has nowhere to hide:

  components   present = regnicola + straniera + indigena, on every row, both
               for the whole population and for women alone
  sexes        the female count never exceeds the total
  hierarchy    every parent equals the sum of the children printed under it
  colony       the eleven Tripolitanian and four Cirenaican circumscriptions
               sum to the colony total the table prints

Together these bind about 850 figures to each other. Two errors survived the
first reading of Tripolitania and both were caught: a `4/3` that the parent and
the component check together forced to `4/1`. Cirenaica passed on the first
pass. Nothing here is published that does not satisfy all four.

## What it adds to table I

Table I stops at the circumscription: eleven rows for Tripolitania, four for
Cirenaica. This goes two levels further, to 79 and 27 rows, and adds the
**sex breakdown** that table I does not carry at all. It also **repairs table
I**: the scan destroyed four of table I's foreign-population cells and one of
its totals, and those figures are printed again here, undamaged.

`level` is `commissariato` for a Commissariato Regionale or Comando di Zona,
`circondario`, `distretto`, or `colony` for the total line. Adding levels
together double-counts; filter to one.

Outputs, under data/processed/istat/:
  libya_1931_districts.csv   one row per circumscription, circondario, district
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1936_localities import (  # noqa: E402
    SEATS, SEAT_SHABIYA, SPECIFIC)
from libya_places import gazetteer, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
SOURCES = {"Tripolitania": RAW / "libya_1931_table2_tripolitania.csv",
           "Cirenaica": RAW / "libya_1931_table2_cirenaica.csv"}

GROUPS = ("present", "regnicola", "straniera", "indigena")
LEVELS = {"0": "colony", "1": "commissariato", "2": "circondario",
          "3": "distretto"}

# The Arabic name each district transliterates, for the ones the 1936 seat list
# does not already carry. The shabiya is never asserted from this table: the
# name is looked up in the repository's own concordance, and a district that
# does not resolve is published unplaced rather than guessed at.
ARABIC = {
    "el-hassa": "الحشان", "regdalin": "رقدالين", "el-agelat": "العجيلات",
    "el-alalga": "العلالقة", "es-sahel": "الساحل",
    "gasr garabulli": "قصر خيار", "gasr el-chiar": "قصر خيار",
    "sciogran": "سوق الخميس", "sugh el-chemis": "سوق الخميس",
    "el-gusbat": "القصبات", "tauorga": "تاورغاء", "er-rogeban": "الرجبان",
    "er-rehibat": "الرحيبات", "ez-zintan": "الزنتان", "er-riaina": "الرياينة",
    "en-nofilia": "النوفلية", "giofra": "الجفرة", "socna": "سوكنة",
    "uaddan": "ودان", "hon": "هون", "zella": "زلة", "orfella": "بني وليد",
    "haraba": "الحرابة", "cabao": "كاباو", "el-giosc": "الجوش",
    "sinauen": "سيناون", "derg": "درج", "umm el-araneb": "أم الأرانب",
    "edri": "إدري", "berghin": "برقن", "traghen": "تراغن",
    "bengasi esterna": "بنغازي", "el-abiar": "الأبيار", "soluch": "سلوق",
    "sidi ahmed el-magrun": "سيدي أحمد المقرون", "tolmeta": "طلميثة",
    "tocra": "توكرة", "apollonia": "سوسة", "cirene": "شحات",
    "tobruch": "طبرق", "porto bardia": "البردية", "agedabia": "أجدابيا",
    "marsa brega": "مرسى البريقة", "el-agheila": "العقيلة", "gialo": "جالو",
    "cufra": "الكفرة", "barce": "المرج", "zuara": "زوارة",
    "sabratha": "صبراتة", "sorman": "صرمان", "zavia": "الزاوية",
    "zanzur": "جنزور", "tagiura": "تاجوراء", "el-azizia": "العزيزية",
    "castel benito": "بن غشير", "homs": "الخمس", "zliten": "زليتن",
    "misurata": "مصراتة", "giado": "جادو", "iefren": "يفرن",
    "el-garian": "غريان", "tarhuna": "ترهونة", "sirte": "سرت",
    "mizda": "مزدة", "nalut": "نالوت", "gadames": "غدامس", "sebha": "سبها",
    "brach": "براك", "murzuch": "مرزق", "gat": "غات", "derna": "درنة",
    "tripoli": "طرابلس", "bengasi": "بنغازي",
}

# Districts the concordance does not carry under any spelling, with the modern
# province each sits in. These are **asserted**, not matched: the 2006 mahalla
# list is a list of neighbourhoods and does not hold every colonial district
# seat, so Zliten, Sabratha, Ajdabiya and the Fezzan oases have to be placed by
# where they are rather than by a name the concordance shares. Every row placed
# this way says `asserted`, and a user who will not take an assertion can drop
# them in one filter.
DISTRICT_SHABIYA = {
    "agedabia": "الواحات", "gialo": "الواحات", "marsa brega": "الواحات",
    "el-agheila": "الواحات",
    "zliten": "المرقب", "gasr el-chiar": "المرقب",
    "gasr garabulli": "المرقب", "sciogran": "المرقب",
    "sugh el-chemis": "المرقب",
    "sabratha": "الزاوية", "el-alalga": "الزاوية",
    "el-hassa": "النقاط الخمس", "regdalin": "النقاط الخمس",
    "er-rogeban": "الجبل الغربي", "ez-zintan": "الجبل الغربي",
    "er-rehibat": "الجبل الغربي", "er-riaina": "الجبل الغربي",
    "derg": "نالوت", "cabao": "نالوت", "haraba": "نالوت",
    "el-giosc": "نالوت", "sinauen": "نالوت",
    "orfella": "مصراتة", "tauorga": "مصراتة",
    "socna": "الجفرة", "uaddan": "الجفرة",
    "traghen": "مرزق",
    "uadi esc-scerghi": "سبها",
    "tuaregh ubari e uadi el-garbi": "وادي الحياة",
    "edri": "وادي الشاطئ", "berghin": "وادي الشاطئ",
    "sidi ahmed el-magrun": "بنغازي", "bengasi esterna": "بنغازي",
    "es-sahel": "الجفارة",
}

# The colony each shabiya belongs to, by the pcode prefix the CODAB layer uses,
# so a name shared by places at both ends of the country cannot cross.
REGION = {"Tripolitania": ("LY02", "LY03"), "Cirenaica": ("LY01",)}


def read(colony):
    rows = []
    for row in csv.DictReader(SOURCES[colony].open()):
        for group in GROUPS:
            for sex in ("mf", "f"):
                row[f"{group}_{sex}"] = int(row[f"{group}_{sex}"])
        row["colony"] = colony
        rows.append(row)
    return rows


def audit(rows, colony):
    """The four checks. Anything that fails here stops the script."""
    trouble = []
    by_name = {r["name"]: r for r in rows}
    children = {}
    for row in rows:
        if row["parent"]:
            children.setdefault(row["parent"], []).append(row)

    for row in rows:
        for sex in ("mf", "f"):
            parts = sum(row[f"{g}_{sex}"] for g in GROUPS[1:])
            if parts != row[f"present_{sex}"]:
                trouble.append(f"{colony} {row['name']} {sex}: the three "
                               f"populations sum to {parts:,}, the row says "
                               f"{row[f'present_{sex}']:,}")
        for group in GROUPS:
            if row[f"{group}_f"] > row[f"{group}_mf"]:
                trouble.append(f"{colony} {row['name']} {group}: more women "
                               f"than people")

    for parent, kids in children.items():
        above = by_name.get(parent)
        if not above:
            trouble.append(f"{colony}: no row named {parent}")
            continue
        for group in GROUPS:
            for sex in ("mf", "f"):
                got = sum(k[f"{group}_{sex}"] for k in kids)
                if got != above[f"{group}_{sex}"]:
                    trouble.append(
                        f"{colony} {parent} {group}_{sex}: its {len(kids)} "
                        f"children sum to {got:,}, the row says "
                        f"{above[f'{group}_{sex}']:,}")

    top = [r for r in rows if r["level"] == "1"]
    total = [r for r in rows if r["level"] == "0"]
    if len(total) != 1:
        trouble.append(f"{colony}: {len(total)} total lines, expected one")
    else:
        for group in GROUPS:
            for sex in ("mf", "f"):
                got = sum(r[f"{group}_{sex}"] for r in top)
                if got != total[0][f"{group}_{sex}"]:
                    trouble.append(
                        f"{colony} total {group}_{sex}: the {len(top)} "
                        f"circumscriptions sum to {got:,}, the table prints "
                        f"{total[0][f'{group}_{sex}']:,}")
    return trouble


def key_of(name):
    """The place a printed label names, stripped of its administrative word."""
    bare = name.lower()
    for word in ("distretto settentrionale di ", "distretto meridionale di ",
                 "commissariato regionale di ", "circondario di ",
                 "distretto di ", "c. r. di ", "c. r. del ", "c. r. della ",
                 "c. z. di ", "c. z. del ", "c. z. della ", "circondario ",
                 "distretto "):
        if bare.startswith(word):
            bare = bare[len(word):]
            break
    return bare.strip()


def place(rows, places, shabiya_keys, scrambled):
    names = dict(SEATS)
    for key, arabic in ARABIC.items():
        names.setdefault(key, arabic)
    for row in rows:
        key = key_of(row["name"])
        arabic = names.get(key, "")
        found, route = None, "unplaced"
        if arabic:
            got = resolve(SPECIFIC.get(arabic, arabic), places, shabiya_keys,
                          scrambled)
            if got and got[2].startswith(REGION[row["colony"]]):
                found, route = got, "concordance"
            elif got:
                route = "the concordance puts this name in the other colony"
        if not found:
            # The 1936 list writes `el gusbat` where this table writes
            # `el-Gusbat`, so both spacings are tried.
            loose = key.replace("-", " ")
            asserted = (SEAT_SHABIYA.get(key) or SEAT_SHABIYA.get(loose)
                        or DISTRICT_SHABIYA.get(key)
                        or DISTRICT_SHABIYA.get(loose))
            if asserted:
                got = resolve(asserted, places, shabiya_keys, scrambled)
                if got and got[2].startswith(REGION[row["colony"]]):
                    found, route = got[:3] + ("asserted",), "asserted"
        row["place_key"] = key
        row["place_ar"] = arabic
        row["shabiya_ar"] = found[0] if found else ""
        row["shabiya_en"] = found[1] if found else ""
        row["shabiya_pcode"] = found[2] if found else ""
        row["shabiya_route"] = route if row["level"] != "0" else "colony total"


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    places, shabiya_keys, scrambled = gazetteer()

    rows, trouble = [], []
    for colony in SOURCES:
        here = read(colony)
        trouble += audit(here, colony)
        rows += here
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    place(rows, places, shabiya_keys, scrambled)
    for row in rows:
        row["level_name"] = LEVELS[row["level"]]

    OUT.mkdir(parents=True, exist_ok=True)
    fields = (["colony", "level_name", "name", "parent", "place_ar",
               "shabiya_ar", "shabiya_en", "shabiya_pcode", "shabiya_route"]
              + [f"{g}_{s}" for g in GROUPS for s in ("mf", "f")]
              + ["place_key"])
    path = OUT / "libya_1931_districts.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:32s} {len(rows):5d} rows")
    report(rows)


def report(rows):
    from collections import Counter
    print()
    for colony in SOURCES:
        here = [r for r in rows if r["colony"] == colony]
        kinds = Counter(r["level_name"] for r in here)
        total = next(r for r in here if r["level_name"] == "colony")
        print(f"{colony}: {len(here)} rows {dict(kinds)}")
        print(f"   present {total['present_mf']:,} of whom "
              f"{total['present_f']:,} women "
              f"({total['present_f'] / total['present_mf']:.1%}); "
              f"indigenous {total['indigena_mf']:,}, Italians "
              f"{total['regnicola_mf']:,}, other foreigners "
              f"{total['straniera_mf']:,}")
    print("\n  [ok ] every component, sex, hierarchy and colony check passes")
    placed = [r for r in rows if r["shabiya_en"]]
    print(f"{len(placed)} of {len(rows)} rows carry a shabiya "
          f"{dict(Counter(r['shabiya_route'] for r in rows))}")
    print("  by shabiya:", dict(Counter(r["shabiya_en"] for r in placed)
                                .most_common(10)))
    unplaced = sorted({r["place_key"] for r in rows
                       if not r["shabiya_en"] and r["level_name"] != "colony"})
    print(f"  {len(unplaced)} names with no shabiya:", ", ".join(unplaced[:14]))
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
