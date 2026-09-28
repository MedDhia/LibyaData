#!/usr/bin/env python3
"""
Table XXX of the 1936 census: the Libyan population by age, sex, civil status
and religion.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione III, Popolazione libica, Tavola XXX, printed pages 104 to 109.

**Transcribed by eye** and validated before anything is published. The
transcription is committed as `data/raw/istat/libya_1936_table30.csv` and is
the source.

## What it holds

The 750,851 Libyans resident in April 1936 by five-year age class (ten-year
above 70), sex and civil status: `celibi e nubili` (never married),
`coniugati`, `vedovi`, `divorziati` and `ignoto`. Each province and the
Territorio Militare del Sud is given for the whole population (`complesso`,
which includes the few of another or unknown religion), for Muslims and, except
for the Territorio, for Jews; and the four municipi of Tripoli, Misurata,
Bengasi and Derna are given for the whole population.

The Territorio prints no Jewish block: its 16 non-Muslims are the Jews
table XXII puts there. The check below confirms it from this table alone.

## Checks

  sex          M + F = MF in all six blocks of every line
  status       the five civil states add to the total, for MF, M and F
  age          the age classes add to the Totale line, in every column
  province     the four provinces and the Territorio add to Libya, for the
               whole population and for Muslims; the four provinces add to
               Libya for Jews, leaving exactly the Territorio's non-Muslims
  religion     Muslims plus Jews never exceed the whole
  table XXII   the totals by sex and religion equal table XXII's resident
               Libyans, per province and for Libya

Outputs, under data/processed/istat/:
  libya_1936_libyan_age.csv   long: area, religion, age, status, sex, persons
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

STATES = ("tot", "celibi", "coniugati", "vedovi", "divorziati", "ignoto")
SEXES = ("mf", "m", "f")
NUMBERS = [f"{s}_{x}" for s in STATES for x in SEXES]
PROVINCES = ("Provincia di Tripoli", "Provincia di Misurata",
             "Provincia di Bengasi", "Provincia di Derna",
             "Territorio Militare del Sud")


def read():
    rows = []
    for row in csv.DictReader((RAW / "libya_1936_table30.csv").open()):
        for column in NUMBERS:
            row[column] = int(row[column])
        rows.append(row)
    return rows


def audit(rows):
    trouble = []
    blocks = defaultdict(dict)
    for r in rows:
        blocks[(r["area"], r["religion"])][r["age"]] = r
        who = f"{r['area']} {r['religion']} {r['age']}"
        for s in STATES:
            if r[f"{s}_m"] + r[f"{s}_f"] != r[f"{s}_mf"]:
                trouble.append(f"{who} {s}: M + F")
        for x in SEXES:
            got = sum(r[f"{s}_{x}"] for s in STATES[1:])
            if got != r[f"tot_{x}"]:
                trouble.append(f"{who} {x}: the civil states sum to {got:,}")
    for key, lines in blocks.items():
        for column in NUMBERS:
            got = sum(v[column] for a, v in lines.items() if a != "Totale")
            if got != lines["Totale"][column]:
                trouble.append(f"{key} {column}: ages sum to {got:,}")
    for religion, members in (("complesso", PROVINCES),
                              ("mussulmani", PROVINCES)):
        for age, top in blocks[("Libia", religion)].items():
            for column in NUMBERS:
                got = sum(blocks[(p, religion)][age][column] for p in members)
                if got != top[column]:
                    trouble.append(f"Libia {religion} {age} {column}: "
                                   f"provinces {got:,}")
    south = "Territorio Militare del Sud"
    for age, top in blocks[("Libia", "ebrei")].items():
        for column in NUMBERS:
            rest = top[column] - sum(blocks[(p, "ebrei")][age][column]
                                     for p in PROVINCES[:4])
            others = (blocks[(south, "complesso")][age][column]
                      - blocks[(south, "mussulmani")][age][column])
            if rest != others:
                trouble.append(f"Libia ebrei {age} {column}: {rest} left for "
                               f"the Territorio, which has {others} "
                               f"non-Muslims")
    for (area, religion), lines in blocks.items():
        if religion != "complesso":
            continue
        for age, whole in lines.items():
            for column in NUMBERS:
                parts = sum(blocks.get((area, g), {}).get(age, {}).get(
                    column, 0) for g in ("mussulmani", "ebrei"))
                if parts > whole[column]:
                    trouble.append(f"{area} {age} {column}: Muslims and Jews "
                                   f"exceed the whole")
    return trouble


def against_xxii(rows):
    if not RESIDENT.exists():
        return ["libya_1936_libyans_resident.csv is missing"], 0
    lines = defaultdict(dict)
    for r in csv.DictReader(RESIDENT.open()):
        lines[r["name"]][r["dimora"]] = r
    trouble, checked = [], 0
    names = {"Libia": "LIBIA"}
    for r in rows:
        if r["age"] != "Totale" or r["area"].startswith("di cui"):
            continue
        kinds = lines[names.get(r["area"], r["area"])]
        twin = kinds.get("Tot") or next(iter(kinds.values()))
        pairs = {"complesso": (("tot_mf", "mf"), ("tot_f", "f")),
                 "mussulmani": (("tot_mf", "muslim"),),
                 "ebrei": (("tot_mf", "jewish"),)}[r["religion"]]
        for mine, theirs in pairs:
            if r[mine] != int(twin[theirs]):
                trouble.append(f"{r['area']} {r['religion']} {mine}: "
                               f"{r[mine]:,}, table XXII {int(twin[theirs]):,}")
            else:
                checked += 1
    return trouble, checked


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    rows = read()
    trouble = audit(rows)
    more, checked = against_xxii(rows)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    long = []
    for r in rows:
        for s in STATES:
            for x in SEXES:
                long.append({"area": r["area"], "religion": r["religion"],
                             "age": r["age"],
                             "civil_status": "all" if s == "tot" else s,
                             "sex": x.upper(), "persons": r[f"{s}_{x}"]})
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "libya_1936_libyan_age.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(long[0]))
        writer.writeheader()
        writer.writerows(long)
    print(f"{path.name:36s} {len(long):5d} rows")
    report(rows, checked)


def report(rows, checked):
    by = {(r["area"], r["religion"], r["age"]): r for r in rows}
    libya = by[("Libia", "complesso", "Totale")]
    young = sum(by[("Libia", "complesso", a)]["tot_mf"]
                for a in ("0-4", "5-9", "10-14"))
    girls = by[("Libia", "complesso", "15-19")]
    print()
    print(f"Libya 1936, Libyan residents: {libya['tot_mf']:,}, "
          f"{libya['tot_m'] / libya['tot_f'] * 100:.0f} men per 100 women; "
          f"{young / libya['tot_mf']:.0%} under fifteen")
    print(f"  women 15-19: {girls['coniugati_f'] / girls['tot_f']:.0%} married; "
          f"men 15-19: {girls['coniugati_m'] / girls['tot_m']:.0%}")
    print(f"  widowed: {libya['vedovi_f']:,} women and {libya['vedovi_m']:,} "
          f"men; divorced: {libya['divorziati_f']:,} women and "
          f"{libya['divorziati_m']:,} men")
    print("\n  [ok ] sex, civil status, age, province and religion identities "
          "hold in every line")
    print(f"  [ok ] {checked} figures agree with table XXII")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
