#!/usr/bin/env python3
"""
Read table XX of the 1936 Italian census: the Libyan population by locality.

Source: Istituto Centrale di Statistica del Regno d'Italia, `VIII censimento
generale della popolazione, 21 aprile 1936, Volume V: Libia`, Rome 1939, Part
II, Section III (`Popolazione libica`), table XX, printed pages 57 to 79:
`Popolazione presente e temporaneamente assente secondo il tipo della dimora ed
il sesso. Famiglie e convivenze: nelle circoscrizioni politico-amministrative
per località ed aggregati etnici`.

Appendix II of the same volume, read by
`scripts/extract_istat_1936_localities.py`, is the index to this table: every
locality it lists carries the page of table XX where its population is printed.
This reads the numbers.

## What a row holds

Four counts, and the classification the colonial state cared most about:

  famiglie        families and convivenze
  present_mf      population present, both sexes
  present_f       of which women
  absent_mf       population temporarily absent, both sexes
  dwelling        `st.` stabile, `sn.` semi-nomade, `n.` nomade

The dwelling type is the census's own three-way split of the Libyan population
into settled, semi-nomadic and nomadic, recorded per locality.

## Reading a page of it

Twenty-three scanned pages, two blocks to a page, and a column layout that
shifts from page to page. The columns are found per page: the x positions of the
numeric cells fall into four clusters a block, and each number is assigned to the
cluster it sits in rather than to its position in the line. That matters because
a number the scan destroys leaves a hole, and reading the numbers in order would
then shift every later column on that row by one.

Labels wrap over two and three lines (`Bèni Mìslem,` / `Gmàta`), so label-only
bands accumulate onto the next band that carries numbers.

`row_kind` separates what the table stacks together: `locality` is a place,
`quarter` a named quarter or ethnic aggregate under one, `subtotal` a
circumscription or territory line, and `census_1931` the comparison row the
table prints beside each subtotal. **Only `locality` and `quarter` rows are
population; adding a subtotal to them would double-count.**

## What is checked, and what that shows

Three checks decide whether a row is published: women cannot outnumber both
sexes, families cannot outnumber people, and the absent cannot outnumber the
present by more than tenfold. A row that fails is kept with `is_consistent` = 0
so the damage is visible rather than silently dropped.

The volume's own Prospetto 20 on page 21* gives the Libyan present population of
1936 as **750,851**. That is the number to compare the sum of published rows
against, and the report prints both.

Outputs, under data/processed/istat/:
  libya_population_1936.csv   one row per line of table XX
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1936_localities import (  # noqa: E402
    PDF, fetch_pdf, latin_fold, lines_of, skeleton_latin)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "istat"

# Table XX, zero-indexed. The printed page number is the index minus 67.
TABLE = range(124, 147)
PAGE_OFFSET = 67
HEADER_Y = 690
BAND = 4                 # points of drift allowed inside one printed row
# The two blocks are split where the left one's last figure column ends: the
# right block's labels begin immediately after it, and a fixed split at the
# middle of the page pulled them onto the left block's rows.
BLOCK_MARGIN = 8
COLUMN_GAP = 9           # a gap wider than this separates two columns
COLUMNS = ("famiglie", "present_mf", "present_f", "absent_mf")

# The published total this extraction is measured against: Prospetto 20, page
# 21*, `POPOLAZIONE LIBICA PRESENTE E RESIDENTE`, Libia, present, both sexes.
PUBLISHED_TOTAL = 750851

NUMBER = re.compile(r"^[\d][\d.,'· ]*$")
DWELLING = re.compile(r"(?i)\b(st|sn|n|llt|nt)\s*[.,']")
SUBTOTAL = re.compile(r"(?i)\b(circondario|residenza|res[il]denza|distretto|"
                      r"mud[il]{1,2}r[il]{1,2}|provincia|territorio|commissariato|"
                      r"gab[il]la|cab[il]la|ramo|totale)\b")
QUARTER = re.compile(r"(?i)\b(quartieri|israeliti|altri\s*censiti|aggregati)")
# The table prints a 1931 comparison under every 1936 figure, and the scan
# spells its label a dozen ways: Cens., Oens., Oms., Oe'ns, OtmB., and the year
# as 1931, i9à1 or 19a1. Reading those rows as places doubled the population.
CENSUS_1931 = re.compile(r"(?i)[co][a-z'.]{0,6}\s*\.?\s*[i1l]9[a-z0-9àè]{2}\b|"
                         r"\b[i1l]9[a-z0-9àè]{2}\s*[('\u2018]")


def as_int(text):
    """A printed number, or None if the scan mangled it beyond repair."""
    cleaned = re.sub(r"[ '·]", "", text).replace(",", ".")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+|\d{1,4}", cleaned):
        return int(cleaned.replace(".", ""))
    return None


def numbers_and_labels(cells):
    values, labels = [], []
    for cell in cells:
        value = as_int(cell["text"]) if NUMBER.match(cell["text"]) else None
        (values if value is not None else labels).append(
            dict(cell, value=value))
    return values, labels


def columns_of(values, wanted=None, minimum=5):
    """The four column edges of one block, found from the numbers themselves.

    The table sets its figures flush right, so a column is a cluster of right
    edges. Clustering the left edges instead merges every column into one,
    because a four-figure number starts further left than a three-figure one in
    the same column.
    """
    xs = sorted(round(v["x1"]) for v in values)
    if not xs:
        return []
    clusters, current = [], [xs[0]]
    for x in xs[1:]:
        if x - current[-1] > COLUMN_GAP:
            clusters.append(current)
            current = []
        current.append(x)
    clusters.append(current)
    # A column of a short table holds few figures, so the floor is a parameter:
    # on the 1921 tables a column of nineteen rows can be mostly dashes.
    clusters = [c for c in clusters if len(c) >= minimum]
    clusters.sort(key=len, reverse=True)
    return sorted(sum(c) / len(c) for c in clusters[:wanted or len(COLUMNS)])


def kind_of(label, printed):
    """What the table means by this line.

    The comparison row is tested first and on the printed text, because the
    cleaned label loses the punctuation that marks it.
    """
    if CENSUS_1931.search(printed) or CENSUS_1931.search(label):
        return "census_1931"
    # The scan sometimes destroys the year as well as the word, leaving only a
    # short token opening the line: Cens., Oens., Oms., OtmB. A Libyan name in
    # this transliteration does not begin with one.
    first = re.sub(r"[^a-z]", "", latin_fold(label).split(" ")[0] if label else "")
    if 2 <= len(first) <= 5 and first[0] in "co" and set("nmb") & set(first[1:]):
        return "census_1931"
    if SUBTOTAL.search(label[:40]):
        return "subtotal"
    if QUARTER.search(label[:40]):
        return "quarter"
    return "locality"


def read_table():
    """Every line of table XX, as a row of cells with its page and block."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams

    pages = []
    for number in TABLE:
        page = next(extract_pages(PDF, page_numbers=[number],
                                  laparams=LAParams(line_margin=0.2,
                                                    char_margin=1.2)))
        lines = sorted([ln for ln in lines_of(page) if ln["y"] < HEADER_Y],
                       key=lambda ln: -ln["y"])
        # Group by baseline, growing a band while the next line is within BAND
        # points of it. Rounding to a grid instead splits a printed row whenever
        # it straddles a boundary, and the half without the label becomes a
        # phantom row carrying real figures.
        bands, current, top = {}, [], None
        for line in lines:
            if top is None or top - line["y"] <= BAND:
                current.append(line)
                top = line["y"] if top is None else top
            else:
                bands[round(top)] = current
                current, top = [line], line["y"]
        if current:
            bands[round(top)] = current
        pages.append((number, bands))
    return pages


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    fetch_pdf()

    rows = []
    for number, bands in read_table():
        everything = [cell for band in bands.values() for cell in band]
        all_values, _ = numbers_and_labels(everything)
        edges = columns_of(all_values, wanted=2 * len(COLUMNS))
        if len(edges) < len(COLUMNS) + 1:
            print(f"  page {number - PAGE_OFFSET}: {len(edges)} figure columns "
                  f"found, expected {2 * len(COLUMNS)}", file=sys.stderr)
        split = edges[len(COLUMNS) - 1] + BLOCK_MARGIN if len(edges) >= len(
            COLUMNS) else 400
        for block, (low, high) in enumerate(((0, split), (split, 999))):
            values = [v for v in all_values if low <= v["x1"] < high]
            centres = columns_of(values)
            if len(centres) < 2:
                continue
            carried = []
            for y in sorted(bands, reverse=True):
                cells = sorted([c for c in bands[y] if low <= c["x1"] < high],
                               key=lambda c: c["x"])
                if not cells:
                    continue
                numbers, labels = numbers_and_labels(cells)
                printed = " ".join(c["text"] for c in labels)
                if not numbers:
                    # A label that wraps: hold it for the row that carries the
                    # numbers.
                    if printed.strip():
                        carried.append(printed.strip())
                    continue
                label = " ".join(carried + [printed]).strip()
                carried = []
                row = {"pdf_page": number, "printed_page": number - PAGE_OFFSET,
                       "block": block, "label_printed": label}
                for name in COLUMNS:
                    row[name] = ""
                for value in numbers:
                    near = min(range(len(centres)),
                               key=lambda i: abs(centres[i] - value["x1"]))
                    if abs(centres[near] - value["x1"]) <= COLUMN_GAP and \
                            near < len(COLUMNS):
                        row[COLUMNS[near]] = value["value"]
                dwelling = DWELLING.search(label)
                row["dwelling"] = (dwelling.group(1).lower().replace("llt", "st")
                                   .replace("nt", "n") if dwelling else "")
                clean = re.sub(r"\s+", " ", re.sub(r"[.·•]{2,}|[|:;]", " ",
                                                   label)).strip(" .,'•")
                clean = DWELLING.sub(" ", clean)
                clean = re.sub(r"\s+", " ", clean).strip(" .,'")
                row["label"] = clean
                row["row_kind"] = kind_of(latin_fold(clean).strip(), label)
                rows.append(row)

    check(rows)
    join_localities(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "libya_population_1936.csv", rows)
    report(rows)


def join_localities(rows):
    """Tie a row of the table to the locality index, and so to a shabiya.

    Appendix II gives every locality the page of table XX it is printed on, so
    the join is on the sound of the name **within that page**, which is a far
    tighter constraint than the name alone.
    """
    path = OUT / "libya_localities_1936.csv"
    index = defaultdict(dict)
    if path.exists():
        with path.open() as fh:
            for row in csv.DictReader(fh):
                if row["tav_xx_page"] and row["skeleton"]:
                    index[row["tav_xx_page"]].setdefault(row["skeleton"], []).append(row)
    for row in rows:
        row["locality_it"] = row["shabiya_en"] = row["shabiya_pcode"] = ""
        row["circoscrizione_it"] = ""
        if row["row_kind"] not in ("locality", "quarter"):
            continue
        key = skeleton_latin(row["label"])
        page = index.get(str(row["printed_page"]), {})
        found = page.get(key, [])
        if not found and len(key) >= 4:
            # The table writes the name twice, once as the locality and once as
            # the ethnic aggregate, and the scan adds its own debris, so the
            # appendix's name is looked for inside the row's, not against it.
            inside = [candidates for skeleton, candidates in page.items()
                      if len(skeleton) >= 5 and skeleton in key]
            if len(inside) == 1:
                found = inside[0]
        if len(found) == 1:
            row["locality_it"] = found[0]["locality_it"]
            row["shabiya_en"] = found[0]["shabiya_en"]
            row["shabiya_pcode"] = found[0]["shabiya_pcode"]
            row["circoscrizione_it"] = found[0]["circoscrizione_it"]


def check(rows):
    for row in rows:
        present = row["present_mf"] or 0
        women = row["present_f"] or 0
        families = row["famiglie"] or 0
        absent = row["absent_mf"] or 0
        sound = (present and women <= present and families <= present
                 and absent <= present * 10)
        row["is_consistent"] = int(bool(sound))


def write(path, rows):
    if not rows:
        print(f"{path.name:32s} no rows")
        return
    fields = ["pdf_page", "printed_page", "block", "label", "row_kind",
              "dwelling", "famiglie", "present_mf", "present_f", "absent_mf",
              "is_consistent", "locality_it", "circoscrizione_it", "shabiya_en",
              "shabiya_pcode", "label_printed"]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:32s} {len(rows):5d} rows")


def report(rows):
    kinds = Counter(row["row_kind"] for row in rows)
    print(f"\n{len(rows)} lines read from table XX, {dict(kinds)}")
    good = [r for r in rows if r["is_consistent"]]
    print(f"{len(good)} rows pass the consistency checks")
    people = [r for r in good if r["row_kind"] in ("locality", "quarter")]
    total = sum(r["present_mf"] for r in people)
    print(f"\n{len(people)} locality and quarter rows, "
          f"{total:,} present, against the volume's own {PUBLISHED_TOTAL:,} "
          f"({100 * total / PUBLISHED_TOTAL:.1f}%)")
    print("dwelling:", dict(Counter(r["dwelling"] or "(none)" for r in people)))
    tied = [r for r in people if r["shabiya_en"]]
    print(f"{len(tied)} of them tie to a locality of appendix II, "
          f"{sum(r['present_mf'] for r in tied):,} present")
    print("  by shabiya:", dict(Counter(r["shabiya_en"] for r in tied).most_common(8)))
    subtotals = [r for r in good if r["row_kind"] == "subtotal"]
    print(f"{len(subtotals)} subtotal rows, {sum(r['present_mf'] for r in subtotals):,} "
          f"present between them")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
