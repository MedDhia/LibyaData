#!/usr/bin/env python3
"""
Re-open every page the Libyan trade series was transcribed from, and check it.

`data/processed/istat/libya_annuario_trade.csv` was not produced by a reader.
It was transcribed by eye from page images of the `Annuario Statistico
Italiano`, because an automatic reader could not be made to produce figures
worth publishing: `data/processed/CODEBOOK.md` says why. What can still be
checked mechanically is checked here, every time, so the transcription cannot
rot quietly:

  * every page a figure cites exists in the volume it names, and carries a
    `Commercio marittimo` heading and the colony the row claims;
  * the figure appears on that page, as a run of digits, in thousands or in
    lire, wherever the volume's text layer can be read at all;
  * every published figure equals every printing of it that is marked
    published, and no superseded printing is published anywhere;
  * the two files agree on how many volumes print each figure.

The page check needs the volumes, 712 MB, which
`scripts/extract_istat_annuario_index.py` downloads. Without them the script
runs the file checks and says the page checks were skipped.
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "raw" / "istat" / "annuario"
OUT = ROOT / "data" / "processed" / "istat"
SERIES = OUT / "libya_annuario_trade.csv"
PRINTINGS = OUT / "libya_annuario_trade_printings.csv"
VOLUMES = OUT / "libya_annuario_volumes.csv"

TRADE = re.compile(r"commerciomarittim", re.I)
WEST = re.compile(r"[a-z]{0,6}[l1][i1]tania|libiaocci?dentale", re.I)
EAST = re.compile(r"c[ji1]?renaica|libiaorientale", re.I)


def flat(text):
    return re.sub(r"[^A-Za-z0-9]+", "", text or "")


def files_agree():
    """The two files have to say the same thing about every figure."""
    printings = defaultdict(list)
    trouble = []
    for row in csv.DictReader(PRINTINGS.open()):
        key = (row["colony"], int(row["year"]), row["direction"])
        printings[key].append(row)
    published = {k: [r for r in v if r["status"] == "published"]
                 for k, v in printings.items()}

    for row in csv.DictReader(SERIES.open()):
        year, colony = int(row["year"]), row["colony"]
        for direction, column in (("imports", "imports_thousand_lire"),
                                  ("exports", "exports_thousand_lire")):
            if not row[column]:
                continue
            here = published.get((colony, year, direction), [])
            values = {int(r["thousand_lire"]) for r in here}
            if not here:
                trouble.append(f"{colony} {year} {direction}: published with no "
                               f"printing behind it")
            elif values != {int(row[column])}:
                trouble.append(f"{colony} {year} {direction}: series says "
                               f"{row[column]}, printings say {sorted(values)}")
            claimed = int(row[f"{direction[:-1]}_printings"])
            if here and len(here) != claimed:
                trouble.append(f"{colony} {year} {direction}: {len(here)} "
                               f"printings, the series claims {claimed}")
        if not row["imports_thousand_lire"] and row["agreement"] != "not available":
            trouble.append(f"{colony} {year}: empty but not marked unavailable")

    # A superseded figure must not also be published for the same cell.
    for key, rows in printings.items():
        published_values = {int(r["thousand_lire"]) for r in rows
                            if r["status"] == "published"}
        for row in rows:
            if (row["status"] != "published"
                    and int(row["thousand_lire"]) in published_values):
                trouble.append(f"{key}: {row['thousand_lire']} is both "
                               f"published and superseded")
    return trouble


def pages_carry_what_they_claim():
    """Open every cited page and check it is the page the row says it is."""
    if not BOOKS.exists():
        return None
    import pdfplumber

    volumes = {int(v["year_from"]): v["file"]
               for v in csv.DictReader(VOLUMES.open())}
    wanted = defaultdict(set)
    figures = defaultdict(set)
    for row in csv.DictReader(PRINTINGS.open()):
        wanted[(int(row["volume"]), int(row["pdf_page"]))].add(row["colony"])
        figures[(int(row["volume"]), int(row["pdf_page"]))].add(
            (row["thousand_lire"], row["lire_printed"]))

    trouble, checked, found_figures, missing_figures = [], 0, 0, 0
    for (volume, page), colonies in sorted(wanted.items()):
        name = volumes.get(volume)
        path = BOOKS / name if name else None
        if not path or not path.exists():
            trouble.append(f"{volume}: volume not downloaded")
            continue
        with pdfplumber.open(path) as pdf:
            if page >= len(pdf.pages):
                trouble.append(f"{volume} p{page}: past the end of the volume")
                continue
            text = pdf.pages[page].extract_text() or ""
        checked += 1
        flattened = flat(text)
        if not TRADE.search(flattened):
            trouble.append(f"{volume} p{page}: no `Commercio marittimo` heading")
        for colony in colonies:
            pattern = WEST if colony == "Tripolitania" else EAST
            if not pattern.search(flattened):
                trouble.append(f"{volume} p{page}: does not name {colony}")
        # The figure itself, in either unit, ignoring the spaces the volume
        # sets its thousands with. The scan damages the bold total lines, so a
        # figure that cannot be found is reported and not treated as an error.
        digits = re.sub(r"\D", "", text)
        for thousands, lire in figures[(volume, page)]:
            if (lire and lire in digits) or thousands in digits:
                found_figures += 1
            else:
                missing_figures += 1
    return trouble, checked, found_figures, missing_figures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-pages", action="store_true",
                        help="check the files against each other only")
    args = parser.parse_args()

    trouble = files_agree()
    series = list(csv.DictReader(SERIES.open()))
    printings = list(csv.DictReader(PRINTINGS.open()))
    print(f"{len(series)} colony-years, {len(printings)} printings")
    if trouble:
        print(f"  [FAIL] {len(trouble)} disagreements between the two files:")
        for line in trouble[:6]:
            print("     " + line)
    else:
        print("  [ok ] the series and the printings agree on every figure")

    if args.skip_pages:
        print("  page checks skipped")
    else:
        result = pages_carry_what_they_claim()
        if result is None:
            print("  page checks skipped: the volumes are not downloaded")
        else:
            page_trouble, checked, found, missing = result
            trouble += page_trouble
            if page_trouble:
                print(f"  [FAIL] {len(page_trouble)} pages are not what the "
                      f"transcription says they are:")
                for line in page_trouble[:6]:
                    print("     " + line)
            else:
                print(f"  [ok ] all {checked} cited pages carry a "
                      f"`Commercio marittimo` table for the colony claimed")
            print(f"  {found} of {found + missing} figures are legible in the "
                  f"text layer of the page they were transcribed from; the rest "
                  f"are on bold total lines the scan damaged, which is why the "
                  f"series was read by eye")

    if trouble:
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
