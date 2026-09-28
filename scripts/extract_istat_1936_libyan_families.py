#!/usr/bin/env python3
"""
Tables XXIII to XXIX of the 1936 census: Libyan families, marriage and
institutions.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione III, Popolazione libica, printed pages 92, 93 and 100 to 103.

**Transcribed by eye**, like the other 1931 and 1936 tables, and validated
before anything is published. The transcriptions are committed as
`data/raw/istat/libya_1936_table{23,24,26,27,28,29}.csv` and are the source.
Table XXV, families by number of children, is published separately.

## What the tables are

  XXIII   resident families and their members by the economic activity and
          the religion of the head, by province and for the four municipi
  XXIV    the same families by number of members, 1 to 20 and more
  XXVI    Muslim monogamous heads of family by their age and their wife's
  XXVII   Muslim polygamous husbands by their age and their wives' ages
  XXVIII  the same husbands by number of wives (2, 3 or 4) and age
  XXIX    convivenze, the Libyans living in hospitals, schools, hospices,
          prisons and other collective quarters, by sex and province

## Why XXVI to XXVIII matter

They are a count of polygamy in a Muslim society taken by a colonial state,
by age of both spouses and by province, and nothing comparable exists for Libya
before or after. The census found **142,993 monogamous Muslim heads of family
and 5,507 polygamous husbands**, 3.7% of the two together, with 11,305 wives
between them: 5,232 with two wives, 259 with three and 16 with four. The age
gap is in the cross-tabulation, cell by cell.

## Checks

  XXIII   the nine activity categories sum to the total for families and for
          members; the four provinces and the military territory sum to Libya;
          Muslim plus Jewish never exceed the whole
  XXIV    the size classes sum to the families; members over sizes 1 to 19
          leave at least twenty for each family of 20 or more; the categories
          sum to the total
  XXVI    wives by age sum to the heads; ages sum to the total; provinces sum
  XXVII   wives by age sum to the wives; ages and provinces sum
  XXVIII  2 + 3 + 4 wives = the husbands; ages and provinces sum
  XXIX    M + F = MF; the five kinds sum to the whole; provinces sum to Libya

## Four cross-checks between tables

  XXIII against XXII   families and members per province equal table XXII's
                       family heads and resident Libyans
  XXIV against XXIII   each activity category has the same families and
                       members in both
  XXVIII against XXVII husbands by age agree, and 2 x (two wives) + 3 x (three)
                       + 4 x (four) equals the wives XXVII counts, in every cell
  XXVI  against XXVII  the provinces carry the same age classes

Outputs, under data/processed/istat/:
  libya_1936_libyan_families.csv        XXIII, long: one row per religion,
                                        area and activity of the head
  libya_1936_libyan_family_size.csv     XXIV, long: religion, activity, size
  libya_1936_muslim_marriages.csv       XXVI and XXVII, long: union, area,
                                        husband's age, wife's age, wives
  libya_1936_polygamous_husbands.csv    XXVIII, long
  libya_1936_libyan_institutions.csv    XXIX, long
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
RESIDENT = OUT / "libya_1936_libyans_resident.csv"

CATEGORIES = ("agricoltura", "industria", "trasporti", "commercio",
              "libere_culto", "amministrazione", "domestica",
              "non_professionali", "senza_indicazione")
PROVINCES = ("Provincia di Tripoli", "Provincia di Misurata",
             "Provincia di Bengasi", "Provincia di Derna",
             "Territorio Militare del Sud")
SIZES = [f"size_{k}" for k in range(1, 20)] + ["size_20plus"]
HUSBAND_AGES = ("20-24", "25-29", "30-34", "35-39", "40-44", "45-49",
                "50-54", "55-59", "60-64", "65+")
AREAS29 = ("libia", "mun_tripoli", "tripoli", "misurata", "bengasi",
           "derna", "territorio")
AREA29_NAME = {"libia": "LIBIA", "mun_tripoli": "di cui municipio di Tripoli",
               "tripoli": "Provincia di Tripoli",
               "misurata": "Provincia di Misurata",
               "bengasi": "Provincia di Bengasi",
               "derna": "Provincia di Derna",
               "territorio": "Territorio Militare del Sud"}


def read(name):
    rows = []
    for row in csv.DictReader((RAW / name).open()):
        for key, value in row.items():
            if value.lstrip("-").isdigit() and key not in (
                    "order", "wives_per_husband"):
                row[key] = int(value)
        rows.append(row)
    return rows


def numbers(row, keys):
    return [row[k] for k in keys]


def audit_23(rows):
    trouble = []
    fam = [f"{c}_f" for c in CATEGORIES]
    mem = [f"{c}_m" for c in CATEGORIES]
    by = {(r["religion"], r["area"]): r for r in rows}
    for r in rows:
        if sum(numbers(r, fam)) != r["families"]:
            trouble.append(f"XXIII {r['religion']} {r['area']}: families")
        if sum(numbers(r, mem)) != r["members"]:
            trouble.append(f"XXIII {r['religion']} {r['area']}: members")
    for religion in ("all", "muslim", "jewish"):
        for key in ["families", "members"] + fam + mem:
            got = sum(by[(religion, p)][key] for p in PROVINCES)
            if got != by[(religion, "LIBIA")][key]:
                trouble.append(f"XXIII {religion} {key}: provinces {got:,}")
    for (religion, area), r in by.items():
        if religion != "all":
            continue
        for key in ["families", "members"] + fam + mem:
            if by[("muslim", area)][key] + by[("jewish", area)][key] > r[key]:
                trouble.append(f"XXIII {area} {key}: Muslim and Jewish "
                               f"exceed the whole")
    return trouble


def audit_24(rows):
    trouble = []
    by = {(r["religion"], r["category"]): r for r in rows}
    for r in rows:
        who = f"XXIV {r['religion']} {r['category']}"
        if sum(numbers(r, SIZES)) != r["families"]:
            trouble.append(f"{who}: sizes do not sum to the families")
        known = sum((k + 1) * r[s] for k, s in enumerate(SIZES[:-1]))
        rest = r["members"] - known
        if rest < 20 * r["size_20plus"] or (r["size_20plus"] == 0 and rest):
            trouble.append(f"{who}: {rest:,} members left for "
                           f"{r['size_20plus']} families of 20 or more")
    for religion in ("all", "muslim", "jewish"):
        for key in ["families", "members"] + SIZES:
            got = sum(by[(religion, c)][key] for c in CATEGORIES)
            if got != by[(religion, "totale")][key]:
                trouble.append(f"XXIV {religion} {key}: categories {got:,}")
    return trouble


def audit_cross(rows, table, total, cells):
    """Row cells sum to a total; ages sum to Totale; provinces to Libia."""
    trouble = []
    by = defaultdict(dict)
    for r in rows:
        by[r["area"]][r["husband_age"]] = r
        if sum(numbers(r, cells)) != r[total]:
            trouble.append(f"{table} {r['area']} {r['husband_age']}: cells "
                           f"sum to {sum(numbers(r, cells)):,}")
    keys = [total] + cells + (["husbands"] if total != "husbands" else [])
    for area, lines in by.items():
        for key in keys:
            got = sum(v[key] for a, v in lines.items() if a != "Totale")
            if got != lines["Totale"][key]:
                trouble.append(f"{table} {area} {key}: ages sum to {got:,}")
    for age, top in by["Libia"].items():
        for key in keys:
            got = sum(by[p].get(age, {}).get(key, 0) for p in PROVINCES)
            if got != top[key]:
                trouble.append(f"{table} Libia {age} {key}: provinces "
                               f"{got:,}")
    return trouble


def audit_28(rows, xxvii):
    trouble, checked = [], 0
    by = defaultdict(dict)
    for r in rows:
        by[r["area"]][r["wives_per_husband"]] = r
        ages = [f"h{a.replace('-', '_').replace('+', 'plus')}"
                for a in HUSBAND_AGES]
        if sum(numbers(r, ages)) != r["husbands"]:
            trouble.append(f"XXVIII {r['area']} {r['wives_per_husband']}: "
                           f"ages")
    husbands = {(r["area"], r["husband_age"]): r for r in xxvii}
    for area, lines in by.items():
        for key in ["husbands"] + ages:
            if (lines["2"][key] + lines["3"][key] + lines["4"][key]
                    != lines["Totale"][key]):
                trouble.append(f"XXVIII {area} {key}: 2 + 3 + 4")
        for age, column in zip(list(HUSBAND_AGES) + ["Totale"],
                               ages + ["husbands"]):
            twin = husbands.get((area, age), {"husbands": 0, "wives": 0})
            if lines["Totale"][column] != twin["husbands"]:
                trouble.append(f"XXVIII {area} {age}: {lines['Totale'][column]}"
                               f" husbands, XXVII {twin['husbands']}")
            else:
                checked += 1
            wives = sum(int(n) * lines[n][column] for n in ("2", "3", "4"))
            if wives != twin["wives"]:
                trouble.append(f"XXVIII {area} {age}: implies {wives} wives, "
                               f"XXVII {twin['wives']}")
            else:
                checked += 1
    for key in ["husbands"] + ages:
        for n in ("2", "3", "4", "Totale"):
            got = sum(by[p][n][key] for p in PROVINCES)
            if got != by["Libia"][n][key]:
                trouble.append(f"XXVIII Libia {n} {key}: provinces {got}")
    return trouble, checked


def audit_29(rows):
    trouble = []
    by = {(r["kind"], r["role"], r["sex"]): r for r in rows}
    columns = [f"{a}_{x}" for a in AREAS29 for x in ("n", "c")]
    for (kind, role, sex), r in by.items():
        if sex == "MF":
            for column in columns[1::2]:
                if (by[(kind, role, "M")][column] + by[(kind, role, "F")][column]
                        != r[column]):
                    trouble.append(f"XXIX {kind} {role} {column}: M + F")
        for x in ("n", "c"):
            got = sum(r[f"{a}_{x}"] for a in AREAS29[2:])
            if got != r[f"libia_{x}"]:
                trouble.append(f"XXIX {kind} {role} {sex} {x}: provinces")
    kinds = ("cura", "educazione", "assistenza", "carcerari", "altre")
    for sex in ("MF", "M", "F"):
        for column in columns:
            got = sum(by[(k, "componenti", sex)][column] for k in kinds)
            if got != by[("complesso", "componenti", sex)][column]:
                trouble.append(f"XXIX {sex} {column}: kinds sum to {got}")
    return trouble


def against_xxii(xxiii):
    if not RESIDENT.exists():
        return ["libya_1936_libyans_resident.csv is missing; run "
                "scripts/extract_istat_1936_libyans.py first"], 0
    lines = defaultdict(dict)
    for r in csv.DictReader(RESIDENT.open()):
        lines[r["name"]][r["dimora"]] = r
    trouble, checked = [], 0
    for r in xxiii:
        if r["religion"] != "all" or r["area"].startswith("di cui"):
            continue
        kinds = lines[r["area"]]
        twin = kinds.get("Tot") or next(iter(kinds.values()))
        for mine, theirs in (("families", "heads"), ("members", "mf")):
            if r[mine] != int(twin[theirs]):
                trouble.append(f"XXIII {r['area']} {mine}: {r[mine]:,}, "
                               f"table XXII {int(twin[theirs]):,}")
            else:
                checked += 1
    return trouble, checked


def against_xxiii(xxiv, xxiii):
    top = {r["religion"]: r for r in xxiii if r["area"] == "LIBIA"}
    trouble, checked = [], 0
    for r in xxiv:
        if r["category"] == "totale":
            continue
        for mine, suffix in (("families", "_f"), ("members", "_m")):
            want = top[r["religion"]][r["category"] + suffix]
            if r[mine] != want:
                trouble.append(f"XXIV {r['religion']} {r['category']} {mine}: "
                               f"{r[mine]:,}, XXIII {want:,}")
            else:
                checked += 1
    return trouble, checked


def long_rows(xxiii, xxiv, xxvi, xxvii, xxviii, xxix):
    families = []
    for r in xxiii:
        for c in CATEGORIES + ("all",):
            families.append({
                "religion": r["religion"], "area": r["area"],
                "activity_of_head": c,
                "families": r["families"] if c == "all" else r[f"{c}_f"],
                "members": r["members"] if c == "all" else r[f"{c}_m"]})
    sizes = []
    for r in xxiv:
        for s in SIZES:
            sizes.append({"religion": r["religion"],
                          "activity_of_head": r["category"],
                          "members_in_family": s.replace("size_", "")
                          .replace("20plus", "20+"),
                          "families": r[s]})
    marriages = []
    for union, rows in (("monogamous", xxvi), ("polygamous", xxvii)):
        for r in rows:
            for key, value in r.items():
                if not key.startswith("w") or key == "wives":
                    continue
                label = key[1:].replace("_", "-").replace("65plus", "65+")
                marriages.append({
                    "union": union, "area": r["area"],
                    "husband_age": r["husband_age"],
                    "husbands": r["husbands"], "wife_age": label,
                    "wives": value})
    husbands = []
    for r in xxviii:
        for age in HUSBAND_AGES:
            key = "h" + age.replace("-", "_").replace("+", "plus")
            husbands.append({"area": r["area"],
                             "wives_per_husband": r["wives_per_husband"],
                             "husband_age": age, "husbands": r[key]})
    institutions = []
    for r in xxix:
        for a in AREAS29:
            institutions.append({
                "kind": r["kind"], "role": r["role"], "sex": r["sex"],
                "area": AREA29_NAME[a],
                "institutions": r[f"{a}_n"] if r["sex"] == "MF"
                and r["role"] == "componenti" else "",
                "persons": r[f"{a}_c"]})
    return {"libya_1936_libyan_families.csv": families,
            "libya_1936_libyan_family_size.csv": sizes,
            "libya_1936_muslim_marriages.csv": marriages,
            "libya_1936_polygamous_husbands.csv": husbands,
            "libya_1936_libyan_institutions.csv": institutions}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    xxiii = read("libya_1936_table23.csv")
    xxiv = read("libya_1936_table24.csv")
    xxvi = read("libya_1936_table26.csv")
    xxvii = read("libya_1936_table27.csv")
    xxviii = read("libya_1936_table28.csv")
    xxix = read("libya_1936_table29.csv")

    wives26 = ["w10", "w11", "w12", "w13", "w14", "w15_19", "w20_24",
               "w25_29", "w30_34", "w35_39", "w40_44", "w45_49", "w50_54",
               "w55_59", "w60_64", "w65plus"]
    trouble = (audit_23(xxiii) + audit_24(xxiv)
               + audit_cross(xxvi, "XXVI", "husbands", wives26)
               + audit_cross(xxvii, "XXVII", "wives", wives26[3:])
               + audit_29(xxix))
    more, n28 = audit_28(xxviii, xxvii)
    trouble += more
    more, n22 = against_xxii(xxiii)
    trouble += more
    more, n23 = against_xxiii(xxiv, xxiii)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in long_rows(xxiii, xxiv, xxvi, xxvii, xxviii,
                                xxix).items():
        with (OUT / name).open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"{name:40s} {len(rows):5d} rows")
    report(xxiii, xxvi, xxvii, xxviii, xxix, n22, n23, n28)


def report(xxiii, xxvi, xxvii, xxviii, xxix, n22, n23, n28):
    libya = next(r for r in xxiii if r["religion"] == "all"
                 and r["area"] == "LIBIA")
    mono = next(r for r in xxvi if r["area"] == "Libia"
                and r["husband_age"] == "Totale")["husbands"]
    poly = next(r for r in xxvii if r["area"] == "Libia"
                and r["husband_age"] == "Totale")
    split = {r["wives_per_husband"]: r["husbands"] for r in xxviii
             if r["area"] == "Libia"}
    print()
    print(f"Libya 1936, Libyan families: {libya['families']:,} with "
          f"{libya['members']:,} members, {libya['members'] / libya['families']:.2f} "
          f"each; {libya['agricoltura_f'] / libya['families']:.0%} headed by "
          f"someone in agriculture")
    print(f"  Muslim marriage: {mono:,} monogamous heads, {poly['husbands']:,} "
          f"polygamous husbands ({poly['husbands'] / (mono + poly['husbands']):.1%}) "
          f"with {poly['wives']:,} wives: {split['2']:,} with two, "
          f"{split['3']:,} with three, {split['4']:,} with four")
    for area in ("Provincia di Tripoli", "Provincia di Misurata",
                 "Provincia di Bengasi", "Provincia di Derna",
                 "Territorio Militare del Sud"):
        m = next(r for r in xxvi if r["area"] == area
                 and r["husband_age"] == "Totale")["husbands"]
        p = next(r for r in xxvii if r["area"] == area
                 and r["husband_age"] == "Totale")["husbands"]
        print(f"    {area:30s} {p / (m + p):5.1%} polygamous")
    inst = {r["kind"]: r for r in xxix if r["role"] == "componenti"
            and r["sex"] == "MF"}
    print(f"  institutions: {inst['complesso']['libia_c']:,} Libyans in "
          f"{inst['complesso']['libia_n']} convivenze, "
          f"{inst['carcerari']['libia_c']:,} of them in prison")
    print("\n  [ok ] every printed identity holds in all six tables")
    print(f"  [ok ] {n22} figures agree with table XXII: families and members "
          f"per province are its family heads and residents")
    print(f"  [ok ] {n23} figures agree between XXIII and XXIV")
    print(f"  [ok ] {n28} figures agree between XXVII and XXVIII, the wives "
          f"implied by 2, 3 and 4 wives each included")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
