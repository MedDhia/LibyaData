#!/usr/bin/env python3
"""
Table IV of the 1936 census: where the settlers were, and where they lived.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`, Tavola
IV, `Popolazione presente, temporaneamente assente, residente, distinta secondo
il carattere della dimora, il luogo ove si trovava l'assente e il sesso`,
printed pages 5 and 6.

**Transcribed by eye**, like the other 1931 and 1936 tables, and validated
before anything is published. The transcription is committed as
`data/raw/istat/libya_1936_table4.csv` and is the source.

## What it counts, which is narrower than tables I to III

**Only the `nazionale, straniera e assimilata` population**: Italians from the
Kingdom, other foreigners and the small assimilated group, 115,637 present and
66,525 resident. The Libyan population, 732,973 present, is not in this table.
Use `libya_1936_circumscriptions.csv` for the whole population.

What it adds is the question of who was actually living there, and it gives the
answer in one number: **52,421 of the 115,637 counted were `occasionale`,
present without a habitual dwelling**. Forty-five per cent of the Italian and
foreign presence in Libya in April 1936 was passing through, and that is the
Ethiopian war showing up in a census. It concentrates where the building and
the shipping were. The Circondario di Tòbruch counted 15,238 present and 975
habitual; Derna 13,163 and 1,925; Barce 11,043 and 1,762. In the four provinces
of the west, where the settlement was older, the ratio reverses: the Circondario
di Tripoli counted 34,506 present and 30,044 habitual.

The absent are given by where they were: in another circumscription of Libya, in
the Kingdom, or elsewhere. Of 3,309 absent residents, 1,884 were elsewhere in
Libya and 867 in Italy.

## Five checks, and the fifth crosses to another table

  dimora      present = abituale + occasionale, for the whole population and
              for women
  where       the absent split by place sums to the absent in complesso
  residence   resident = abituale + temporaneamente assente, the definition the
              table works to
  hierarchy   every parent equals the sum of the rows under it, and the
              provinces sum to Libya
  table II    the population present and resident here equals `nazionale` plus
              `straniera` in table II, row by row and for women separately

The last binds this transcription to one made from a different page: 276 figures
agree. The table passed all five on the first reading.

Outputs, under data/processed/istat/:
  libya_1936_residents.csv   69 rows, the same circumscriptions as table II
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1936_circumscriptions import (  # noqa: E402
    COLONY, key_of, place)
from libya_places import gazetteer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
SOURCE = RAW / "libya_1936_table4.csv"
CIRCUMSCRIPTIONS = OUT / "libya_1936_circumscriptions.csv"

BLOCKS = ("present", "habitual", "occasional", "absent", "absent_libya",
          "absent_kingdom", "absent_elsewhere", "resident")
NUMBERS = [f"{b}_{s}" for b in BLOCKS for s in ("mf", "f")]


def read():
    rows = []
    for row in csv.DictReader(SOURCE.open()):
        for column in NUMBERS:
            row[column] = int(row[column])
        rows.append(row)
    return rows


def audit(rows):
    trouble = []
    by_name = {r["name"]: r for r in rows}
    children = {}
    for row in rows:
        if row["parent"]:
            children.setdefault(row["parent"], []).append(row)

    for row in rows:
        for sex in ("mf", "f"):
            if row[f"habitual_{sex}"] + row[f"occasional_{sex}"] != row[f"present_{sex}"]:
                trouble.append(f"{row['name']} {sex}: habitual and occasional "
                               f"do not add to present")
            where = sum(row[f"absent_{w}_{sex}"]
                        for w in ("libya", "kingdom", "elsewhere"))
            if where != row[f"absent_{sex}"]:
                trouble.append(f"{row['name']} {sex}: the absent by place sum "
                               f"to {where:,}, the row says {row[f'absent_{sex}']:,}")
            if row[f"habitual_{sex}"] + row[f"absent_{sex}"] != row[f"resident_{sex}"]:
                trouble.append(f"{row['name']} {sex}: habitual plus absent is "
                               f"not the resident population")
        for block in BLOCKS:
            if row[f"{block}_f"] > row[f"{block}_mf"]:
                trouble.append(f"{row['name']} {block}: more women than people")

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

    top = [r for r in rows if r["level"] == "provincia"]
    total = [r for r in rows if r["level"] == "colony"]
    if len(total) == 1:
        for column in NUMBERS:
            got = sum(r[column] for r in top)
            if got != total[0][column]:
                trouble.append(f"Libya {column}: the provinces sum to {got:,}, "
                               f"the table prints {total[0][column]:,}")
    return trouble


def against_table_two(rows):
    """The population here is table II's Italians plus its other foreigners."""
    if not CIRCUMSCRIPTIONS.exists():
        return ["libya_1936_circumscriptions.csv is missing; run "
                "scripts/extract_istat_1936_circumscriptions.py first"], 0
    two = {r["name"]: r for r in csv.DictReader(CIRCUMSCRIPTIONS.open())}
    trouble, checked = [], 0
    for row in rows:
        twin = two.get(row["name"])
        if not twin:
            continue
        for when in ("present", "resident"):
            for sex in ("mf", "f"):
                want = (int(twin[f"{when}_national_{sex}"])
                        + int(twin[f"{when}_foreign_{sex}"]))
                if want != row[f"{when}_{sex}"]:
                    trouble.append(f"{row['name']} {when} {sex}: table II has "
                                   f"{want:,} Italians and foreigners, table IV "
                                   f"has {row[f'{when}_{sex}']:,}")
                else:
                    checked += 1
    return trouble, checked


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    places, shabiya_keys, scrambled = gazetteer()

    rows = read()
    trouble = audit(rows)
    more, checked = against_table_two(rows)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    province = {}
    for row in rows:
        if row["level"] == "provincia":
            province[row["name"]] = row["name"]
        elif row["parent"]:
            province[row["name"]] = province.get(row["parent"], "")
        row["province"] = (row["name"] if row["level"] == "provincia"
                           else province.get(row["name"], ""))
    place(rows, places, shabiya_keys, scrambled,
          lambda r: COLONY.get(r["province"] or r["name"], "Tripolitania"))

    OUT.mkdir(parents=True, exist_ok=True)
    fields = (["province", "level", "name", "parent", "place_ar", "shabiya_ar",
               "shabiya_en", "shabiya_pcode", "shabiya_route"] + NUMBERS
              + ["order", "place_key"])
    path = OUT / "libya_1936_residents.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:36s} {len(rows):5d} rows")
    report(rows, checked)


def report(rows, checked):
    total = next(r for r in rows if r["level"] == "colony")
    share = total["occasional_mf"] / total["present_mf"]
    print()
    print(f"Libya 1936, Italians and other foreigners: "
          f"{total['present_mf']:,} present, of whom "
          f"{total['occasional_mf']:,} ({share:.0%}) without a habitual "
          f"dwelling; {total['resident_mf']:,} resident, "
          f"{total['absent_mf']:,} of them away "
          f"({total['absent_libya_mf']:,} elsewhere in Libya, "
          f"{total['absent_kingdom_mf']:,} in the Kingdom)")
    worst = sorted((r for r in rows if r["level"] == "circondario"),
                   key=lambda r: -(r["occasional_mf"] / max(r["present_mf"], 1)))
    print("  most occasional, by circondario: " + ", ".join(
        f"{r['name'].replace('Circondario di ', '')} "
        f"{r['occasional_mf'] / r['present_mf']:.0%}" for r in worst[:4]))
    print("\n  [ok ] dimora, place of absence, residence, hierarchy and colony "
          "checks pass")
    print(f"  [ok ] {checked} figures agree with table II: this population is "
          f"its Italians plus its other foreigners")
    placed = [r for r in rows if r["shabiya_en"]]
    print(f"{len(placed)} of {len(rows)} rows carry a shabiya "
          f"{dict(Counter(r['shabiya_route'] for r in rows))}")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
