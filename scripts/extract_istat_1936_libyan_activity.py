#!/usr/bin/env python3
"""
Tables XXXI and XXXII of the 1936 census: the Libyan population by economic
activity.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione III, Popolazione libica, Tavole XXXI and XXXII, printed pages 110 to
115.

**Transcribed by eye** and validated before anything is published. The
transcriptions are committed as `data/raw/istat/libya_1936_table31.csv` and
`libya_1936_table32.csv` and are the source.

## What they hold

  XXXI   Libyans resident aged 10 and over, by category of economic activity,
         sex and religion, for the provinces, the Territorio and the four
         municipi. Nine categories: agriculture, industry, transport,
         commerce, liberal professions and religion, administration, domestic
         service, `condizioni non professionali` (housewives, students,
         dependants) and `senza indicazione`.
  XXXII  every Libyan resident, by circumscription (the same 83 plus Libya as
         tables XXI and XXII) and by dimora (settled, seminomadic, nomadic),
         split into the active population by seven categories and the
         inactive. The printed percentages are derived and not transcribed.

## Checks, and four crossings to other tables

  XXXI     M + F = MF; the nine categories add to the total; provinces add to
           Libya; Muslims and Jews never exceed the whole
  XXXII    the seven categories add to the active; active plus inactive is the
           population; the dimora lines add to the Tot. line; children add to
           parents and the provinces to Libya
  XXII     every line of XXXII, 229 of them, has table XXII's resident
           population for that circumscription and dimora
  XXX      XXXI's population aged 10 and over is table XXX's population less
           the 0-4 and 5-9 classes, by sex and religion, per province
  XXXI     XXXII's seven active categories per province equal XXXI's; and
           XXXII's inactive equals XXXI's non-professional and unstated plus
           the children under ten

One cell was corrected on first reading: the Circondario di Barce's
agriculture in XXXII prints a worn bold 4.819 that reads as 4.319; its row,
its three distretti and its province each give 4,819.

Outputs, under data/processed/istat/:
  libya_1936_libyan_activity.csv       XXXI, long: religion, area, activity,
                                       sex, persons
  libya_1936_libyan_activity_dimora.csv  XXXII, one row per circumscription
                                       and dimora, as printed
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
AGE = RAW / "libya_1936_table30.csv"

CATS = ("agricoltura", "industria", "trasporti", "commercio", "libere_culto",
        "amministrazione", "domestica", "non_professionali",
        "senza_indicazione")
ACTIVE = CATS[:7]
PROVINCES = ("Provincia di Tripoli", "Provincia di Misurata",
             "Provincia di Bengasi", "Provincia di Derna",
             "Territorio Militare del Sud")
N31 = [f"{c}_{x}" for c in ("totale",) + CATS for x in ("mf", "m", "f")]
N32 = ["residents", *ACTIVE, "active", "inactive"]


def read(name, numbers):
    rows = []
    for row in csv.DictReader((RAW / name).open()):
        for column in numbers:
            row[column] = int(row[column])
        rows.append(row)
    return rows


def audit_31(rows):
    trouble = []
    by = {(r["religion"], r["area"]): r for r in rows}
    for r in rows:
        who = f"XXXI {r['religion']} {r['area']}"
        for c in ("totale",) + CATS:
            if r[f"{c}_m"] + r[f"{c}_f"] != r[f"{c}_mf"]:
                trouble.append(f"{who} {c}: M + F")
        for x in ("mf", "m", "f"):
            if sum(r[f"{c}_{x}"] for c in CATS) != r[f"totale_{x}"]:
                trouble.append(f"{who} {x}: categories")
    for religion in ("complesso", "mussulmani", "ebrei"):
        for column in N31:
            got = sum(by[(religion, p)][column] for p in PROVINCES)
            if got != by[(religion, "Libia")][column]:
                trouble.append(f"XXXI {religion} {column}: provinces")
    for (religion, area), r in by.items():
        if religion == "complesso":
            for column in N31:
                if (by[("mussulmani", area)][column]
                        + by[("ebrei", area)][column] > r[column]):
                    trouble.append(f"XXXI {area} {column}: Muslims and Jews")
    return trouble


def audit_32(rows):
    trouble = []
    for r in rows:
        who = f"XXXII {r['order']} {r['name']} {r['dimora']}"
        if sum(r[c] for c in ACTIVE) != r["active"]:
            trouble.append(f"{who}: categories do not add to the active")
        if r["active"] + r["inactive"] != r["residents"]:
            trouble.append(f"{who}: active plus inactive")
    lines = defaultdict(dict)
    for r in rows:
        lines[r["name"]][r["dimora"]] = r
    for name, kinds in lines.items():
        if "Tot" in kinds:
            for column in N32:
                got = sum(kinds[d][column] for d in ("st", "sn", "n")
                          if d in kinds)
                if got != kinds["Tot"][column]:
                    trouble.append(f"XXXII {name} {column}: dimora lines")
    top = {n: k.get("Tot") or next(iter(k.values())) for n, k in lines.items()}
    kids = defaultdict(list)
    for r in top.values():
        if r["parent"]:
            kids[r["parent"]].append(r)
    for parent, ks in kids.items():
        for column in N32:
            if sum(k[column] for k in ks) != top[parent][column]:
                trouble.append(f"XXXII {parent} {column}: children")
    return trouble


def crossings(xxxi, xxxii):
    trouble, counts = [], defaultdict(int)
    resident = [r for r in csv.DictReader(RESIDENT.open())]
    for mine, theirs in zip(xxxii, resident):
        if (mine["name"], mine["dimora"]) != (theirs["name"], theirs["dimora"]):
            trouble.append(f"XXXII line {mine['order']} is out of step with "
                           f"table XXII")
            break
        if mine["residents"] != int(theirs["mf"]):
            trouble.append(f"XXXII {mine['name']} {mine['dimora']}: "
                           f"{mine['residents']:,} vs table XXII {theirs['mf']}")
        else:
            counts["XXII"] += 1

    ages = defaultdict(dict)
    for r in csv.DictReader(AGE.open()):
        ages[(r["area"], r["religion"])][r["age"]] = r
    by31 = {(r["religion"], r["area"]): r for r in xxxi}
    for (religion, area), r in by31.items():
        block = ages.get((area, religion))
        if not block:
            continue
        for x in ("mf", "m", "f"):
            want = (int(block["Totale"][f"tot_{x}"])
                    - int(block["0-4"][f"tot_{x}"])
                    - int(block["5-9"][f"tot_{x}"]))
            if r[f"totale_{x}"] != want:
                trouble.append(f"XXXI {religion} {area} {x}: {r[f'totale_{x}']:,}"
                               f", table XXX gives {want:,} aged 10 and over")
            else:
                counts["XXX"] += 1

    top32 = {}
    for r in xxxii:
        if r["dimora"] in ("Tot", "st") and r["name"] not in top32:
            top32[r["name"]] = r
    top32["Libia"] = top32["LIBIA"]
    for area in PROVINCES + ("Libia",):
        mine, theirs = top32[area], by31[("complesso", area)]
        for c in ACTIVE:
            if mine[c] != theirs[f"{c}_mf"]:
                trouble.append(f"XXXII {area} {c}: {mine[c]:,}, XXXI "
                               f"{theirs[f'{c}_mf']:,}")
            else:
                counts["XXXI"] += 1
        under10 = mine["residents"] - theirs["totale_mf"]
        idle = (theirs["non_professionali_mf"] + theirs["senza_indicazione_mf"]
                + under10)
        if mine["inactive"] != idle:
            trouble.append(f"XXXII {area} inactive: {mine['inactive']:,}, "
                           f"XXXI and XXX give {idle:,}")
        else:
            counts["XXXI"] += 1
    return trouble, counts


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    xxxi = read("libya_1936_table31.csv", N31)
    xxxii = read("libya_1936_table32.csv", N32)
    trouble = audit_31(xxxi) + audit_32(xxxii)
    if not RESIDENT.exists():
        trouble.append("libya_1936_libyans_resident.csv is missing; run "
                       "scripts/extract_istat_1936_libyans.py first")
    else:
        more, counts = crossings(xxxi, xxxii)
        trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    long = []
    for r in xxxi:
        for c in ("totale",) + CATS:
            for x in ("mf", "m", "f"):
                long.append({"religion": r["religion"], "area": r["area"],
                             "activity": "all" if c == "totale" else c,
                             "sex": x.upper(), "persons": r[f"{c}_{x}"]})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows, fields in (
            ("libya_1936_libyan_activity.csv", long, list(long[0])),
            ("libya_1936_libyan_activity_dimora.csv", xxxii,
             ["order", "name", "level", "parent", "dimora"] + N32)):
        with (OUT / name).open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields,
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"{name:40s} {len(rows):5d} rows")
    report(xxxi, xxxii, counts)


def report(xxxi, xxxii, counts):
    libya = next(r for r in xxxi if r["religion"] == "complesso"
                 and r["area"] == "Libia")
    lines = {(r["name"], r["dimora"]): r for r in xxxii}
    print()
    print(f"Libya 1936, Libyans aged 10 and over: {libya['totale_mf']:,}; "
          f"{libya['agricoltura_mf'] / libya['totale_mf']:.0%} in agriculture, "
          f"{libya['non_professionali_mf'] / libya['totale_mf']:.0%} without a "
          f"profession")
    print(f"  women: {libya['agricoltura_f']:,} of {libya['totale_f']:,} "
          f"recorded in agriculture, {libya['non_professionali_f']:,} without "
          f"a profession")
    for d, label in (("st", "settled"), ("sn", "seminomadic"),
                     ("n", "nomadic")):
        r = lines[("LIBIA", d)]
        print(f"  {label:12s} {r['active'] / r['residents']:.0%} active, "
              f"{r['agricoltura'] / r['active']:.0%} of them in agriculture")
    print("\n  [ok ] every printed identity holds in both tables")
    print(f"  [ok ] {counts['XXII']} lines of XXXII carry table XXII's "
          f"residents; {counts['XXX']} figures of XXXI agree with table XXX; "
          f"{counts['XXXI']} figures agree between XXXI and XXXII")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
