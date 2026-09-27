#!/usr/bin/env python3
"""
Table III of the 1931 census: who was present, who was absent, who lived there.

Source: Istituto Centrale di Statistica, `VII Censimento generale della
popolazione 1931, Volume V, Colonie e Possedimenti`, Tavola III, `Popolazione
regnicola e straniera presente, temporaneamente assente e residente, secondo il
sesso`, printed page 13 for Tripolitania and page 24 for Cirenaica.

Like table II it was **transcribed by eye** rather than read by a program, for
the reason `scripts/extract_istat_1931_districts.py` gives, and it is validated
the same way before anything is published.

## What it counts, which is narrower than tables I and II

**Only the regnicola and straniera population**: Italians from the Kingdom and
other foreigners, 30,901 in Tripolitania and 18,506 in Cirenaica. The
indigenous population, 512,771 and 141,945, is not in this table at all. Reading
these figures as Libya's population would be wrong by a factor of twenty.

What it adds is the distinction the other two tables do not make, between being
somewhere and living there:

  present    counted in the circumscription on census night, split into those
             whose dimora there was `abituale` and those whose dimora was
             `temporanea`
  resident   whose home it was, whether or not they were in it that night
  absent     resident but temporarily elsewhere, with the women of them

The two are not the same population and the table says so: 1,747 of the 30,901
people present in Tripolitania were passing through, and 1,132 residents were
away. The gap is largest where the colonial economy was moving people about.
Giofra had 276 present but 311 resident and 55 away; Zliten had 142 present of
whom 59 were temporary.

Every count is given for both sexes and for men and women separately, which
neither table I nor table II does for this population.

## Six checks, and what each catches

  sexes       MF = M + F in each of the four blocks
  dimora      present = abituale + temporanea, for MF, M and F alike
  residence   resident = abituale + temporaneamente assente, the definition the
              table works to, for MF and for women
  hierarchy   every parent equals the sum of the circondari printed under it
  colony      the circumscriptions sum to the colony total
  table II    the present population here equals `regnicola` plus `straniera`
              in table II, circumscription by circumscription and for women

The last is the strongest, because it ties this transcription to a different
table on a different page that was transcribed separately. Both colonies passed
all six on the first reading.

Outputs, under data/processed/istat/:
  libya_1931_residents.csv   one row per circumscription and circondario
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1931_districts import (  # noqa: E402
    ARABIC, DISTRICT_SHABIYA, LEVELS, REGION, key_of)
from extract_istat_1936_localities import (  # noqa: E402
    SEATS, SEAT_SHABIYA, SPECIFIC)
from libya_places import gazetteer, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
SOURCES = {"Tripolitania": "libya_1931_table3_tripolitania.csv",
           "Cirenaica": "libya_1931_table3_cirenaica.csv"}
DISTRICTS = OUT / "libya_1931_districts.csv"

BLOCKS = ("present", "habitual", "temporary", "resident")
NUMBERS = ([f"{b}_{s}" for b in BLOCKS for s in ("mf", "m", "f")]
           + ["absent_mf", "absent_f"])


def read(colony):
    rows = []
    for row in csv.DictReader((RAW / SOURCES[colony]).open()):
        for column in NUMBERS:
            row[column] = int(row[column])
        row["colony"] = colony
        rows.append(row)
    return rows


def audit(rows, colony):
    trouble = []
    by_name = {r["name"]: r for r in rows}
    children = {}
    for row in rows:
        if row["parent"]:
            children.setdefault(row["parent"], []).append(row)

    for row in rows:
        for block in BLOCKS:
            if row[f"{block}_mf"] != row[f"{block}_m"] + row[f"{block}_f"]:
                trouble.append(f"{colony} {row['name']} {block}: men and women "
                               f"do not add to the total")
        for sex in ("mf", "m", "f"):
            if row[f"habitual_{sex}"] + row[f"temporary_{sex}"] != row[f"present_{sex}"]:
                trouble.append(f"{colony} {row['name']} {sex}: habitual and "
                               f"temporary do not add to present")
        for sex, absent in (("mf", "absent_mf"), ("f", "absent_f")):
            if row[f"habitual_{sex}"] + row[absent] != row[f"resident_{sex}"]:
                trouble.append(f"{colony} {row['name']} {sex}: habitual plus "
                               f"absent is not the resident population")
        if row["absent_f"] > row["absent_mf"]:
            trouble.append(f"{colony} {row['name']}: more women absent than "
                           f"people absent")

    for parent, kids in children.items():
        above = by_name.get(parent)
        if not above:
            trouble.append(f"{colony}: no row named {parent}")
            continue
        for column in NUMBERS:
            got = sum(k[column] for k in kids)
            if got != above[column]:
                trouble.append(f"{colony} {parent} {column}: its {len(kids)} "
                               f"children sum to {got:,}, the row says "
                               f"{above[column]:,}")

    top = [r for r in rows if r["level"] == "1"]
    total = [r for r in rows if r["level"] == "0"]
    if len(total) != 1:
        trouble.append(f"{colony}: {len(total)} total lines, expected one")
    else:
        for column in NUMBERS:
            got = sum(r[column] for r in top)
            if got != total[0][column]:
                trouble.append(f"{colony} total {column}: the {len(top)} "
                               f"circumscriptions sum to {got:,}, the table "
                               f"prints {total[0][column]:,}")
    return trouble


def against_table_two(rows):
    """The present population here is table II's `regnicola` plus `straniera`.

    Two tables on two pages, transcribed separately, counting the same people
    from the same census. If they agree row by row, neither transcription has a
    digit wrong in the columns they share.
    """
    if not DISTRICTS.exists():
        return ["libya_1931_districts.csv is missing; run "
                "scripts/extract_istat_1931_districts.py first"]
    two = {}
    for row in csv.DictReader(DISTRICTS.open()):
        two[(row["colony"], row["name"])] = row
    trouble, checked = [], 0
    for row in rows:
        twin = two.get((row["colony"], row["name"]))
        if not twin:
            continue
        for sex in ("mf", "f"):
            expected = int(twin[f"regnicola_{sex}"]) + int(twin[f"straniera_{sex}"])
            if expected != row[f"present_{sex}"]:
                trouble.append(f"{row['colony']} {row['name']} {sex}: table II "
                               f"has {expected:,} Italians and foreigners, "
                               f"table III has {row[f'present_{sex}']:,} present")
            else:
                checked += 1
    return trouble, checked


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
        if not found:
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
    crossed = against_table_two(rows)
    if isinstance(crossed, list):
        trouble += crossed
        checked = 0
    else:
        trouble += crossed[0]
        checked = crossed[1]
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
              + NUMBERS + ["place_key"])
    path = OUT / "libya_1931_residents.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:32s} {len(rows):5d} rows")
    report(rows, checked)


def report(rows, checked):
    print()
    for colony in SOURCES:
        here = [r for r in rows if r["colony"] == colony]
        total = next(r for r in here if r["level_name"] == "colony")
        print(f"{colony}: {len(here)} rows, "
              f"{dict(Counter(r['level_name'] for r in here))}")
        print(f"   present {total['present_mf']:,} Italians and foreigners, of "
              f"whom {total['temporary_mf']:,} were passing through; resident "
              f"{total['resident_mf']:,}, of whom {total['absent_mf']:,} were "
              f"away ({total['absent_f']:,} of them women)")
    print("\n  [ok ] sexes, dimora, residence, hierarchy and colony checks pass")
    print(f"  [ok ] {checked} cross-checks against table II agree: the present "
          f"population here is its Italians plus its foreigners")
    placed = [r for r in rows if r["shabiya_en"]]
    print(f"{len(placed)} of {len(rows)} rows carry a shabiya "
          f"{dict(Counter(r['shabiya_route'] for r in rows))}")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
