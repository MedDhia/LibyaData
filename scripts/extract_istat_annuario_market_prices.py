#!/usr/bin/env python3
"""
Quantities and prices of produce sold in the markets of Libya, 1937 to 1939,
from the `Annuario Statistico Italiano`.

Source: three pages of the colonial chapter, **transcribed by eye** into
`data/raw/istat/libya_annuario_market_prices.csv`, one row per printed cell
with the cell as printed (`printed`) and as a number (`value`):

  1938 volume, pdf 332  the markets of Tripoli, Misurata, Bengasi and Derna
                        in 1937: quantities sold of 23 products, and the
                        lowest and highest price of each
  1939 volume, pdf 365  the markets of the Sahara Libico (Brach, Cufra, Gat,
                        Hon, Murzuch) in 1938: the lowest and highest monthly
                        average price of six products
  1941 volume, pdf 353  the same markets and products in 1939

The 1941 page is not in `libya_annuario_index.csv`: its chapter heading is
read, but the table heading is not. The index finds 1941 with one table.

## Blanks, dashes and question marks

A dash means the product was not sold there: a zero for a quantity, a blank
for a price. A question mark means the figure was not known: a blank, with a
note. One quantity is blank because the scan destroyed a digit (Bengasi,
firewood, printed `5 4?3` quintals).

## Checks

These tables print no totals, so there is no sum to check against. What is
checked:

  * every lowest price is at most the highest price for the same market,
    product and year;
  * each product has one unit throughout (lire per quintal, per kilogram,
    per litre, each, or per four eggs), except where a footnote changes it;
  * every `value` is the number the `printed` cell shows.

Output: data/processed/istat/libya_annuario_market_prices.csv
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat" / "libya_annuario_market_prices.csv"
OUT = ROOT / "data" / "processed" / "istat"

REGION = {"Tripoli": "Tripolitania", "Misurata": "Tripolitania",
          "Bengasi": "Cyrenaica", "Derna": "Cyrenaica",
          "Brach": "Sahara Libico", "Cufra": "Sahara Libico",
          "Gat": "Sahara Libico", "Hon": "Sahara Libico",
          "Murzuch": "Sahara Libico"}


def read():
    with RAW.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def audit(rows, bad):
    checked = 0
    for r in rows:
        p, v = r["printed"], r["value"]
        if p in ("-", "\u2014"):
            want = "0" if r["measure"] == "quantity_sold" else ""
        elif "?" in p:
            want = ""
        else:
            want = p.replace(" ", "").replace(",", ".")
        if v != want:
            bad.append(f"{r['market']} {r['product']} {r['measure']}: value "
                       f"{v!r} for printed {p!r}")
        if want == "" and not r["note"]:
            bad.append(f"{r['market']} {r['product']} {r['measure']}: blank "
                       f"without a note")
    pairs = defaultdict(dict)
    for r in rows:
        if r["measure"] != "quantity_sold" and r["value"]:
            kind = r["measure"].rsplit("_", 1)
            pairs[(r["year"], r["market"], r["product"], kind[0])][kind[1]] = \
                float(r["value"])
    for k, d in pairs.items():
        if {"min", "max"} <= set(d):
            checked += 1
            if d["min"] > d["max"]:
                bad.append(f"{k}: lowest {d['min']} > highest {d['max']}")
    units = defaultdict(set)
    for r in rows:
        if not r["note"].startswith("the volume gives this cell"):
            units[(r["product"], r["measure"] == "quantity_sold")].add(r["unit"])
    for k, u in units.items():
        if len(u) > 1:
            bad.append(f"{k}: more than one unit {sorted(u)}")
    stray = {r["market"] for r in rows} - REGION.keys()
    if stray:
        bad.append(f"markets with no region: {sorted(stray)}")
    return checked


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    rows = read()
    bad = []
    checked = audit(rows, bad)
    if bad:
        print(f"{len(bad)} checks failed:")
        for b in bad[:40]:
            print(f"  {b}")
        sys.exit(1)
    out = [{"year": r["year"], "region": REGION[r["market"]],
            "market": r["market"], "product": r["product"],
            "measure": r["measure"], "unit": r["unit"], "value": r["value"],
            "printed": r["printed"], "volume": r["volume"],
            "pdf_page": r["pdf_page"], "note": r["note"]} for r in rows]
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "libya_annuario_market_prices.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"  wrote libya_annuario_market_prices.csv: {len(out)} rows")
    wheat = {(r["market"], r["measure"]): r["value"] for r in rows
             if r["product"] == "wheat" and r["year"] in ("1937", "1939")}
    known = sum(1 for r in rows if r["value"] != "")
    print()
    print(f"  wheat, lire per quintal: Tripoli {wheat[('Tripoli', 'price_min')]}"
          f" to {wheat[('Tripoli', 'price_max')]} in 1937; Brach "
          f"{wheat[('Brach', 'average_price_min')]} to "
          f"{wheat[('Brach', 'average_price_max')]} in 1939")
    print(f"  {known} of {len(rows)} cells carry a figure")
    print(f"\n  [ok ] {checked} lowest prices at most their highest; one "
          f"unit per product; every value is its printed cell")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
