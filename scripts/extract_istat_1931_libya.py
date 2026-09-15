#!/usr/bin/env python3
"""
Read the Libyan tables of the 1931 Italian census of the colonies.

Source: Istituto Centrale di Statistica del Regno d'Italia, `VII censimento
generale della popolazione, 21 aprile 1931, Volume V: Colonie e possedimenti`,
Rome 1935, Part II, tables I and II for Tripolitania (printed page 12) and for
Cyrenaica (printed page 24). Downloaded from ISTAT's digital library; the PDF is
fetched here if it is absent.

## What 1931 has that 1936 does not, and the other way round

The 1936 volume lists a thousand localities and counts the Libyan population in
each. The 1931 volume does not go below the circumscription, and in exchange it
does something 1936 does not: it counts **all four populations side by side** —
the colony's total, the Italians from the Kingdom (`regnicola`), other
foreigners (`straniera`) and the indigenous population — with the area in square
kilometres and the density. Two tables:

  TAVOLA I   area, the four populations, density, by Commissariato Regionale
             and Comando di Zona
  TAVOLA II  the same four populations by sex, and one level deeper, to the
             Circondario and the Distretto

Libya is two colonies here, not one: Tripolitania and Cyrenaica are counted
separately and the volume never adds them together. It gives 543,672 present in
Tripolitania and 160,451 in Cyrenaica, of whom 512,771 and 141,945 are
indigenous.

## Table II is not here, and that is a finding about the scan

**Only table I is published.** Table II carries the district detail, which is
the more valuable half, and it cannot be read from this scan: the OCR runs the
label and the first two figures together into one string, so a line arrives as
`C. R. DI TRIPOLI (2). 81.98638.444 21.47`. The wide figures can be split back
apart by their thousands separators, but they then have no column position, and
assigning them in order is exactly what fails when the scan has dropped one.
Publishing a district table keyed by guesswork would be worse than publishing
none, so the district figures of 1931 are recorded as unavailable. The 1936
volume's locality list, which this repository does publish, is the way to get
below the circumscription for the colonial period.

## Reading the page

Figures are set flush right, so a column is a cluster of right edges, and each
number is assigned to the column it sits under rather than to its place in the
line. Both tables sit on one page and are split at the baseline of the `TAVOLA
II` heading.

The Tripolitanian page is **tilted**: a printed row's label sits seven points
above its own last figure, which is exactly where the next label sits, so
grouping by baseline hands every row's figures to the label below it and the
colony's total comes out 11% short. The tilt is measured by trying a range of
slopes and keeping the one that puts the most labels in a band with figures, and
a page that is not tilted is left alone.

`level` is read from the label's own prefix, which is how the table marks its
hierarchy: `C. R.` a Commissariato Regionale, `C. Z.` a Comando di Zona,
`TOTALE` the colony. **Adding levels together double-counts**, which is why the
level is on every row.

## What is checked

The tables print their own totals. For Cyrenaica every column comes out exactly
as printed. For Tripolitania the Italian and the indigenous columns come out
exactly, and three columns are short by precisely the cells the scan destroyed:
Misurata's area, Zavia's total population, and four small counts of foreigners.
The report names them, and `validate.py` fails if a sum ever exceeds its printed
total or misses it with no damaged cell to account for the gap.

Circumscriptions are placed in a modern shabiya the same way the 1936 gazetteer
places them: each seat is given the Arabic name it transliterates and that name
is resolved through this repository's concordance.

Outputs, under data/processed/istat/:
  libya_1931_circoscrizioni.csv   table I, one row per circumscription
"""

import argparse
import csv
import re
import sys
import urllib.request
from collections import Counter
from difflib import get_close_matches
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1936_localities import (  # noqa: E402
    latin_fold, lines_of)
from extract_istat_1936_population import as_int, columns_of  # noqa: E402
from extract_opensanctions_libya import ARABIC_ALIASES  # noqa: E402
from libya_places import gazetteer, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
PDF = RAW / ("Censimenti_popolazione_censpop1931_IST0005835Volume_V_"
             "Colonie_e_possedimenti_OCRottimizz.pdf")
SOURCE = ("https://ebiblio.istat.it/digibib/Censimenti%20popolazione/censpop1931/"
          "IST0005835Volume_V_Colonie_e_possedimenti+OCRottimizz.pdf")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# The two pages that carry Libya, zero-indexed, with the colony each is for.
PAGES = {76: "Tripolitania", 88: "Cirenaica"}
BAND = 4

TABLE_ONE = ("superficie_km2", "present_total", "present_italian",
             "present_foreign", "present_indigenous", "density_km2")
TABLE_TWO = ("total_mf", "total_f", "italian_mf", "italian_f",
             "foreign_mf", "foreign_f", "indigenous_mf", "indigenous_f")

# The totals the tables print for themselves, which is what the extraction is
# measured against.
PUBLISHED = {
    "Tripolitania": {"superficie_km2": 912532, "present_total": 543672,
                     "present_italian": 28496, "present_foreign": 2405,
                     "present_indigenous": 512771},
    "Cirenaica": {"superficie_km2": 861420, "present_total": 160451,
                  "present_italian": 16104, "present_foreign": 2402,
                  "present_indigenous": 141945},
}

LEVELS = ((r"^c\W*r\b", "commissariato_regionale"),
          (r"^c\W*z\b", "comando_di_zona"),
          (r"^circ", "circondario"),
          (r"^dist", "distretto"),
          (r"^di\s*cui", "municipio"),
          (r"^totale", "total"))

# The circumscriptions of 1931, by colony, because the name alone is ambiguous:
# the Gebel of Tripolitania is the Nefusa mountain in the west and the Gebel of
# Cyrenaica is the green mountain in the east.
#
# Most of them are regions rather than towns, and most cover more than one
# modern shabiya: the Commissariato della Gefara reaches from Tripoli through
# Jafara into Murqub, and the four southern Comandi di Zona cover the whole
# Fezzan. Those are marked `spans_several_shabiyat` rather than given a province
# they only partly occupy. Only where a 1931 circumscription and a modern
# shabiya are the same ground does it get an Arabic name to resolve.
REGIONS = {
    ("Tripolitania", "tripoli"): "طرابلس",
    ("Tripolitania", "confine occidentale"): "",
    ("Tripolitania", "zavia"): "الزاوية",
    ("Tripolitania", "gefara"): "",
    ("Tripolitania", "leptis"): "المرقب",
    ("Tripolitania", "misurata"): "مصراته",
    ("Tripolitania", "gebel"): "",
    ("Tripolitania", "sud orientale"): "",
    ("Tripolitania", "sud occidentale"): "",
    ("Tripolitania", "fezzan"): "",
    ("Tripolitania", "totale"): "",
    ("Cirenaica", "bengasi"): "",
    ("Cirenaica", "municipio di bengasi"): "بنغازي",
    ("Cirenaica", "gebel"): "",
    ("Cirenaica", "marmarica"): "البطنان",
    ("Cirenaica", "agedabia"): "",
    ("Cirenaica", "totale"): "",
}


def fetch_pdf():
    if PDF.exists():
        return
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"fetching {SOURCE.rsplit('/', 1)[-1]} (17 MB)")
    request = urllib.request.Request(SOURCE, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=600) as response:
        PDF.write_bytes(response.read())


def skew_of(lines):
    """How far the scan tilts, in points of drop per point of width.

    On the Tripolitanian page a printed row's label sits seven points above its
    own last figure, which is exactly where the next label sits. Banding by
    baseline then hands every row's figures to the label below it, and the
    colony's total comes out 11% short. The tilt is found by trying a range of
    slopes and keeping the one that puts the most labels in a band with figures.
    """
    def rows_at(slope):
        bands = {}
        for line in lines:
            bands.setdefault(round((line["y"] + slope * line["x"]) / BAND),
                             []).append(line)
        return sum(1 for cells in bands.values()
                   if any(as_int(c["text"]) is None and c["x"] < 250
                          for c in cells)
                   and sum(1 for c in cells if as_int(c["text"]) is not None) >= 3)

    flat = rows_at(0)
    best = max((i / 1000 for i in range(1, 31)), key=rows_at)
    # A page that is not tilted must not be tilted by the search, so a slope is
    # only taken when it finds a fifth more rows than no slope at all.
    return best if rows_at(best) >= flat * 1.2 else 0.0


def bands_of(page):
    lines = lines_of(page)
    slope = skew_of([ln for ln in lines if ln["y"] < 800])
    for line in lines:
        line["y"] = line["y"] + slope * line["x"]
    lines = sorted(lines, key=lambda ln: -ln["y"])
    bands, current, top = [], [], None
    for line in lines:
        if top is None or top - line["y"] <= BAND:
            current.append(line)
            top = line["y"] if top is None else top
        else:
            bands.append((top, current))
            current, top = [line], line["y"]
    if current:
        bands.append((top, current))
    return bands


def level_of(label):
    flat = latin_fold(label).strip()
    for pattern, name in LEVELS:
        if re.search(pattern, flat):
            return name
    return ""


def seat_of(label):
    """The place name, with the level prefix and the table's noise removed."""
    flat = latin_fold(label)
    flat = re.sub(r"^\s*(c\W*[rz]\b|circ\w*|dist\w*|di cui nel municipio di|"
                  r"municipio di)\W*", " ", flat)
    flat = re.sub(r"\bdi\b|\bdel\b|\bdella\b|\bdei\b|\bdi cui\b", " ", flat)
    flat = re.sub(r"\(\d\)|\d", " ", flat)
    return re.sub(r"\s+", " ", flat).strip(" .,'")


def canonical(colony, seat):
    """The circumscription this scan-damaged label is, out of a closed list."""
    names = [name for (where, name) in REGIONS if where == colony]
    close = get_close_matches(seat, names, n=1, cutoff=0.6)
    return close[0] if close else ""


def place_of(colony, seat, places, shabiya_keys, scrambled, level=""):
    """The shabiya of a 1931 circumscription, where it is one shabiya."""
    if level == "total":
        return "totale", "", None, "colony_total"
    if level == "municipio":
        seat = f"municipio di {seat}"
    name = canonical(colony, seat)
    if not name:
        return "", "", None, "unread"
    arabic = REGIONS[(colony, name)]
    if not arabic:
        return name, "", None, "spans_several_shabiyat"
    found = resolve(arabic, places, shabiya_keys, scrambled)
    if found:
        return name, arabic, found, "concordance"
    if arabic in ARABIC_ALIASES:
        found = resolve(ARABIC_ALIASES[arabic], places, shabiya_keys, scrambled)
        if found:
            return name, arabic, found[:3] + ("asserted",), "asserted"
    return name, arabic, None, "unplaced"


def read_page(number):
    """(table I rows, table II rows) of one page, as label and figures."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams

    page = next(extract_pages(PDF, page_numbers=[number],
                              laparams=LAParams(line_margin=0.25,
                                                char_margin=1.5)))
    bands = bands_of(page)
    split = next((y for y, cells in bands
                  if any(re.search(r"(?i)tav[oa]la\s+ii", c["text"])
                         for c in cells)), 0)
    tables = {"one": [], "two": []}
    for y, cells in bands:
        if y > 800:
            continue
        which = "one" if y > split else "two"
        tables[which].append((y, cells))
    return tables


def rows_of(bands, columns, blocks=1):
    """One row per band, with its figures placed in the table's columns.

    Table II is set in two blocks side by side, so its columns are found across
    the page and cut in half; each half is then read as its own table.
    """
    cells = [cell for _, group in bands for cell in group]
    numbers = [dict(cell, value=as_int(cell["text"]))
               for cell in cells if as_int(cell["text"]) is not None]
    if blocks > 1:
        edges = columns_of(numbers, wanted=blocks * len(columns))
        if len(edges) < len(columns) + 1:
            return rows_of(bands, columns)
        split = edges[len(columns) - 1] + 20
        left = [(y, [c for c in group if c["x1"] < split]) for y, group in bands]
        right = [(y, [c for c in group if c["x1"] >= split]) for y, group in bands]
        return rows_of(left, columns) + rows_of(right, columns)

    edges = columns_of(numbers, wanted=len(columns))
    if len(edges) < 2:
        return []
    label_edge = min(edges) - 25

    rows = []
    for _, group in bands:
        label = " ".join(c["text"] for c in sorted(group, key=lambda c: c["x"])
                         if as_int(c["text"]) is None and c["x"] < label_edge)
        figures = [c for c in group if as_int(c["text"]) is not None]
        if not figures or not re.search(r"[A-Za-z]{3}", label):
            continue
        row = {"label_printed": " ".join(label.split())}
        for name in columns:
            row[name] = ""
        for cell in figures:
            near = min(range(len(edges)), key=lambda i: abs(edges[i] - cell["x1"]))
            if abs(edges[near] - cell["x1"]) <= 12 and near < len(columns):
                row[columns[near]] = as_int(cell["text"])
        rows.append(row)
    return rows


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    fetch_pdf()
    places, shabiya_keys, scrambled = gazetteer()

    first = []
    for number, colony in PAGES.items():
        tables = read_page(number)
        for row in rows_of(tables["one"], TABLE_ONE):
            row["colony"] = colony
            first.append(row)

    for row in first:
        row["level"] = level_of(row["label_printed"])
        row["seat_printed"] = seat_of(row["label_printed"])
        name, arabic, found, route = place_of(
            row["colony"], row["seat_printed"], places, shabiya_keys, scrambled,
            row["level"])
        row["seat"] = name or row["seat_printed"]
        row["seat_ar"] = arabic
        row["shabiya_ar"] = found[0] if found else ""
        row["shabiya_en"] = found[1] if found else ""
        row["shabiya_pcode"] = found[2] if found else ""
        row["shabiya_route"] = route

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "libya_1931_circoscrizioni.csv", first,
          ["colony", "seat", "level", "seat_ar", "shabiya_ar", "shabiya_en",
           "shabiya_pcode", "shabiya_route"] + list(TABLE_ONE)
          + ["seat_printed", "label_printed"])
    report(first)


def write(path, rows, fields):
    if not rows:
        print(f"{path.name:34s} no rows")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:34s} {len(rows):5d} rows")


def report(first):
    print()
    for colony, published in PUBLISHED.items():
        rows = [r for r in first if r["colony"] == colony
                and r["level"] in ("commissariato_regionale", "comando_di_zona")]
        print(f"{colony}: {len(rows)} circumscriptions in table I")
        for field, target in published.items():
            total = sum(r[field] for r in rows if r[field] != "")
            missing = [r["seat"] for r in rows if r[field] == ""]
            if not missing:
                mark = "ok " if total == target else "OFF"
                note = "exactly as printed" if total == target else "NOT the total"
            else:
                mark = "ok " if total < target else "OFF"
                note = (f"short by {target - total:,}, the scan destroyed "
                        f"{len(missing)}: {', '.join(missing)}")
            print(f"   [{mark}] {field:20s} {total:>10,} against {target:>10,}, "
                  f"{note}")
    print()
    placed = [r for r in first if r["shabiya_en"]]
    print(f"{len(placed)} of {len(first)} rows carry a shabiya "
          f"{dict(Counter(r['shabiya_route'] for r in first))}")
    print("table II, the district detail, is not published: the scan runs its "
          "labels and figures together")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
