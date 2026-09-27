#!/usr/bin/env python3
"""
Tables I, II and III of the 1936 census: Libya by circumscription and municipality.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`, Section
I, printed pages 2 to 4: `Superficie e densità - Popolazione presente e
residente` (Tav. I), the same by sex `nelle province, circondari, residenze,
distretti e sottozone militari` (Tav. II), and `nei municipi` (Tav. III).

**Transcribed by eye**, like the 1931 tables, and validated the same way before
anything is published. The transcriptions are committed as
`data/raw/istat/libya_1936_table*.csv` and are the source.

## What this adds to what the repository already has of 1936

`libya_localities_1936.csv` names 1,090 places and `libya_population_1936.csv`
counts people in them, but the second overcounts the colony by 6.7% and neither
gives the administrative hierarchy with its population. This does: 69 rows from
the colony down through provinces, circondari, residenze, distretti and the
military sub-zones of the south, each with the population **present** and
**resident**, split into `nazionale` (Italians), `straniera e assimilata` and
`libica`, and every one of those by sex.

It is also the frame the 1931 tables can be read against, though not directly:
Libya in 1931 is two colonies of eleven and four circumscriptions, in 1936 four
provinces and a military territory. The names carry over; the boundaries do not.

## The municipalities are a second cut of the same census

Table III gives 27 `municipi`, created by decree in November 1935, and they are
not another level of the hierarchy: a municipality is sometimes one residenza,
sometimes two, sometimes three distretti. The footnotes to table II say which,
and this script checks every municipality against the circumscriptions it is
made of. All 432 figures agree, which is what makes the two transcriptions
confirm each other.

## The checks

  components   present and resident each equal `nazionale` + `straniera` +
               `libica`, for the whole population and for women alone
  sexes        the female count never exceeds the total
  hierarchy    every parent equals the sum of the rows printed under it
  colony       the four provinces and the military territory sum to Libya
  area         table I's areas sum to Libya's, and its printed density is the
               present population over the area, to the two decimals it gives
  municipality every municipality equals the circumscriptions its footnote
               names, across all 16 columns

1,104 figures in table II and 432 in table III, bound to each other and to the
colony totals. Both tables passed on the first reading.

Outputs, under data/processed/istat/:
  libya_1936_circumscriptions.csv   69 rows, the administrative hierarchy
  libya_1936_municipalities.csv     27 rows, the municipalities
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1931_districts import (  # noqa: E402
    ARABIC, DISTRICT_SHABIYA, REGION as COLONY_REGION)
from extract_istat_1936_localities import (  # noqa: E402
    SEATS, SEAT_SHABIYA, SPECIFIC)
from libya_places import gazetteer, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"

GROUPS = ("total", "national", "foreign", "libyan")
NUMBERS = [f"{w}_{g}_{s}" for w in ("present", "resident")
           for g in GROUPS for s in ("mf", "f")]
# Which colony of 1931 each 1936 province sits in, so the shabiya guard that
# stopped a name crossing the country still applies. The Territorio Militare
# del Sud is the exception: it runs from Ghat to Kufra and so reaches into
# both, and its sub-zones are allowed either.
COLONY = {"Provincia di Tripoli": "Tripolitania",
          "Provincia di Misurata": "Tripolitania",
          "Provincia di Bengasi": "Cirenaica",
          "Provincia di Derna": "Cirenaica",
          "Territorio Militare del Sud": "both",
          "LIBIA": "both"}
# The circumscriptions each municipality is made of, from the footnotes to
# table II. A municipality is not a level of the hierarchy: it is sometimes one
# residenza and sometimes three distretti.
MADE_OF = {
    "el-Azizia": ["Residenza di el-Azizia"], "Garian": ["Residenza di Garian"],
    "Iefren": ["Residenza di Iefren"], "Mizda": ["Residenza di Mizda"],
    "Nalut": ["Circondario di Nalut"], "Sabratha": ["Distretto di Sabratha"],
    "Sugh el-Giumaa": ["Residenza di Sugh el-Giumaa"],
    "Tagiura": ["Residenza di Tagiura"], "Tripoli": ["Circondario di Tripoli"],
    "Zavia": ["Circondario di Zavia"], "Zuara": ["Distretto di Zuara"],
    "Beni Ulid": ["Residenza di Beni Ulid"],
    "el-Gusbat": ["Residenza di el-Gusbat"], "Homs": ["Residenza di Homs"],
    "Misurata": ["Residenza di Misurata"],
    "Sirte": ["Residenza di Sirte", "Residenza di en-Nofilia"],
    "Tarhuna": ["Residenza di Tarhuna"], "Zliten": ["Circondario di Zliten"],
    "Agedabia": ["Circondario di Agedabia"], "Barce": ["Circondario di Barce"],
    "Bengasi": ["Residenza di Bengasi", "Residenza di Tocra"],
    "Soluch": ["Residenza di Soluch"], "Apollonia": ["Distretto di Apollonia"],
    "Beda Littoria": ["Distretto di Beda Littoria",
                      "Distretto di Gerdes Gerrari", "Distretto di Cirene"],
    "Derna": ["Circondario di Derna"],
    "Porto Bardia": ["Residenza di Porto Bardia"],
    "Tobruch": ["Residenza di Tobruch"],
}
# Names of 1936 that the concordance does not carry and the 1931 lists do not
# either, with the province each sits in. Asserted, and labelled as such.
EXTRA_SHABIYA = {
    "beni ulid": "مصراتة", "beda littoria": "الجبل الأخضر",
    "gerdes gerrari": "الجبل الأخضر", "giovanni berta": "الجبل الأخضر",
    "suani ben adem": "الجفارة", "el-abiar": "بنغازي",
    "el-gusbat": "المرقب", "el-giof": "الكفرة", "gat": "غات",
}


def read(name, numbers=NUMBERS):
    rows = []
    for row in csv.DictReader((RAW / name).open()):
        for column in numbers:
            row[column] = int(row[column])
        rows.append(row)
    return rows


def audit(rows):
    trouble = []
    by_name = {r["name"]: r for r in rows}
    children = {}
    for row in rows:
        if row.get("parent"):
            children.setdefault(row["parent"], []).append(row)

    for row in rows:
        for when in ("present", "resident"):
            for sex in ("mf", "f"):
                parts = sum(row[f"{when}_{g}_{sex}"] for g in GROUPS[1:])
                if parts != row[f"{when}_total_{sex}"]:
                    trouble.append(f"{row['name']} {when} {sex}: the three "
                                   f"populations sum to {parts:,}, the row says "
                                   f"{row[f'{when}_total_{sex}']:,}")
            for group in GROUPS:
                if row[f"{when}_{group}_f"] > row[f"{when}_{group}_mf"]:
                    trouble.append(f"{row['name']} {when} {group}: more women "
                                   f"than people")

    for parent, kids in children.items():
        above = by_name.get(parent)
        if not above:
            trouble.append(f"no row named {parent}")
            continue
        for column in NUMBERS:
            got = sum(k[column] for k in kids)
            if got != above[column]:
                trouble.append(f"{parent} {column}: its {len(kids)} children "
                               f"sum to {got:,}, the row says {above[column]:,}")

    top = [r for r in rows if r.get("level") == "provincia"]
    total = [r for r in rows if r.get("level") == "colony"]
    if len(total) == 1:
        for column in NUMBERS:
            got = sum(r[column] for r in top)
            if got != total[0][column]:
                trouble.append(f"Libya {column}: the {len(top)} provinces sum "
                               f"to {got:,}, the table prints "
                               f"{total[0][column]:,}")
    return trouble


def audit_area(one, two):
    """Table I: areas sum to the colony and the printed density is right."""
    trouble = []
    by_name = {r["name"]: r for r in two}
    top = [r for r in one if r["order"] != "0"]
    total = next(r for r in one if r["order"] == "0")
    if sum(int(r["superficie_km2"]) for r in top) != int(total["superficie_km2"]):
        trouble.append("table I: the areas do not sum to Libya's")
    for row in one:
        density = round(int(row["present_total"]) / int(row["superficie_km2"]), 2)
        if abs(density - float(row["density_km2"])) > 0.005:
            trouble.append(f"table I {row['name']}: the printed density "
                           f"{row['density_km2']} is not the present population "
                           f"over the area ({density})")
        twin = by_name.get(row["name"])
        if twin and int(row["present_total"]) != twin["present_total_mf"]:
            trouble.append(f"table I {row['name']}: present {row['present_total']}"
                           f" against table II's {twin['present_total_mf']}")
    return trouble


def audit_municipalities(three, two):
    """Every municipality is the circumscriptions its footnote names."""
    by_name = {r["name"]: r for r in two}
    trouble, checked = [], 0
    for row in three:
        parts = MADE_OF.get(row["name"])
        if not parts:
            trouble.append(f"municipality {row['name']}: no circumscription "
                           f"named for it")
            continue
        missing = [p for p in parts if p not in by_name]
        if missing:
            trouble.append(f"municipality {row['name']}: table II has no "
                           f"{missing}")
            continue
        for column in NUMBERS:
            got = sum(by_name[p][column] for p in parts)
            if got != row[column]:
                trouble.append(f"municipality {row['name']} {column}: its "
                               f"circumscriptions give {got:,}, table III says "
                               f"{row[column]:,}")
            else:
                checked += 1
    return trouble, checked


def key_of(name):
    bare = name.lower()
    for word in ("provincia di ", "circondario di ", "residenza di ",
                 "distretto di ", "sottozona militare di ", "territorio "):
        if bare.startswith(word):
            bare = bare[len(word):]
            break
    return bare.strip()


def place(rows, places, shabiya_keys, scrambled, colony_of):
    names = dict(SEATS)
    for key, arabic in ARABIC.items():
        names.setdefault(key, arabic)
    for row in rows:
        key = key_of(row["name"])
        colony = colony_of(row)
        allowed = (("LY01", "LY02", "LY03") if colony == "both"
                   else COLONY_REGION[colony])
        arabic = names.get(key) or names.get(key.replace("-", " "), "")
        found, route = None, "unplaced"
        if arabic:
            got = resolve(SPECIFIC.get(arabic, arabic), places, shabiya_keys,
                          scrambled)
            if got and got[2].startswith(allowed):
                found, route = got, "concordance"
        if not found:
            loose = key.replace("-", " ")
            asserted = (SEAT_SHABIYA.get(key) or SEAT_SHABIYA.get(loose)
                        or DISTRICT_SHABIYA.get(key)
                        or DISTRICT_SHABIYA.get(loose)
                        or EXTRA_SHABIYA.get(key) or EXTRA_SHABIYA.get(loose))
            if asserted:
                got = resolve(asserted, places, shabiya_keys, scrambled)
                if got and got[2].startswith(allowed):
                    found, route = got[:3] + ("asserted",), "asserted"
        row["place_key"] = key
        row["place_ar"] = arabic
        row["shabiya_ar"] = found[0] if found else ""
        row["shabiya_en"] = found[1] if found else ""
        row["shabiya_pcode"] = found[2] if found else ""
        row["shabiya_route"] = found and route or (
            "colony total" if row.get("level") == "colony" else route)


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    places, shabiya_keys, scrambled = gazetteer()

    two = read("libya_1936_table2.csv")
    three = read("libya_1936_table3.csv")
    one = read("libya_1936_table1.csv", numbers=[])

    trouble = audit(two) + audit(three) + audit_area(one, two)
    more, checked = audit_municipalities(three, two)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    # The area and density of table I belong to the rows table II shares.
    area = {r["name"]: r for r in one}
    province = {}
    for row in two:
        if row["level"] == "provincia":
            province[row["name"]] = row["name"]
        elif row["parent"]:
            province[row["name"]] = province.get(row["parent"], "")
        row["province"] = (row["name"] if row["level"] == "provincia"
                           else province.get(row["name"], ""))
        twin = area.get(row["name"]) or (area.get("LIBIA")
                                         if row["level"] == "colony" else None)
        row["superficie_km2"] = twin["superficie_km2"] if twin else ""
        row["density_km2"] = twin["density_km2"] if twin else ""

    place(two, places, shabiya_keys, scrambled,
          lambda r: COLONY.get(r["province"] or r["name"], "Tripolitania"))
    place(three, places, shabiya_keys, scrambled,
          lambda r: COLONY.get(r["province"], "Tripolitania"))

    OUT.mkdir(parents=True, exist_ok=True)
    head = ["province", "level", "name", "parent", "place_ar", "shabiya_ar",
            "shabiya_en", "shabiya_pcode", "shabiya_route"]
    write(OUT / "libya_1936_circumscriptions.csv", two,
          head + ["superficie_km2", "density_km2"] + NUMBERS
          + ["order", "place_key"])
    write(OUT / "libya_1936_municipalities.csv", three,
          ["province", "name", "place_ar", "shabiya_ar", "shabiya_en",
           "shabiya_pcode", "shabiya_route"] + NUMBERS + ["order", "place_key"])
    report(two, three, checked)


def write(path, rows, fields):
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:36s} {len(rows):5d} rows")


def report(two, three, checked):
    print()
    total = next(r for r in two if r["level"] == "colony")
    print(f"Libya 1936: {total['present_total_mf']:,} present "
          f"({total['present_total_f']:,} women), "
          f"{total['resident_total_mf']:,} resident; "
          f"{total['present_libyan_mf']:,} Libyans, "
          f"{total['present_national_mf']:,} Italians, "
          f"{total['present_foreign_mf']:,} other foreigners")
    print("  by level:", dict(Counter(r["level"] for r in two)))
    print("\n  [ok ] components, sexes, hierarchy, colony, area and density "
          "checks pass")
    print(f"  [ok ] {checked} figures of the 27 municipalities equal the "
          f"circumscriptions their footnotes name")
    for rows, what in ((two, "circumscriptions"), (three, "municipalities")):
        placed = [r for r in rows if r["shabiya_en"]]
        print(f"{len(placed)} of {len(rows)} {what} carry a shabiya "
              f"{dict(Counter(r['shabiya_route'] for r in rows))}")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
