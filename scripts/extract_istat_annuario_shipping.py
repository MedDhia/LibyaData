#!/usr/bin/env python3
"""
Shipping in the ports of Libya, 1921 to 1937, from the `Annuario Statistico
Italiano`.

Source: the colonial chapter of the yearbooks for 1922-1925 to 1938, located
by `scripts/extract_istat_annuario_index.py`: the tables `Navigazione
marittima`, `Movimento della navigazione marittima`, `Movimento generale della
navigazione` and `Movimento della navigazione nei porti della Libia
occidentale / orientale`, 25 pages in twelve volumes.

**Transcribed by eye** from page images, as the trade series was, because the
scans damage the bold total lines. The transcription is committed as
`data/raw/istat/libya_annuario_shipping.csv`, one row per printing: every
volume that prints a figure has its own row, so a year printed four times is
there four times.

## What it holds

Vessels, net registered tonnage, cargo landed or loaded (tonnes) and
passengers landed or embarked, for ships arriving and departing:

  1923-1933  the port of Tripoli, by steam and sail
  1921-1933  the principal ports of Cyrenaica, all vessels together
  1932-1937  every port of Libya by steam and sail and by flag (all flags,
             and Italian), with the colony totals

The earlier tables of 1913 to 1921, `Movimento della navigazione con
l'Italia`, count traffic between Italy and Libya from the Italian side, which
is a different quantity, and are left out, as they were for trade.

## Checks

  * steam plus sail equals the whole, for every measure, wherever a table
    prints all three;
  * the ports add to the colony total wherever a table prints both;
  * Italian-flag figures never exceed all flags;
  * every figure printed in more than one volume agrees across them, except
    where a later volume says it corrected the earlier one. Four such
    revisions are known and listed in REVISIONS, each announced by the revising
    volume's own footnote ("Sono state rettificate alcune cifre pubblicate
    nell'Annuario precedente"). A disagreement anywhere else fails.

The published figure is the latest printing. Earlier printings that differ are
kept in the printings file as `superseded`.

## Source misprint

1938 volume, pdf 330: Apollonia, 1937, ships departed under all flags, sail,
net tonnage printed 2 964. Steam plus sail must give the printed whole,
105 334 - 102 380 = 2 954, and the ports must give the printed colony total
34 023, which also needs 2 954. The raw file keeps 2 964; the series publishes
2 954 with a note.

Outputs, under data/processed/istat/:
  libya_annuario_shipping.csv            one row per port, year, flag,
                                         propulsion and direction
  libya_annuario_shipping_printings.csv  one row per printing of each figure
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat" / "libya_annuario_shipping.csv"
OUT = ROOT / "data" / "processed" / "istat"

MEASURES = ("vessels", "net_tonnage", "cargo_tonnes", "passengers")
KEY = ("colony", "port", "year", "flag", "propulsion", "direction")

# (volume, colony, port, year, flag, propulsion, direction, measure):
#     (printed, corrected)
MISPRINTS = {
    ("1938", "Cirenaica", "Apollonia", "1937", "all", "sail", "departed",
     "net_tonnage"): (2964, 2954),
}

# (colony, port, year) -> the volume that revised figures printed earlier.
REVISIONS = {
    ("Tripolitania", "Tripoli", "1929"): "1933",
    ("Cirenaica", "all ports", "1932"): "1936",
    ("Cirenaica", "all ports", "1933"): "1936",
    ("Tripolitania", "all ports", "1936"): "1938",
}


def order(volume):
    """`1922-1925` sorts by its first year."""
    return int(volume.split("-")[0])


def read():
    rows = []
    with RAW.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            r["printed"] = {m: (int(r[m]) if r[m] != "" else None)
                            for m in MEASURES}
            r["value"] = dict(r["printed"])
            r["notes"] = {}
            for m in MEASURES:
                key = (r["volume"],) + tuple(r[k] for k in KEY) + (m,)
                if key in MISPRINTS:
                    printed, fixed = MISPRINTS[key]
                    if r["printed"][m] != printed:
                        raise SystemExit(f"{key}: expected printed {printed}, "
                                         f"raw has {r['printed'][m]}")
                    r["value"][m] = fixed
                    r["notes"][m] = (f"printed {printed} in the {r['volume']} "
                                     f"volume, corrected to {fixed}: steam "
                                     f"plus sail and the ports' total both "
                                     f"give it")
            rows.append(r)
    return rows


def audit(rows, bad):
    by_prop = defaultdict(dict)
    by_port = defaultdict(dict)
    by_flag = defaultdict(dict)
    for r in rows:
        by_prop[(r["volume"], r["colony"], r["port"], r["year"], r["flag"],
                 r["direction"])][r["propulsion"]] = r
        by_port[(r["volume"], r["colony"], r["year"], r["flag"],
                 r["propulsion"], r["direction"])][r["port"]] = r
        by_flag[(r["volume"], r["colony"], r["port"], r["year"],
                 r["propulsion"], r["direction"])][r["flag"]] = r
    checked = 0
    for k, d in by_prop.items():
        if {"steam", "sail", "all"} <= set(d):
            for m in MEASURES:
                a, b, t = (d[p]["value"][m] for p in ("steam", "sail", "all"))
                if None in (a, b, t):
                    continue
                checked += 1
                if a + b != t:
                    bad.append(f"{k} {m}: steam {a} + sail {b} != {t}")
    for k, d in by_port.items():
        named = [p for p in d if p != "all ports"]
        if "all ports" in d and len(named) >= 2:
            for m in MEASURES:
                vals = [d[p]["value"][m] for p in named]
                t = d["all ports"]["value"][m]
                if None in vals or t is None:
                    continue
                checked += 1
                if sum(vals) != t:
                    bad.append(f"{k} {m}: ports {sum(vals)} != total {t}")
    for k, d in by_flag.items():
        if {"all", "italian"} <= set(d):
            for m in MEASURES:
                a, t = d["italian"]["value"][m], d["all"]["value"][m]
                if None not in (a, t) and a > t:
                    bad.append(f"{k} {m}: Italian {a} > all flags {t}")
    for r in rows:
        if any(v is not None and v < 0 for v in r["value"].values()):
            bad.append(f"{r['volume']} {r['port']} {r['year']}: negative")
    return checked


def reconcile(rows, bad):
    """One figure per line and measure: the latest printing, with the earlier
    ones kept and marked."""
    printings = defaultdict(list)
    for r in rows:
        for m in MEASURES:
            if r["value"][m] is not None:
                printings[tuple(r[k] for k in KEY) + (m,)].append(r)
    series, long_rows, revised = {}, [], set()
    for key, rs in printings.items():
        rs = sorted(rs, key=lambda r: (order(r["volume"]), int(r["pdf_page"])))
        m = key[-1]
        latest = rs[-1]["value"][m]
        values = {r["value"][m] for r in rs}
        if len(values) > 1:
            ref = key[:3]
            reviser = REVISIONS.get(ref)
            first_new = next(r["volume"] for r in rs if r["value"][m] == latest)
            if reviser is None:
                bad.append(f"{key}: printings differ with no revision on "
                           f"record: {[(r['volume'], r['value'][m]) for r in rs]}")
            elif first_new != reviser or any(
                    r["value"][m] != latest for r in rs
                    if order(r["volume"]) >= order(reviser)):
                bad.append(f"{key}: revision expected from the {reviser} "
                           f"volume, printings "
                           f"{[(r['volume'], r['value'][m]) for r in rs]}")
            revised.add(key[:-1])
        for r in rs:
            status = ("published" if r["value"][m] == latest
                      else f"superseded by the {rs[-1]['volume']} volume")
            long_rows.append(dict(
                {k: r[k] for k in KEY}, measure=m, value=r["value"][m],
                printed=r["printed"][m], volume=r["volume"],
                pdf_page=r["pdf_page"], status=status,
                note=r["notes"].get(m, "")))
        s = series.setdefault(key[:-1], {"printings": set(), "notes": []})
        s[m] = latest
        s["printings"].update(r["volume"] for r in rs)
        note = rs[-1]["notes"].get(m)
        if note:
            s["notes"].append(f"{m}: {note}")
    missing = set(REVISIONS) - {k[:3] for k in revised}
    if missing:
        bad.append(f"revisions on record but not found: {sorted(missing)}")
    return series, long_rows, revised


def write(name, rows, fields):
    with (OUT / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {name}: {len(rows):,} rows")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    rows = read()
    bad = []
    checked = audit(rows, bad)
    series, long_rows, revised = reconcile(rows, bad)
    if bad:
        print(f"{len(bad)} checks failed:")
        for b in bad[:40]:
            print(f"  {b}")
        sys.exit(1)

    out = []
    for key in sorted(series, key=lambda k: (k[0], k[2], k[1] == "all ports",
                                             k[1], k[3], k[5], k[4])):
        s = series[key]
        vols = sorted(s["printings"], key=order)
        out.append(dict(
            zip(KEY, key), **{m: s.get(m, "") for m in MEASURES},
            printings=len(vols), volumes=" ".join(vols),
            agreement=("revised" if key in revised else
                       "single printing" if len(vols) == 1 else "agree"),
            note="; ".join(s["notes"])))
    write("libya_annuario_shipping.csv", out,
          list(KEY) + list(MEASURES) + ["printings", "volumes", "agreement",
                                        "note"])
    write("libya_annuario_shipping_printings.csv", long_rows,
          list(KEY) + ["measure", "value", "printed", "volume", "pdf_page",
                       "status", "note"])

    trip = {r["year"]: r for r in out if r["port"] == "Tripoli"
            and r["flag"] == "all" and r["propulsion"] == "all"
            and r["direction"] == "arrived"}
    multi = sum(1 for r in out if r["printings"] > 1)
    print()
    print(f"  Tripoli, net tonnage of ships arriving: "
          f"{int(trip['1923']['net_tonnage']):,} in 1923, "
          f"{int(trip['1937']['net_tonnage']):,} in 1937")
    print(f"  {len(rows):,} printings in {len({r['volume'] for r in rows})} "
          f"volumes; {multi} of {len(out)} lines printed more than once; "
          f"{len(revised)} revised by a later volume")
    print(f"\n  [ok ] every printed identity holds: {checked} sums")
    print(f"  [ok ] every repeated printing agrees, or is a revision the "
          f"revising volume announces ({len(REVISIONS)} on record)")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
