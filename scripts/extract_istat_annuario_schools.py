#!/usr/bin/env python3
"""
Schools in Libya, 1934-35 to 1939-40, from the `Annuario Statistico
Italiano`.

Source: the `Istruzione` tables of the colonial chapter, **transcribed by
eye** into `data/raw/istat/libya_annuario_schools.csv`, one row per printed
line:

  1937 volume, pdf 318, reprinted unchanged in the 1938 volume, pdf 334
      elementary and secondary schools in 1936-37 by type of school (public
      schools of Italian type, for Jews and for Muslims; recognised schools;
      private schools for Europeans, Jews and Muslims; nursery schools) and
      by region, with the totals of 1934-35 and 1935-36
  1939 volume, pdf 365; 1940 volume, pdf 114; 1941 volume, pdf 353
      the elementary schools of the Sahara Libico in 1938-39 and 1939-40

Each line gives schools, classes, and pupils enrolled in all, by sex (boys
only in the 1937 table), by nationality (Italian, Libyan citizen, foreign)
and by religion (Catholic, Muslim, Jewish, other); the Sahara tables add
teachers.

## Checks

  * nationalities add to the pupils, and so do religions, on every line;
    boys and girls add to the pupils where both are printed; boys never
    exceed the pupils;
  * school types add to their subtotal, the subtotals to the whole, and the
    three regions to the same whole, in every column;
  * public plus private schools give the Sahara total;
  * every line printed in two volumes agrees.

Output: data/processed/istat/libya_annuario_schools.csv
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat" / "libya_annuario_schools.csv"
OUT = ROOT / "data" / "processed" / "istat"

NUM = ("schools", "classes", "pupils_mf", "pupils_m", "pupils_f", "italian",
       "libyan", "foreign", "catholic", "muslim", "jewish", "other_religion",
       "teachers")
NATION = ("italian", "libyan", "foreign")
RELIGION = ("catholic", "muslim", "jewish", "other_religion")
LINE = ("area", "school_year", "level", "line_kind", "line")


def read():
    with RAW.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in NUM:
            r[k] = int(r[k]) if r[k] != "" else None
    return rows


def g(r, cols):
    return sum(r[c] or 0 for c in cols)


def audit(rows, bad):
    checked = 0
    for r in rows:
        w = f"{r['volume']} {r['area']} {r['school_year']} {r['line']}"
        for cols in (NATION, RELIGION):
            checked += 1
            if g(r, cols) != r["pupils_mf"]:
                bad.append(f"{w}: {cols[0]}... {g(r, cols)} != "
                           f"{r['pupils_mf']}")
        if r["pupils_f"] is not None:
            checked += 1
            if r["pupils_m"] + r["pupils_f"] != r["pupils_mf"]:
                bad.append(f"{w}: M + F != MF")
        if r["pupils_m"] > r["pupils_mf"]:
            bad.append(f"{w}: boys exceed pupils")
    pages = defaultdict(list)
    for r in rows:
        pages[(r["volume"], r["pdf_page"], r["area"], r["level"])].append(r)

    def add_up(parts, whole, label):
        nonlocal checked
        for c in NUM:
            if whole[c] is None:
                continue
            checked += 1
            if sum(p[c] or 0 for p in parts) != whole[c]:
                bad.append(f"{label} {c}: {sum(p[c] or 0 for p in parts)} "
                           f"!= {whole[c]}")
    for key, rs in pages.items():
        year = max(r["school_year"] for r in rs)
        cur = [r for r in rs if r["school_year"] == year]
        types = [r for r in cur if r["line_kind"] == "type"]
        subt = [r for r in cur if r["line_kind"] == "typetot"]
        totals = [r for r in cur if r["line_kind"] == "total"]
        regions = [r for r in cur if r["line_kind"] == "region"]
        if subt:
            groups, current = [], []
            for r in cur:
                if r["line_kind"] == "type":
                    current.append(r)
                elif r["line_kind"] == "typetot":
                    groups.append((current, r))
                    current = []
            for parts, whole in groups:
                add_up(parts, whole, f"{key} {whole['line']}")
            # a type printed alone (the recognised schools) is its own
            # subtotal
            single = [r for r in cur if r["line_kind"] == "single"]
            add_up(subt + single, totals[0], f"{key} types to whole")
        else:
            add_up(types, totals[0], f"{key} types to whole")
        if regions:
            add_up(regions, totals[-1], f"{key} regions to whole")
            add_up([totals[0]], totals[-1], f"{key} two totals")
    seen = defaultdict(set)
    for r in rows:
        seen[tuple(r[k] for k in LINE)].add(
            (r["volume"], tuple(r[c] for c in NUM)))
    repeated = 0
    for k, s in seen.items():
        if len({v for _, v in s}) > 1:
            bad.append(f"{k}: printings differ")
        if len(s) > 1:
            repeated += 1
    return checked, seen, repeated


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    rows = read()
    bad = []
    checked, seen, repeated = audit(rows, bad)
    if bad:
        print(f"{len(bad)} checks failed:")
        for b in bad[:40]:
            print(f"  {b}")
        sys.exit(1)
    out, done = [], set()
    for r in rows:
        k = tuple(r[c] for c in LINE)
        if k in done:
            continue
        done.add(k)
        vols = sorted({v for v, _ in seen[k]})
        out.append(dict({c: r[c] for c in LINE}, **{c: r[c] for c in NUM},
                        volumes=" ".join(vols), pdf_page=r["pdf_page"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "libya_annuario_schools.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"  wrote libya_annuario_schools.csv: {len(out)} rows")
    tot = next(r for r in out if r["line"] == "In complesso")
    print()
    print(f"  elementary pupils 1936-37: {tot['pupils_mf']:,}, "
          f"{tot['libyan']:,} of them Libyan; {tot['muslim']:,} Muslim, "
          f"{tot['jewish']:,} Jewish")
    print(f"\n  [ok ] {checked} sums hold; {repeated} lines printed in two "
          f"volumes agree")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
