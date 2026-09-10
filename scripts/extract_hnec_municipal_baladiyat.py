#!/usr/bin/env python3
"""
Date the polling-centre register forward, from HNEC's 2024 and 2025 documents.

The 2021 register (`scripts/extract_hnec_polling_centres.py`) names each polling
centre's locality and its municipality, and is the only complete statement of
which locality sits in which baladiya. Two later collections restate the
municipality for a subset of the same centres, and both are read here through
the **centre code** rather than the Arabic text:

  municipal_2025/    "المراكز_<office>_<baladiya>", October 2025, one document
                     per municipality holding a council election. The
                     municipality is in the file name. The text layer is
                     scrambled — the embedded fonts carry a ToUnicode map that
                     reports a different letter for almost every glyph, so the
                     Arabic extracts as ﺗﺜﺮﺟﺊ where the page shows مدرسة — but
                     the digits are unaffected, and the centre code is all this
                     needs.
  card_distribution/ voter-card distribution statistics for the 2024 and 2025
                     municipal rounds, whose centre name ends in the
                     municipality in brackets.

Each centre code is drawn twice in the 2025 documents, a shadow copy offset by
0.06pt, and two adjacent rows therefore land on one baseline and interleave into
a single run of digits. A run whose length is a multiple of five is de-interleaved
by stride, which is exact: every one of the 360 codes recovered this way is a
code the 2021 register already lists.

What this adds is a municipality for centres whose 2021 locality name was
mangled by the broken fonts in two of the 24 register documents, and the current
spelling of municipalities those documents printed as رست for سرت and طربق for
طبرق. `scripts/build_concordance.py` merges the spellings by the centre codes
they share.

Output:
  data/processed/hnec_centre_baladiya_2024_2025.csv   one row per centre and
                                                      document
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import normalise_name, to_logical  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hnec"
OUT = ROOT / "data" / "processed"

CODE_LENGTH = 5
# "<code> <centre name> (<baladiya>) <a number>" on one reconstructed line.
STATISTIC_ROW = re.compile(r"(\d{4,6})\s+(.{3,120}?)\)([^)(]{2,40})\(\s+\d")
# The statistics' embedded font substitutes Latin letters into some Arabic
# words, printing م اzتة for مصراتة. A name that is not Arabic throughout was
# misread, and naming a municipality is the whole point of the row, so it goes.
ARABIC_NAME = re.compile(r"^[\u0620-\u064a\u0670-\u06d3 ]{3,}$")


def municipal_codes(path):
    """Centre codes in one 2025 per-municipality document."""
    codes = set()
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            baselines = defaultdict(list)
            for char in page.chars:
                if char["text"].isdigit():
                    baselines[round(char["top"], 2)].append(char)
            for chars in baselines.values():
                chars.sort(key=lambda c: c["x0"])
                digits = "".join(c["text"] for c in chars)
                if not digits or len(digits) % CODE_LENGTH:
                    continue
                # One baseline can carry several interleaved rows.
                rows = len(digits) // CODE_LENGTH
                codes.update(digits[i::rows] for i in range(rows))
    return codes


def statistic_rows(path):
    """(centre code, municipality) from one card-distribution statistic."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join(to_logical(page.extract_text() or "") for page in pdf.pages)
    rows, unreadable = [], 0
    for code, _, baladiya in STATISTIC_ROW.findall(text):
        name = normalise_name(baladiya)
        if ARABIC_NAME.match(name):
            rows.append((code, name))
        else:
            unreadable += 1
    return rows, unreadable


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    register = {}
    path = OUT / "hnec_polling_centres_2021.csv"
    if path.exists():
        with path.open() as fh:
            register = {r["centre_code"]: r for r in csv.DictReader(fh)}
    if not register:
        sys.exit("run scripts/extract_hnec_polling_centres.py first")

    rows, unknown, unreadable = [], 0, 0
    for name, prefix in (("municipal_2025", "mc"), ("card_distribution", "cd")):
        manifest = json.loads((RAW / f"{name}_manifest.json").read_text())
        for entry in manifest:
            document = RAW / name / entry["file"]
            if not document.exists():
                continue
            if prefix == "mc":
                # المراكز_<electoral office>_<municipality>
                baladiya = entry["title"].split("_")[-1].strip()
                found = [(code, baladiya) for code in municipal_codes(document)]
            else:
                found, misread = statistic_rows(document)
                unreadable += misread
            kept = 0
            for code, baladiya in found:
                if code not in register:
                    unknown += 1
                    continue
                kept += 1
                rows.append({
                    "centre_code": code,
                    "baladiya_ar": baladiya,
                    "source_collection": name,
                    "mahalla_ar": register[code]["mahalla_ar"],
                    "city_ar": register[code]["city_ar"],
                    "baladiya_2021_ar": register[code]["baladiya_ar"],
                    "source_date": entry["date"][:10],
                    "source_document": entry["title"],
                    "source_sha256": entry["sha256"],
                })
            print(f"  {entry['title'][:52]:54s} {kept:4d} centres")

    fields = list(rows[0])
    path = OUT / "hnec_centre_baladiya_2024_2025.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["source_date"],
                                                     r["centre_code"])))

    centres = len({r["centre_code"] for r in rows})
    baladiyat = len({r["baladiya_ar"] for r in rows})
    print(f"\n{path.name:38s} {len(rows)} statements, {centres} centres, "
          f"{baladiyat} municipalities")
    print(f"{'':38s} {unknown} centre codes not in the 2021 register, "
          f"{unreadable} municipality names misread and dropped")
    print("next: python3 scripts/build_concordance.py")


if __name__ == "__main__":
    main()
