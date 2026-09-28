#!/usr/bin/env python3
"""
Tables XXXIII and XXXIV of the 1936 census: the Libyan population by
profession.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione III, Popolazione libica, Tavole XXXIII and XXXIV, printed pages 116 to
123.

**Transcribed by eye** and validated before anything is published. The
transcriptions are committed as `data/raw/istat/libya_1936_table33.csv` and
`libya_1936_table34.csv` and are the source.

## What they hold

The same 132 lines in both: 9 categories of economic activity, 30 classes and
91 numbered professions or conditions, plus the grand total. The `level`
column says which a line is: `categoria`, `classe`, `classe_parziale` (a class
whose professions are listed only `di cui`, so they do not add up to it),
`professione` or `totale`.

  XXXIII  Libyans resident aged 10 and over, by profession and sex, for Libya
          (MF and F), each province and the Territorio (M and F), and the
          four municipi
  XXXIV   the same, by age class (10-14, 15-17, 18-20, 21-24, 25-34, 35-44,
          45-54, 55-64, 65 and over, unknown) and sex, for Libya

The professions are those the census chose to print, among them the camel
drivers of the Fezzan (222 of 271 in the Territorio), the palm tappers who
drew `leghbi`, the Quran teachers, the mudirs, muktars and cabila heads of the
native administration, and the judges of the sharia and rabbinical courts.

## Checks, and the crossings to other tables

  XXXIII   Libya MF = Libya F plus the men of the four provinces and the
           Territorio; Libya F = the women of the five; no municipio exceeds
           its province; professions add to their class, classes (and
           conditions listed directly) to their category, categories to the
           total
  XXXIV    the age classes add to MF and to F on every line; the same
           hierarchy holds; every line's MF and F equal XXXIII's
  XXXI     XXXIII's nine categories and its total equal table XXXI's, for
           every area and sex: 200 figures
  XXX      XXXIV's grand total by age and sex equals table XXX's population,
           once XXX's five-year classes are grouped to XXXIV's: 16 figures

## A misprint in the source, and three misreadings

**The source prints one figure that cannot be right.** In XXXIII the men of
the Provincia di Bengasi selling meat, poultry, eggs and fish are printed as
363, clearly. The Libyan total for that line (1,275), the class of food
commerce and the category of commerce all require 263. The raw file keeps the
printed 363; this script applies the correction listed in `MISPRINTS` and says
so in the published file's `note` column.

Three cells of XXXIV were misread on first transcription and corrected when two
sums agreed: 17,086 men of 65 and over in agriculture, 1,285 men of 15 to 17
without a stated profession, 13 women tailors aged 21 to 24.

Outputs, under data/processed/istat/:
  libya_1936_libyan_professions.csv       XXXIII, long: profession, area, sex
  libya_1936_libyan_professions_age.csv   XXXIV, long: profession, age, sex
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"

AREAS = ("tripoli", "mun_tripoli", "misurata", "mun_misurata", "bengasi",
         "mun_bengasi", "derna", "mun_derna", "territorio")
PROVINCES = ("tripoli", "misurata", "bengasi", "derna", "territorio")
AREA_NAME = {"tripoli": "Provincia di Tripoli",
             "mun_tripoli": "di cui municipio di Tripoli",
             "misurata": "Provincia di Misurata",
             "mun_misurata": "di cui municipio di Misurata",
             "bengasi": "Provincia di Bengasi",
             "mun_bengasi": "di cui municipio di Bengasi",
             "derna": "Provincia di Derna",
             "mun_derna": "di cui municipio di Derna",
             "territorio": "Territorio Militare del Sud"}
N33 = ["libia_mf", "libia_f"] + [f"{a}_{s}" for a in AREAS for s in "mf"]
AGES = ("a10_14", "a15_17", "a18_20", "a21_24", "a25_34", "a35_44", "a45_54",
        "a55_64", "a65plus", "ignota")
AGE_LABEL = dict(zip(AGES, ("10-14", "15-17", "18-20", "21-24", "25-34",
                            "35-44", "45-54", "55-64", "65+", "ignota")))
N34 = ["mf", "f"] + [f"{a}_{s}" for a in AGES for s in "mf"]
# (profession, column) -> (printed, corrected)
MISPRINTS = {("vendita di carne, salumi, uova, pollame e pesce",
              "bengasi_m"): (363, 263)}
CATEGORY_KEYS = ("agricoltura", "industria", "trasporti", "commercio",
                 "libere_culto", "amministrazione", "domestica",
                 "non_professionali", "senza_indicazione")
# XXX's five-year classes grouped to XXXIV's
AGE_GROUPS = {"a10_14": ["10-14"], "a25_34": ["25-29", "30-34"],
              "a35_44": ["35-39", "40-44"], "a45_54": ["45-49", "50-54"],
              "a55_64": ["55-59", "60-64"],
              "a65plus": ["65-69", "70-79", "80-89", "90+"],
              "ignota": ["ignota"]}
YOUNG = (("a15_17", "a18_20", "a21_24"), ["15-19", "20-24"])


def read(name, numbers):
    rows = []
    for row in csv.DictReader((RAW / name).open()):
        for column in numbers:
            row[column] = int(row[column])
        rows.append(row)
    return rows


def correct(rows):
    for row in rows:
        row["note"] = ""
        for (name, column), (printed, fixed) in MISPRINTS.items():
            if row["name"] == name:
                assert row[column] == printed, (name, column, row[column])
                row[column] = fixed
                row["note"] = (f"{column} printed as {printed}; the line total, "
                               f"the class and the category require {fixed}")


def hierarchy(rows, numbers, table):
    """Professions to class, classes to category, categories to total."""
    trouble = []

    def close(parent, kids):
        for column in numbers:
            got = sum(k[column] for k in kids)
            if got != parent[column]:
                trouble.append(f"{table} {parent['name']} {column}: its "
                               f"{len(kids)} lines sum to {got:,}")

    category, cls, in_cat, in_cls, categories = None, None, [], [], []
    for row in rows + [{"level": "end"}]:
        level = row["level"]
        if level in ("categoria", "totale", "end"):
            if cls and cls["level"] == "classe" and in_cls:
                close(cls, in_cls)
            if category and in_cat:
                close(category, in_cat)
            if level == "categoria":
                categories.append(row)
            if level == "totale":
                close(row, categories)
            category, cls, in_cat, in_cls = row, None, [], []
        elif level.startswith("classe"):
            if cls and cls["level"] == "classe" and in_cls:
                close(cls, in_cls)
            cls, in_cls = row, []
            in_cat.append(row)
        elif cls is None:
            in_cat.append(row)
        else:
            in_cls.append(row)
    return trouble


def audit_33(rows):
    trouble = hierarchy(rows, N33, "XXXIII")
    for r in rows:
        men = sum(r[f"{p}_m"] for p in PROVINCES)
        women = sum(r[f"{p}_f"] for p in PROVINCES)
        if r["libia_f"] + men != r["libia_mf"]:
            trouble.append(f"XXXIII {r['name']}: Libya MF")
        if women != r["libia_f"]:
            trouble.append(f"XXXIII {r['name']}: Libya F")
        for p in ("tripoli", "misurata", "bengasi", "derna"):
            for s in "mf":
                if r[f"mun_{p}_{s}"] > r[f"{p}_{s}"]:
                    trouble.append(f"XXXIII {r['name']}: municipio of {p}")
    return trouble


def audit_34(rows, xxxiii):
    trouble = hierarchy(rows, N34, "XXXIV")
    for r, twin in zip(rows, xxxiii):
        if r["name"] != twin["name"]:
            trouble.append(f"XXXIV line {r['order']} is out of step")
            break
        if sum(r[f"{a}_{s}"] for a in AGES for s in "mf") != r["mf"]:
            trouble.append(f"XXXIV {r['name']}: ages do not add to MF")
        if sum(r[f"{a}_f"] for a in AGES) != r["f"]:
            trouble.append(f"XXXIV {r['name']}: ages do not add to F")
        if (r["mf"], r["f"]) != (twin["libia_mf"], twin["libia_f"]):
            trouble.append(f"XXXIV {r['name']}: MF and F differ from XXXIII")
    return trouble


def crossings(xxxiii, xxxiv):
    trouble, counts = [], {"XXXI": 0, "XXX": 0}
    xxxi = {r["area"]: r for r in csv.DictReader(
        (RAW / "libya_1936_table31.csv").open()) if r["religion"] == "complesso"}
    lines = [r for r in xxxiii if r["level"] in ("categoria", "totale")]
    for key, r in zip(CATEGORY_KEYS + ("totale",), lines):
        pairs = [("Libia", r["libia_mf"], f"{key}_mf"),
                 ("Libia", r["libia_f"], f"{key}_f")]
        for a in AREAS:
            for s in "mf":
                pairs.append((AREA_NAME[a], r[f"{a}_{s}"], f"{key}_{s}"))
        for area, mine, column in pairs:
            want = int(xxxi[area][column])
            if mine != want:
                trouble.append(f"XXXIII {r['name']} {area} {column}: {mine:,}"
                               f", table XXXI {want:,}")
            else:
                counts["XXXI"] += 1
    ages = {r["age"]: r for r in csv.DictReader(
        (RAW / "libya_1936_table30.csv").open())
        if r["area"] == "Libia" and r["religion"] == "complesso"}
    total = xxxiv[-1]
    groups = dict(AGE_GROUPS)
    for s in "mf":
        for key, classes in list(groups.items()) + [YOUNG]:
            keys = key if isinstance(key, tuple) else (key,)
            mine = sum(total[f"{k}_{s}"] for k in keys)
            want = sum(int(ages[c][f"tot_{s}"]) for c in classes)
            if mine != want:
                trouble.append(f"XXXIV {keys} {s}: {mine:,}, table XXX "
                               f"{want:,}")
            else:
                counts["XXX"] += 1
    return trouble, counts


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    xxxiii = read("libya_1936_table33.csv", N33)
    xxxiv = read("libya_1936_table34.csv", N34)
    correct(xxxiii)
    trouble = audit_33(xxxiii) + audit_34(xxxiv, xxxiii)
    more, counts = crossings(xxxiii, xxxiv)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    by_area, by_age = [], []
    for r in xxxiii:
        base = {"order": r["order"], "level": r["level"],
                "profession": r["name"]}
        by_area.append({**base, "area": "Libia", "sex": "MF",
                        "persons": r["libia_mf"], "note": ""})
        by_area.append({**base, "area": "Libia", "sex": "F",
                        "persons": r["libia_f"], "note": ""})
        for a in AREAS:
            for s in "mf":
                by_area.append({**base, "area": AREA_NAME[a], "sex": s.upper(),
                                "persons": r[f"{a}_{s}"],
                                "note": r["note"]
                                if r["note"].startswith(f"{a}_{s} ")
                                else ""})
    for r in xxxiv:
        base = {"order": r["order"], "level": r["level"],
                "profession": r["name"]}
        for a in AGES:
            for s in "mf":
                by_age.append({**base, "age": AGE_LABEL[a], "sex": s.upper(),
                               "persons": r[f"{a}_{s}"]})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("libya_1936_libyan_professions.csv", by_area),
                       ("libya_1936_libyan_professions_age.csv", by_age)):
        with (OUT / name).open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"{name:40s} {len(rows):5d} rows")
    report(xxxiii, counts)


def report(xxxiii, counts):
    by = {r["name"]: r for r in xxxiii}
    print()
    for name in ("allevatori di bestiame e pastori",
                 "operai, facchini, garzoni, apprendisti",
                 "tessitori in lana, canapa, ecc., tessitori di tappeti",
                 "cammellieri, carovanieri",
                 "coranisti, dottori di corano, insegnanti di corano",
                 "capi paese, capi distretto (mudir), capi quartiere (muctar), "
                 "capi cabila, capi zauia"):
        r = by[name]
        print(f"  {r['libia_mf']:7,d} ({r['libia_f']:5,d} women)  {name}")
    print("\n  [ok ] line totals, sexes, municipi, classes, categories and ages "
          "hold in both tables")
    print(f"  [ok ] {counts['XXXI']} figures agree with table XXXI and "
          f"{counts['XXX']} with table XXX")
    print("  [note] one misprint in the source corrected, listed in MISPRINTS")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
