#!/usr/bin/env python3
"""
Read the Libyan tables of the 1921 Italian census of the colonies.

Source: Istituto Centrale di Statistica del Regno d'Italia, `Censimento della
popolazione delle colonie italiane al 1° dicembre 1921 e rilevazione degli
abitanti del possedimento delle Isole Egee al 20 agosto 1922`, Rome 1931. The
figures published here are the summary of inhabited centres that opens each
colony's chapter: `La Tripolitania comprendeva, al 1° dicembre 1921, data del
VI Censimento generale della popolazione italiana, i seguenti Centri e Località
abitate` (PDF page 20) and the same sentence for Cirenaica (PDF page 62).

## What this census counted, which is not what 1931 and 1936 counted

**The 1921 census is the VI general census of the Italian population, extended
to the colonies.** It counted the people the colonial state governed directly in
the inhabited centres: 18,566 present in Tripolitania and 8,607 in Cirenaica. In
1931 the same colonies return 543,672 and 160,451, because by then the census
enumerated the indigenous population as well, and because Italy held far more
ground.

So these figures are the settler and foreign population of the coastal centres,
and **putting them in a series with 1931 or 1936 would measure the growth of the
Italian census rather than the growth of Libya**. They are worth having as what
they are: the earliest locality-level count Italy made, ten years into the
occupation, and a picture of where in Libya the colonial state actually sat.

## Why the summary and not table I

Each chapter also carries a table I, `Popolazione presente, temporaneamente
assente e residente nei Centri e Località abitate`, with nine columns instead of
three: the present population split into habitual and occasional, and the
temporarily absent split by where they were. Table I is the fuller table and it
is the one worth having, but the scan of its Cirenaica page is damaged in a way
that cannot be repaired from the page: it splits capitals off their words
(`E l Merg`, `R égima`), wraps `Marsa Susa (Apollo-` over two lines, and leaves
some centres' figures on the line below the name, so three of the fourteen
centres cannot be attributed without guessing. Its Tripolitania page reads
exactly.

Publishing one colony from one table and the other from another would put two
different readings in one file. The summary prints the same centres with three
of the same columns in a layout neither scan damaged, and it reconciles to the
printed totals for both colonies to the unit, so both colonies are read from it.
Table I's six further columns remain unread and are noted in
`sources/italy_README.md` as the obvious thing to recover from a better scan.

## The columns

  famiglie        families and convivenze
  present_total   population present at the census
  resident        resident population

`row_kind` is `centre` for an inhabited centre, `section` for the two
`di cui nella Sezione Mare` lines that Tripoli and Zuara are partly made of,
and `total` for the colony line. Only `centre` rows sum to the colony.

## Reading it

Figures are set flush right, so a column is a cluster of right edges and each
number is assigned to the column it sits under. The volume separates thousands
with a **space**, so `16 010` is one figure and not two, and it sets 1 as `l` or
`I` and 0 as `O` often enough to lose whole rows, so a token that could only be
a figure has those letters swapped back before it is read.

The centres are printed in alphabetical order and the list is closed, so where
the count of figure-carrying lines equals the count of centres, each line takes
the centre at its own position and the printed label is used to **check** that
assignment rather than to make it. This is what recovers `Tòcra`, which the scan
leaves as `T6cx~`. Every row records the agreement between its position and its
printed label, and any disagreement is named in the report.

The tables print their own totals, 3,090 families and 18,566 present for
Tripolitania and 1,592 and 8,607 for Cirenaica, and the extraction is measured
against them.

Outputs, under data/processed/istat/:
  libya_1921_localities.csv   one row per centre, section and colony total
"""

import argparse
import csv
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1936_localities import (  # noqa: E402
    SEATS, SEAT_SHABIYA, SPECIFIC, latin_fold, lines_of)
from extract_istat_1936_population import columns_of  # noqa: E402
from extract_opensanctions_libya import ARABIC_ALIASES  # noqa: E402
from libya_places import gazetteer, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
PDF = RAW / ("Censimenti_popolazione_censpop1921_UBO0296438_Popolazione_"
             "colonie_italiane_e_rilevazione_abitanti_isole_egee_"
             "OCR_ottimizzato.pdf")
SOURCE = ("https://ebiblio.istat.it/digibib/Censimenti%20popolazione/censpop1921/"
          "UBO0296438_Popolazione_colonie_italiane_e_rilevazione_abitanti_"
          "isole_egee+OCR_ottimizzato.pdf")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# The introduction summary of each colony, zero-indexed, with the y bounds of
# the table itself. The bounds matter: the Tripolitania page carries a second
# table of families and convivenze below this one.
PAGES = {20: ("Tripolitania", 255, 460), 62: ("Cirenaica", 110, 440)}
BAND = 4

COLUMNS = ("famiglie", "present_total", "resident")

PUBLISHED = {
    "Tripolitania": {"famiglie": 3090, "present_total": 18566, "resident": 19332},
    "Cirenaica": {"famiglie": 1592, "present_total": 8607, "resident": 9318},
}

# The centres of 1921, in the alphabetical order the tables print them, so a
# scan-damaged label can be checked against a closed list. Cirenaica has
# fourteen and not fifteen: Benina appears in neither table, and the fourteen
# sum to the printed total exactly.
CENTRES = {
    "Tripolitania": ("tripoli", "azizia", "homs", "sorman", "sugh el giumaa",
                     "tagiura", "zanzur", "zauia", "zuara"),
    "Cirenaica": ("bengasi", "cirene", "derna", "driana", "el merg", "ghemines",
                  "marsa susa", "regima", "soluch", "tilimun", "tobruch",
                  "tocra", "tolmeta", "zavia hania"),
}

# The Arabic name each centre transliterates. The shabiya is never asserted
# from this table: the name is looked up in the repository's own concordance.
CENTRE_AR = {
    "tripoli": "طرابلس", "azizia": "العزيزية", "homs": "الخمس",
    "sorman": "صرمان", "sugh el giumaa": "سوق الجمعة", "tagiura": "تاجوراء",
    "zanzur": "جنزور", "zauia": "الزاوية", "zuara": "زوارة",
    "bengasi": "بنغازي", "cirene": "شحات", "derna": "درنة",
    "driana": "دريانة", "el merg": "المرج", "ghemines": "قمينس",
    "marsa susa": "سوسة", "regima": "الرجمة", "soluch": "سلوق",
    "tilimun": "تلمين", "tobruch": "طبرق", "tocra": "توكرة",
    "tolmeta": "طلميثة", "zavia hania": "زاوية الحنية",
}

# Cirenaica's Zàvia Hània is not in the concordance under that name. `الحنية`,
# a mahalla of Jabal al Akhdar, is the same place read without its `zàvia`, and
# using it is a reading of mine rather than a match, so the row says `asserted`
# and a user who will not take an assertion can drop it.
ASSERTED = {"زاوية الحنية": "الحنية"}

# The colony a shabiya falls in, from the pcode prefix the CODAB layer itself
# uses: LY01 is the east, LY02 the north-west, LY03 the Fezzan. This is the one
# check that catches a name resolving to the wrong Libya. Without it Zanzur,
# beside Tripoli, lands on a mahalla of Tobruk that shares its name.
REGION = {"Tripolitania": ("LY02", "LY03"), "Cirenaica": ("LY01",)}

# Centres whose concordance match sat in the other colony, collected for the
# report so a silent correction never happens.
CONTRADICTED = []

AGREES = 0.55


def as_int(text):
    """A figure, in a volume that separates thousands with a space.

    `16 010` is one number here and not two, and `2 813` likewise. A string that
    mixes the two separators, as the scan's `2 0.39` does, is refused.
    """
    # The scan leaves rules and specks against a figure: ": 16 010", "!16 558".
    cleaned = re.sub(r"^[^\w]+|[^\w]+$", "", text.strip().replace("'", ""))
    # This scan sets 1 as l or I and 0 as O often enough to lose whole rows:
    # Bengasi's 1 110 families arrives as `1 IlO`. The swap is made only where
    # nothing but a figure could stand, and the printed totals say whether it
    # was right.
    if re.fullmatch(r"[lIO\d][lIO\d. ]*", cleaned):
        cleaned = cleaned.translate(str.maketrans("lIO", "110"))
    for pattern, separator in ((r"\d{1,3}(?: \d{3})+", " "),
                               (r"\d{1,3}(?:\.\d{3})+", "."),
                               (r"\d{1,6}", "")):
        if re.fullmatch(pattern, cleaned):
            return int(cleaned.replace(separator, "") if separator else cleaned)
    return None


def fetch_pdf():
    if PDF.exists():
        return
    RAW.mkdir(parents=True, exist_ok=True)
    print("fetching the 1921 volume (9 MB)")
    request = urllib.request.Request(SOURCE, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=600) as response:
        PDF.write_bytes(response.read())


def bands_of(page, bottom, top):
    """The printed lines of the table, grouped into the rows they were set in.

    A row is a run of lines no more than BAND apart, not a rounding of y to a
    grid: rounding cuts a printed row in two whenever it straddles a boundary,
    and on the Cirenaica page a centre's name and its figures are routinely set
    four points apart.
    """
    lines = [ln for ln in lines_of(page) if bottom < ln["y"] < top]
    lines.sort(key=lambda ln: -ln["y"])
    bands, current, edge = [], [], None
    for line in lines:
        if edge is None or edge - line["y"] <= BAND:
            current.append(line)
            edge = line["y"] if edge is None else edge
        else:
            bands.append(current)
            current, edge = [line], line["y"]
    if current:
        bands.append(current)
    return bands


def name_of(label):
    """The letters of a printed label, with the table's furniture removed."""
    flat = re.sub(r"[^a-z ]", " ", latin_fold(label))
    return re.sub(r"\s+", " ", flat).strip()


def similarity(name, other):
    from difflib import SequenceMatcher
    if not other:
        return 0.0
    return max(SequenceMatcher(None, name, other).ratio(),
               SequenceMatcher(None, name.replace(" ", ""),
                               other.replace(" ", "")).ratio())


def pieces(label):
    """The label cut where the table's leader dots cut it."""
    parts = [name_of(piece) for piece in re.split(r"[.·•]{2,}|\s{3,}", label)]
    return [part for part in parts if part] or [""]


def best_match(label, names):
    scored = [(max(similarity(name, piece) for piece in pieces(label)), name)
              for name in names]
    return max(scored)


def rows_of(bands, colony):
    """One row per line of the table that carries figures.

    The figures decide which lines are rows: a line with none is a wrapped label
    or a speck the scan left behind. Each figure is assigned to the column whose
    right edge it sits on, because the table is set flush right.
    """
    numbers = [cell for band in bands for cell in band
               if as_int(cell["text"]) is not None]
    edges = columns_of([dict(cell, value=as_int(cell["text"]))
                        for cell in numbers], wanted=len(COLUMNS), minimum=3)
    if len(edges) != len(COLUMNS):
        print(f"   {colony}: found {len(edges)} columns, expected "
              f"{len(COLUMNS)}; not read")
        return []
    label_edge = min(edges) - 25

    entries = []
    for band in bands:
        figures = {}
        for cell in band:
            value = as_int(cell["text"])
            if value is None:
                continue
            near = min(range(len(edges)), key=lambda i: abs(edges[i] - cell["x1"]))
            if abs(edges[near] - cell["x1"]) <= 12:
                figures[COLUMNS[near]] = value
        if not figures:
            continue
        label = " ".join(cell["text"] for cell in sorted(band, key=lambda c: c["x"])
                         if as_int(cell["text"]) is None and cell["x"] < label_edge)
        entries.append({"label_printed": " ".join(label.split()),
                        "figures": figures})

    # The `di cui nella Sezione Mare` lines are parts of the centre above them,
    # not centres, and the colony line closes the table.
    for entry in entries:
        name = name_of(entry["label_printed"])
        if re.search(r"\bmare\b", name):
            entry["row_kind"] = "section"
        elif similarity("totale", name) > 0.7 or name.startswith("totale"):
            entry["row_kind"] = "total"
        else:
            entry["row_kind"] = "centre"

    rows = []
    parent = ""
    centres = [e for e in entries if e["row_kind"] == "centre"]
    order = CENTRES[colony]
    positional = len(centres) == len(order)
    if not positional:
        print(f"   {colony}: {len(centres)} lines carry figures against "
              f"{len(order)} centres; falling back to name matching")
    index = 0
    for entry in entries:
        row = dict(entry["figures"], colony=colony,
                   row_kind=entry["row_kind"],
                   label_printed=entry["label_printed"])
        if entry["row_kind"] == "centre":
            if positional:
                name = order[index]
                score = max(similarity(name, name_of(entry["label_printed"])),
                            best_match(entry["label_printed"], [name])[0])
            else:
                score, name = best_match(entry["label_printed"], order)
                if score < AGREES:
                    name = ""
            index += 1
            row["centre"] = name
            row["match_score"] = round(score, 2)
            row["label_agrees"] = "yes" if score >= AGREES else "no"
            parent = name
        elif entry["row_kind"] == "section":
            row["centre"] = parent
            row["match_score"] = ""
            row["label_agrees"] = ""
        else:
            row["centre"] = "totale"
            row["match_score"] = ""
            row["label_agrees"] = ""
        rows.append(row)
    return rows


def place_of(centre, colony, places, shabiya_keys, scrambled):
    """The shabiya of a 1921 centre, from the repository's own concordance.

    A match is kept only if it lands in the colony the table puts the centre in,
    which is what stops a name shared by a settlement at the other end of the
    country from being taken for this one.
    """
    arabic = CENTRE_AR.get(centre) or dict(SEATS).get(centre, "")
    if not arabic:
        return "", None, "unplaced"
    attempts = [(SPECIFIC.get(arabic, arabic), "concordance")]
    if arabic in ARABIC_ALIASES:
        attempts.append((ARABIC_ALIASES[arabic], "asserted"))
    if arabic in ASSERTED:
        attempts.append((ASSERTED[arabic], "asserted"))
    if centre in SEAT_SHABIYA:
        attempts.append((SEAT_SHABIYA[centre], "asserted"))
    for spelling, route in attempts:
        found = resolve(spelling, places, shabiya_keys, scrambled)
        if not found:
            continue
        if not found[2].startswith(REGION[colony]):
            CONTRADICTED.append(f"{centre} ({spelling}) -> {found[1]}")
            continue
        if route == "asserted":
            found = found[:3] + ("asserted",)
        return arabic, found, route
    return arabic, None, "unplaced"


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    fetch_pdf()
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams

    places, shabiya_keys, scrambled = gazetteer()
    rows = []
    for number, (colony, bottom, top) in PAGES.items():
        page = next(extract_pages(PDF, page_numbers=[number],
                                  laparams=LAParams(line_margin=0.25,
                                                    char_margin=1.5)))
        for row in rows_of(bands_of(page, bottom, top), colony):
            arabic = found = None
            route = "not a centre"
            if row["row_kind"] == "centre" and row["centre"]:
                arabic, found, route = place_of(row["centre"], row["colony"],
                                                places, shabiya_keys, scrambled)
            row["centre_ar"] = arabic or ""
            row["shabiya_ar"] = found[0] if found else ""
            row["shabiya_en"] = found[1] if found else ""
            row["shabiya_pcode"] = found[2] if found else ""
            row["shabiya_route"] = route
            rows.append(row)

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "libya_1921_localities.csv", rows)
    report(rows)


def write(path, rows):
    if not rows:
        print(f"{path.name:32s} no rows")
        return
    fields = (["colony", "centre", "row_kind", "centre_ar", "shabiya_ar",
               "shabiya_en", "shabiya_pcode", "shabiya_route"] + list(COLUMNS)
              + ["match_score", "label_agrees", "label_printed"])
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore",
                                restval="")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:32s} {len(rows):5d} rows")


def report(rows):
    print()
    for colony, targets in PUBLISHED.items():
        here = [r for r in rows if r["colony"] == colony]
        centres = [r for r in here if r["row_kind"] == "centre"]
        sections = [r for r in here if r["row_kind"] == "section"]
        print(f"{colony}: {len(centres)} centres, {len(sections)} sections, "
              f"{sum(1 for r in here if r['row_kind'] == 'total')} colony total")
        for field, target in targets.items():
            total = sum(r[field] for r in centres if r.get(field, "") != "")
            gaps = [r["centre"] or r["label_printed"]
                    for r in centres if r.get(field, "") == ""]
            printed = [r[field] for r in here
                       if r["row_kind"] == "total" and r.get(field, "") != ""]
            mark = "ok " if total == target else "OFF"
            note = ("exactly as printed" if total == target
                    else f"off by {total - target:+,}, "
                         f"{len(gaps)} rows have no figure: "
                         f"{', '.join(gaps) or 'none'}")
            same = (" and the table's own total line reads the same"
                    if printed and printed[0] == target else "")
            print(f"   [{mark}] {field:16s} {total:>8,} against {target:>8,}, "
                  f"{note}{same}")
        disagree = [r["label_printed"] for r in centres
                    if r["label_agrees"] == "no"]
        if disagree:
            print(f"   labels the scan damaged past recognition, placed by "
                  f"their position in the alphabetical list: {disagree}")
    placed = [r for r in rows if r["shabiya_en"]]
    print(f"\n{len(placed)} rows carry a shabiya "
          f"{dict(Counter(r['shabiya_route'] for r in rows))}")
    print("  by shabiya:", dict(Counter(r["shabiya_en"] for r in placed)))
    unplaced = sorted({r["centre"] for r in rows
                       if r["row_kind"] == "centre" and not r["shabiya_en"]})
    if unplaced:
        print("  centres with no shabiya:", ", ".join(unplaced))
    if CONTRADICTED:
        print("  concordance matches refused for sitting in the other colony:",
              "; ".join(sorted(set(CONTRADICTED))))
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
