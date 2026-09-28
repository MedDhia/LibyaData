#!/usr/bin/env python3
"""
Railway traffic in Libya, 1923-24 to 1935-36, from the `Annuario Statistico
Italiano`.

Source: the `Traffico ferroviario` tables of the colonial chapter in the 1930
to 1938 volumes, **transcribed by eye** from eleven pages into
`data/raw/istat/libya_annuario_railways.csv`, one row per printing, with the
year as printed.

Passengers carried and tonnes of freight for the railways of Tripolitania and
Cyrenaica by financial year (July to June), and the length of each network.

## Two freight measures

The volumes change their freight column. Up to 1932 Tripolitania prints
`Merci` (goods); from 1933 it prints `Merci e bagagli` (goods and baggage), and
the 1933 volume restates 1927-28 to 1930-31 on the wider basis: 170,243
tonnes of goods in 1927-28 become 171,000 tonnes of goods and baggage.
Cyrenaica prints goods and baggage throughout. The two are kept apart in
`freight_heading` and never compared with each other.

## Checks

The tables print no totals. What holds them is repetition: most years are
printed in three to five volumes. Every figure printed more than once must
agree across volumes, except:

  * a year label the 1931 volume misprints (MISPRINTS): its last Cyrenaica
    row reads 1929-930, but its figures (101,115 passengers, 35,248 tonnes)
    are those the 1932 and 1933 volumes both print for 1928-29, and both
    print different figures for 1929-30;
  * a revision the later volumes make (REVISIONS): Tripolitania's 1932-33
    freight, 191,698 tonnes in the 1934 volume and 194,037 in the 1936, 1937
    and 1938 volumes. No footnote announces it. The latest figure is
    published and the earlier one kept as superseded.

Outputs, under data/processed/istat/:
  libya_annuario_railways.csv            one row per colony, year, measure
  libya_annuario_railways_printings.csv  every printing
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat" / "libya_annuario_railways.csv"
OUT = ROOT / "data" / "processed" / "istat"

KEY = ("colony", "year", "measure", "freight_heading")

# (volume, colony, year as printed) -> year it belongs to
MISPRINTS = {("1931", "Cirenaica", "1929-30"): "1928-29"}
# (colony, year, measure) -> the volume whose figure replaces earlier ones
REVISIONS = {("Tripolitania", "1932-33", "freight_tonnes"): "1936"}


def read():
    with RAW.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["year_printed"] = r["year"]
        fixed = MISPRINTS.get((r["volume"], r["colony"], r["year"]))
        if fixed:
            r["year"] = fixed
            r["note"] = (f"the {r['volume']} volume prints the year as "
                         f"{r['year_printed']}; the 1932 and 1933 volumes "
                         f"print these figures for {fixed}")
        r["value"] = None if r["printed"] == "?" else int(r["printed"])
    return rows


def reconcile(rows, bad):
    by = defaultdict(list)
    for r in rows:
        if r["value"] is not None:
            by[tuple(r[k] for k in KEY)].append(r)
    series, printings, revised = [], [], 0
    for key, rs in by.items():
        rs.sort(key=lambda r: int(r["volume"]))
        latest = rs[-1]["value"]
        values = {r["value"] for r in rs}
        status_of = {}
        if len(values) > 1:
            reviser = REVISIONS.get(key[:3])
            first_new = next(r["volume"] for r in rs if r["value"] == latest)
            if reviser != first_new or any(
                    r["value"] != latest for r in rs
                    if int(r["volume"]) >= int(reviser)):
                bad.append(f"{key}: printings differ "
                           f"{[(r['volume'], r['value']) for r in rs]}")
            revised += 1
        for r in rs:
            status_of[id(r)] = ("published" if r["value"] == latest else
                                f"superseded by the {rs[-1]['volume']} volume")
            printings.append(dict(zip(KEY, key), value=r["value"],
                                  volume=r["volume"], pdf_page=r["pdf_page"],
                                  year_printed=r["year_printed"],
                                  status=status_of[id(r)], note=r["note"]))
        series.append(dict(zip(KEY, key), value=latest, printings=len(rs),
                           volumes=" ".join(r["volume"] for r in rs),
                           agreement=("revised" if len(values) > 1 else
                                      "agree" if len(rs) > 1 else
                                      "single printing"),
                           note=next((r["note"] for r in rs if r["note"]),
                                     "")))
    missing = set(REVISIONS) - {tuple(s[k] for k in KEY[:3]) for s in series
                                if s["agreement"] == "revised"}
    if missing:
        bad.append(f"revisions on record but not found: {missing}")
    return series, printings, revised


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    rows = read()
    bad = []
    for r in rows:
        if r["measure"] == "freight_tonnes" and r["freight_heading"] not in (
                "goods", "goods and baggage"):
            bad.append(f"{r}: freight without a heading")
    series, printings, revised = reconcile(rows, bad)
    if bad:
        print(f"{len(bad)} checks failed:")
        for b in bad[:40]:
            print(f"  {b}")
        sys.exit(1)
    series.sort(key=lambda s: (s["colony"], s["measure"],
                               s["freight_heading"], s["year"]))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("libya_annuario_railways.csv", series),
                       ("libya_annuario_railways_printings.csv", printings)):
        with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
        print(f"  wrote {name}: {len(data)} rows")
    pas = {(s["colony"], s["year"]): s["value"] for s in series
           if s["measure"] == "passengers"}
    repeated = sum(1 for s in series if s["printings"] > 1)
    print()
    print(f"  passengers, Tripolitania: {pas[('Tripolitania', '1923-24')]:,} "
          f"in 1923-24, {pas[('Tripolitania', '1935-36')]:,} in 1935-36")
    print(f"\n  [ok ] {repeated} of {len(series)} figures printed more than "
          f"once agree, apart from {revised} revision and "
          f"{len(MISPRINTS)} misprinted year on record")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
