#!/usr/bin/env python3
"""
Table XXV of the 1936 census: Libyan families by number of children.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione III, Popolazione libica, Tavola XXV, printed pages 94 to 99.

**Transcribed by eye** and validated before anything is published. The
transcription is committed as `data/raw/istat/libya_1936_table25.csv` and is
the source.

## What it holds

Resident Libyan families with co-resident unmarried children, by the number of
those children (1 to 8, 9 and more) in four nested age limits: children under
6, under 15, under 21, and of any age. For each, the table gives the number of
families and the number of children, by the activity of the head of family and
by religion (all, Muslim, Jewish). Three areas: Libya, and the municipi of
Tripoli and Bengasi. Families without children are not counted, so the totals
are families *with* children: 125,079 of the 184,137 Libyan families.

## Checks

  sizes       the families by number of children add to the total, for each
              age limit; so do the children
  categories  the nine activities of the head add to the Totale line
  children    the children in families with k children equal k times those
              families, for k = 1 to 8, in every cell; families with 9 or more
              hold at least nine children each
  nesting     families with a child under 6 <= under 15 <= under 21 <= any
              age, on every line
  religion    Muslim plus Jewish never exceed the whole
  table XXIII no activity has more families with children than table XXIII
              counts families

Three cells were misread on first transcription, all in bold totals, and
corrected where the row, the column and the k-times identity agreed: Libya's
total of families with three children under 15 (23,883), and with three and
seven children under 21 (24,706 and 1,061).

Outputs, under data/processed/istat/:
  libya_1936_libyan_children.csv   long: area, measure (families or
                                   children), religion, activity, age limit,
                                   number of children, value
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"

LIMITS = ("u6", "u15", "u21", "any")
LIMIT_LABEL = {"u6": "under 6", "u15": "under 15", "u21": "under 21",
               "any": "any age"}
KS = [str(k) for k in range(1, 9)] + ["9plus"]
NUMBERS = [f"{a}_{k}" for a in LIMITS for k in KS + ["total"]]
CATS = ("agricoltura", "industria", "trasporti", "commercio", "libere_culto",
        "amministrazione", "domestica", "non_professionali",
        "senza_indicazione")
RELIGION23 = {"complesso": "all", "mussulmani": "muslim", "ebrei": "jewish"}


def read():
    rows = []
    for row in csv.DictReader((RAW / "libya_1936_table25.csv").open()):
        for column in NUMBERS:
            row[column] = int(row[column])
        rows.append(row)
    return rows


def audit(rows):
    trouble = []
    by = {(r["area"], r["measure"], r["religion"], r["activity_of_head"]): r
          for r in rows}
    for r in rows:
        who = (f"{r['area']} {r['measure']} {r['religion']} "
               f"{r['activity_of_head']}")
        for a in LIMITS:
            if sum(r[f"{a}_{k}"] for k in KS) != r[f"{a}_total"]:
                trouble.append(f"{who} {a}: sizes do not add to the total")
        if r["measure"] == "families":
            totals = [r[f"{a}_total"] for a in LIMITS]
            if totals != sorted(totals):
                trouble.append(f"{who}: the age limits are not nested")
            kids = by[(r["area"], "children", r["religion"],
                       r["activity_of_head"])]
            for a in LIMITS:
                for k in KS[:-1]:
                    if kids[f"{a}_{k}"] != int(k) * r[f"{a}_{k}"]:
                        trouble.append(f"{who} {a} k={k}: {kids[f'{a}_{k}']} "
                                       f"children for {r[f'{a}_{k}']} families")
                if kids[f"{a}_9plus"] < 9 * r[f"{a}_9plus"]:
                    trouble.append(f"{who} {a}: too few children in families "
                                   f"of nine or more")
    keys = {(r["area"], r["measure"], r["religion"]) for r in rows}
    for area, measure, religion in keys:
        total = by[(area, measure, religion, "totale")]
        for column in NUMBERS:
            got = sum(by[(area, measure, religion, c)][column] for c in CATS)
            if got != total[column]:
                trouble.append(f"{area} {measure} {religion} {column}: "
                               f"activities sum to {got:,}")
        if religion == "complesso":
            for c in CATS + ("totale",):
                for column in NUMBERS:
                    parts = (by[(area, measure, "mussulmani", c)][column]
                             + by[(area, measure, "ebrei", c)][column])
                    if parts > by[(area, measure, religion, c)][column]:
                        trouble.append(f"{area} {measure} {c} {column}: "
                                       f"Muslim and Jewish exceed the whole")
    return trouble


def against_xxiii(rows):
    xxiii = {r["religion"]: r for r in csv.DictReader(
        (RAW / "libya_1936_table23.csv").open()) if r["area"] == "LIBIA"}
    trouble, checked = [], 0
    for r in rows:
        if r["area"] != "Libia" or r["measure"] != "families":
            continue
        twin = xxiii[RELIGION23[r["religion"]]]
        c = r["activity_of_head"]
        families = int(twin["families"] if c == "totale" else twin[f"{c}_f"])
        if r["any_total"] > families:
            trouble.append(f"{r['religion']} {c}: {r['any_total']:,} families "
                           f"with children, table XXIII has {families:,}")
        else:
            checked += 1
    return trouble, checked


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    rows = read()
    trouble = audit(rows)
    more, checked = against_xxiii(rows)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    long = []
    for r in rows:
        for a in LIMITS:
            for k in KS + ["total"]:
                long.append({"area": r["area"], "measure": r["measure"],
                             "religion": r["religion"],
                             "activity_of_head": r["activity_of_head"],
                             "children_age": LIMIT_LABEL[a],
                             "number_of_children": k.replace("9plus", "9+"),
                             "value": r[f"{a}_{k}"]})
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "libya_1936_libyan_children.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(long[0]))
        writer.writeheader()
        writer.writerows(long)
    print(f"{path.name:36s} {len(long):5d} rows")

    by = {(r["area"], r["measure"], r["religion"], r["activity_of_head"]): r
          for r in rows}
    print()
    for religion in ("mussulmani", "ebrei"):
        fam = by[("Libia", "families", religion, "totale")]
        kids = by[("Libia", "children", religion, "totale")]
        print(f"  {religion:10s} {fam['any_total']:7,d} families with "
              f"children, {kids['any_total'] / fam['any_total']:.2f} each; "
              f"{fam['any_9plus']:,} with nine or more")
    print("\n  [ok ] sizes, activities, k-times, nesting and religion checks "
          "pass on every line")
    print(f"  [ok ] {checked} lines fit within table XXIII's families")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
