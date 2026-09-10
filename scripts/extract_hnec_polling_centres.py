#!/usr/bin/env python3
"""
Extract HNEC's polling-centre register, which states each locality's municipality.

Source: High National Elections Commission, "تحديث مراكز الاقتراع لسنة 2021"
<https://hnec.ly>, 24 documents, one per electoral office region.

Each row is a polling centre, and the columns are exactly the link the
concordance was missing:

    رمز المركز | اسم مركز الاقتراع | المحلة | المدينة | البلدية
    centre code | centre name      | locality | city   | municipality

The 2006 census names 667 mahallat but stops before the 2013 municipal
reorganisation; HNEC's register names the same localities and states which
baladiya each now sits in. Joining on the locality gives the mahalla-to-baladiya
mapping that no published crosswalk provides.

Columns are located from the printed header on each page rather than assumed,
and cells are rebuilt from word coordinates (see `scripts/pdf_tables.py`): the
Arabic is right-to-left and a centre name can straddle two baselines.

Two of the 24 documents embed a font whose character map maps every plain alef
to alef-with-hamza-below, so their text layer returns إلبلدية for البلدية and
مرصإتة for مصراتة. They are detected by the share of that character, which is
rare in real Libyan place names and pervasive here, and the substitution is
undone before parsing. A few words in those two also carry letter-order noise
that cannot be repaired, so their names are matched through the normalised key
in `build_concordance.join_key`, which folds the alef variants anyway.

Outputs:
  data/processed/hnec_polling_centres_2021.csv   one row per polling centre
  data/processed/hnec_locality_baladiya.csv      distinct locality-municipality pairs
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import is_arabic, normalise_name, to_logical  # noqa: E402
from pdf_tables import page_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hnec"
PDFS = RAW / "polling_centres"
OUT = ROOT / "data" / "processed"

# Printed column headers, right to left. The centre-code heading ("رمز المركز")
# is set on two lines and is not looked for: the code is found in the data
# instead, as the cell that is a bare number.
HEADERS = [
    ("centre_name", ("اسم", "مركز")),
    ("mahalla", ("المحلة",)),
    ("city", ("المدينة",)),
    ("baladiya", ("البلدية",)),
]

CODE = re.compile(r"^\d{4,6}$")
# Alef with hamza below is rare in these place names but pervasive in the
# mojibake the two broken fonts produce.
BROKEN_ALEF_SHARE = 0.25


# The broken font emits alef-with-hamza-below for every plain alef.
BROKEN_FONT_REPAIR = str.maketrans({"إ": "ا"})


def text_is_broken(text):
    logical = to_logical(text)
    alefs = logical.count("ا") + logical.count("إ")
    if alefs < 40:
        return False
    return logical.count("إ") / alefs > BROKEN_ALEF_SHARE


def header_columns(rows):
    """Locate each column from the printed header band. None if not found."""
    for row in rows:
        found = {}
        for name, words in HEADERS:
            for cell in row:
                logical = to_logical(cell.text).translate(BROKEN_FONT_REPAIR)
                if all(w in logical for w in words):
                    found[name] = cell.centre
                    break
        # The header band must name at least the locality and the municipality.
        if "mahalla" in found and "baladiya" in found and len(found) >= 3:
            return found
    return None


def assign(row, columns, tolerance, clean=None):
    """Map a row's cells onto the located columns by horizontal position."""
    clean = clean or (lambda t: to_logical(t).strip())
    out = {}
    for cell in row:
        name, distance = min(((n, abs(cell.centre - c)) for n, c in columns.items()),
                             key=lambda p: p[1])
        if distance > tolerance:
            continue
        out[name] = (out.get(name, "") + " " + clean(cell.text)).strip()
    return out


def read_pdf(path, warnings):
    """Return polling-centre rows from one document."""
    rows_out = []
    with pdfplumber.open(path) as pdf:
        whole = "\n".join((page.extract_text() or "") for page in pdf.pages)
        broken = text_is_broken(whole)
        if broken:
            warnings.append(f"{path.name}: broken font repaired before parsing")

        def clean(text):
            text = to_logical(text).strip()
            return text.translate(BROKEN_FONT_REPAIR) if broken else text

        # The header is printed on the first page only; later pages continue
        # the same grid, so the columns are learned once and reused.
        columns = None
        for page in pdf.pages:
            rows = page_rows(page)
            columns = header_columns(rows) or columns
            if columns is None:
                continue
            spacing = sorted(columns.values())
            tolerance = min(b - a for a, b in zip(spacing, spacing[1:])) / 2

            for row in rows:
                code = next((c.text.strip() for c in row
                             if CODE.match(c.text.strip())), None)
                if code is None:
                    continue
                body = [c for c in row if c.text.strip() != code]
                record = assign(body, columns, tolerance, clean)
                if not is_arabic(record.get("mahalla", "")):
                    continue
                rows_out.append({
                    "centre_code": code,
                    "centre_name": normalise_name(record.get("centre_name", "")),
                    "mahalla_ar": normalise_name(record.get("mahalla", "")),
                    "city_ar": normalise_name(record.get("city", "")),
                    "baladiya_ar": normalise_name(record.get("baladiya", "")),
                    "read_by": "text_repaired" if broken else "text",
                })
    return rows_out


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()

    manifest = json.loads((RAW / "polling_centres_manifest.json").read_text())
    by_file = {m["file"]: m for m in manifest}

    records, warnings = [], []
    for path in sorted(PDFS.glob("*.pdf")):
        source = by_file.get(path.name, {})
        try:
            rows = read_pdf(path, warnings)
        except Exception as exc:                       # noqa: BLE001
            warnings.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        for row in rows:
            row["source_document"] = source.get("title", path.name)
            row["source_sha256"] = source.get("sha256", "")
        records.extend(rows)
        print(f"  {source.get('title', path.name)[:46]:48s} {len(rows):4d} centres")

    # A centre code is unique nationally; the same document sometimes repeats a
    # row across a page break.
    seen, deduped = set(), []
    for row in sorted(records, key=lambda r: r["centre_code"]):
        if row["centre_code"] in seen:
            continue
        seen.add(row["centre_code"])
        deduped.append(row)

    fields = ["centre_code", "centre_name", "mahalla_ar", "city_ar", "baladiya_ar",
              "read_by", "source_document", "source_sha256"]
    path = OUT / "hnec_polling_centres_2021.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(deduped)

    pairs = defaultdict(Counter)
    for row in deduped:
        if row["mahalla_ar"] and row["baladiya_ar"]:
            pairs[(row["mahalla_ar"], row["baladiya_ar"])][row["city_ar"]] += 1

    pair_rows = [{
        "mahalla_ar": mahalla, "baladiya_ar": baladiya,
        "city_ar": cities.most_common(1)[0][0],
        "polling_centres": sum(cities.values()),
    } for (mahalla, baladiya), cities in sorted(pairs.items())]

    pair_path = OUT / "hnec_locality_baladiya.csv"
    with pair_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(pair_rows[0]))
        writer.writeheader()
        writer.writerows(pair_rows)

    localities = len({r["mahalla_ar"] for r in pair_rows})
    baladiyat = len({r["baladiya_ar"] for r in pair_rows})
    print(f"\n{path.name:38s} {len(deduped):5d} polling centres")
    print(f"{pair_path.name:38s} {len(pair_rows):5d} locality-municipality pairs, "
          f"{localities} localities, {baladiyat} municipalities")
    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print("  " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
