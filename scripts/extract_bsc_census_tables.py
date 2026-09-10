#!/usr/bin/env python3
"""
Extract every table of the 2006 general population census.

Source: https://bsc.ly/demog_statist/, 22 volumes, one per shabiya.

Each volume prints the same 74 tables in eleven sections, covering household
composition, age and sex structure, non-Libyan residents by country of origin,
school enrolment, educational attainment, marital status, manpower, occupation,
economic activity, employment status, and housing conditions. Roughly half are
broken down by mahalla; the rest cross-tabulate at shabiya level.

Rather than hard-code 74 schemas, this reads the tables structurally. For each
page it finds the table number, rebuilds cells from geometry (see
`scripts/pdf_tables.py`), learns the column positions from the page's own data
rows, and reads the column labels off the header bands above them: the band
whose cell count matches the data columns gives the per-column label, and the
wider bands above it give the group each column sits under.

Output is one long file per section, so a researcher can take just the tables
they need:

  bsc_census_2006_cells_<section>.csv.gz   one row per figure
  bsc_census_2006_table_index.csv          which tables were read, and how

Every figure is reproduced as printed. Where a table prints male, female and
total columns, the identity total = male + female is checked on every row and
the breach rate is reported.
"""

import argparse
import csv
import gzip
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import is_arabic, normalise_name, to_logical  # noqa: E402
from pdf_tables import assign_by_centre, page_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "bsc"
OUT = ROOT / "data" / "processed"

# "Table (47 - 4)" is table 47, continuation sheet 4. The Latin form is used
# because it survives extraction unreversed.
TABLE_NO = re.compile(r"Table\s*\(?\s*(\d{1,3})\s*(?:[-ـ–]\s*(\d{1,3}))?\s*\)?")
NUMERIC = re.compile(r"^\d[\d\s ]*$")
DECIMAL = re.compile(r"^\d{1,3}(?:[\s ]\d{3})*\.\d+$|^\d+\.\d+$")

# The eleven sections of every volume, keyed by the first and last table number.
SECTIONS = [
    (1, 9, "households", "Resident households and their characteristics"),
    (10, 12, "age_sex", "Resident population by age and sex"),
    (13, 13, "non_libyans", "Non-Libyan residents by country group"),
    (14, 16, "enrolment", "Population aged 4-30 in education"),
    (17, 20, "education", "Population aged 10+ by educational status"),
    (21, 28, "marital", "Population aged 15+ by marital status"),
    (29, 36, "manpower", "Population aged 15+ by manpower category"),
    (37, 45, "occupation", "Economically active 15+ by occupation"),
    (46, 56, "activity", "Economically active 15+ by economic activity"),
    (57, 68, "employment", "Economically active 15+ by employment status"),
    (69, 74, "housing", "Housing conditions of Libyan households"),
]

SHABIYA_EN = {
    "البطنان": "Butnan", "درنة": "Derna", "الجبل الأخضر": "Jabal al Akhdar",
    "المرج": "Marj", "بنغازي": "Benghazi", "الواحات": "Al Wahat",
    "الكفرة": "Kufra", "سرت": "Sirte", "الجفرة": "Jufra", "مصراته": "Misrata",
    "المرقب": "Murqub", "طرابلس": "Tripoli", "الجفارة": "Jafara",
    "الزاوية": "Zawiya", "النقاط الخمس": "Nuqat al Khams",
    "الجبل الغربي": "Jabal al Gharbi", "نالوت": "Nalut", "سبها": "Sabha",
    "وادي الشاطئ": "Wadi al Shatii", "مرزق": "Murzuq",
    "وادي الحياة": "Wadi al Hayaa", "غات": "Ghat",
}
TITLE_STRIP = re.compile(r"نتائج|تعداد|العام|لسكان|مدينة|المنطقة|لسنة|2006\s*م?|م$")

# Matched as whole words. "female" contains "male", so a substring test would
# label every female column male.
MALE = re.compile(r"\bmale\b|ذكور")
FEMALE = re.compile(r"\bfemale\b|إناث|اناث")
TOTAL = re.compile(r"\btotal\b|المجموع|مجموع")

# An age band prints as "45 ــ 49". The two numbers are laid out left to right
# inside a right-to-left line, so their order survives extraction reversed in
# some tables and not others. Both are normalised to low-high.
# A range is digits and punctuation only. At least one separator is required,
# otherwise "10" would read as the range 0 to 1; and no letters are allowed,
# otherwise "85 & more 85" would read as the range 85 to 85.
RANGE = re.compile(r"^(\d{1,3})[^0-9A-Za-z؀-ۿ]+(\d{1,3})$")


def section_of(table_no):
    for first, last, slug, title in SECTIONS:
        if first <= table_no <= last:
            return slug, title
    return "other", "Unclassified"


def parse_value(text):
    """Return (value, is_percentage) for a printed figure, or (None, None)."""
    plain = to_logical(text).replace(" ", " ").strip()
    if NUMERIC.match(plain):
        return float(re.sub(r"\s", "", plain)), False
    if DECIMAL.match(plain):
        return float(re.sub(r"\s", "", plain)), True
    return None, None


def label_of(cell):
    """Split a bilingual header cell into its Arabic and Latin halves."""
    text = to_logical(cell.text)
    arabic = " ".join(w for w in text.split() if is_arabic(w))
    latin = " ".join(w for w in text.split() if not is_arabic(w))
    return normalise_name(arabic), " ".join(latin.split()).strip(" ()")


def kind_of(arabic, latin):
    joined = f"{arabic} {latin}".casefold()
    if FEMALE.search(joined):
        return "female"
    if MALE.search(joined):
        return "male"
    if TOTAL.search(joined):
        return "total"
    if "%" in joined:
        return "percent"
    if "عدد" in joined or joined.strip() == "no.":
        return "count"
    return ""


def clean_tokens(tokens):
    """Drop the duplicate and fragment tokens the source's typesetting leaves.

    Some labels are drawn twice, once normally and once with the letters spaced
    apart, so extraction returns both the word and its separate letters.
    Repeated tokens are collapsed, and lone Arabic letters are dropped when the
    label also carries real words.
    """
    seen, out = set(), []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            out.append(token)
    if any(is_arabic(t) and len(t) >= 3 for t in out):
        out = [t for t in out if not (is_arabic(t) and len(t) == 1)]
    return out


def normalise_row_label(text):
    """Return (arabic, latin) for a row label, ranges in ascending order.

    Row labels are bilingual and the two languages interleave in one cell, so
    they are separated the same way as column labels.
    """
    tokens = clean_tokens(to_logical(text).split())
    arabic = normalise_name(" ".join(w for w in tokens if is_arabic(w)))
    latin = " ".join(w for w in tokens if not is_arabic(w))
    latin = " ".join(latin.split()).strip(" ()")

    # A bare range is the row's identity and belongs in the Arabic column. The
    # Latin side is only tested when there is no Arabic, so that a label like
    # "85 and over" is not mistaken for the range 85 to 85.
    for value in ([arabic] if arabic else [arabic, latin]):
        found = RANGE.match(value.strip())
        if found:
            low, high = sorted((int(found.group(1)), int(found.group(2))))
            if low != high:
                return f"{low}-{high}", ""
    if not arabic and latin.strip().isdigit():
        return latin.strip(), ""
    return arabic, latin


def split_stub(band):
    """Split a printed row into its leading label cells and its figures.

    Reading right to left, a row opens with one or more stub cells, then the
    figures, then sometimes an English gloss set in the left margin, which is
    discarded. A stub is identified by position, not by whether it looks like a
    number: the age tables label their rows "48", and treating that as a figure
    would shift every column and drop the row.
    """
    leading, values, seen_number = [], [], False
    for cell in band:
        numeric = parse_value(cell.text)[0] is not None
        if not seen_number:
            if numeric:
                seen_number = True
                values.append(cell)
            else:
                leading.append(cell)
        elif numeric:
            values.append(cell)
        else:
            break                      # gloss in the left margin
    if not leading and values:
        # No text stub, so the row is labelled by its first figure.
        leading, values = [values[0]], values[1:]
    return leading, values


def read_page(page):
    """Return (caption, columns, data rows, raw header bands) for a table page.

    None if the page holds no table this reader recognises.
    """
    rows = page_rows(page)
    if not rows:
        return None

    # The page title sits above the "Table (N)" band; the column headers below
    # it. Anchoring on that band keeps the title out of the column labels.
    anchor = next((i for i, band in enumerate(rows)
                   if TABLE_NO.search(to_logical(" ".join(c.text for c in band)))),
                  None)
    if anchor is None:
        return None

    title_bands = rows[:anchor]
    caption_ar, caption_en = [], []
    for band in title_bands:
        arabic, latin = label_of_band(band)
        if arabic:
            caption_ar.append(arabic)
        if latin:
            caption_en.append(latin)

    # Data rows: a label followed by at least two figures. The label may be
    # Arabic (a mahalla, an occupation) or numeric (a household size, an age).
    def collect(after):
        found = []
        for index, band in enumerate(rows):
            if index <= after or len(band) < 3:
                continue
            labels, values = split_stub(band)
            if len(values) < 2 or not labels:
                continue
            found.append((index, labels, values))
        return found

    candidates = collect(anchor)
    if len(candidates) < 3:
        # A few pages print the table number below the figures rather than
        # above, which would exclude the whole table.
        candidates = collect(-1)
    if len(candidates) < 3:
        return None

    width = Counter(len(values) for _, _, values in candidates).most_common(1)[0][0]
    if width < 2:
        return None
    complete = [values for _, _, values in candidates if len(values) == width]
    if len(complete) < 3:
        return None
    centres = [statistics.median(col) for col in
               zip(*[[c.centre for c in cells] for cells in complete])]
    spacing = min((abs(a - b) for a, b in zip(centres, centres[1:])), default=40)
    tolerance = spacing / 2

    # Header bands lie between the table-number band and the first data row.
    first_data = candidates[0][0]
    header_bands = [band for band in rows[anchor + 1:first_data]
                    if any(parse_value(c.text)[0] is None for c in band)]

    # The lowest band with one labelled cell per column gives the column labels;
    # the nearest band above it that spans several columns gives the group.
    per_column, group_band = None, None
    for position in range(len(header_bands) - 1, -1, -1):
        labelled = [c for c in header_bands[position]
                    if parse_value(c.text)[0] is None]
        if len(labelled) == width:
            per_column = labelled
            group_band = next((b for b in reversed(header_bands[:position])
                               if 1 < len(b) < width), None)
            break
    if per_column is None:
        group_band = next((b for b in reversed(header_bands) if 1 < len(b) <= width),
                          None)

    columns = []
    for index, centre in enumerate(centres):
        label_ar = label_en = ""
        if per_column is not None:
            label_ar, label_en = label_of(per_column[index])
        group_ar = group_en = ""
        if group_band:
            # A group heading is typeset narrower than the columns it spans, so
            # columns are assigned to the nearest heading rather than requiring
            # the column centre to fall inside it.
            match = min(group_band, key=lambda c: abs(c.centre - centre))
            group_ar, group_en = label_of(match)
        columns.append({"column_index": index + 1,
                        "column_label_ar": label_ar, "column_label_en": label_en,
                        "column_group_ar": group_ar, "column_group_en": group_en,
                        "column_kind": kind_of(label_ar, label_en)})

    # Some tables carry a two-level stub: an outer category printed once beside
    # the first of its sub-rows, and an inner label on every sub-row. Stub levels
    # are found the same way as the value columns, and an outer label is carried
    # down until the next one appears.
    depth = max(len(labels) for _, labels, _ in candidates)
    stub_centres = None
    if depth > 1:
        deepest = [labels for _, labels, _ in candidates if len(labels) == depth]
        if len(deepest) >= 2:
            stub_centres = [statistics.median(col) for col in
                            zip(*[[c.centre for c in labels] for labels in deepest])]

    staged = []
    for _, labels, cells in candidates:
        mapped = assign_by_centre(cells, centres, tolerance)
        if mapped is None:
            continue
        levels = [""] * depth
        if stub_centres is not None:
            placed = assign_by_centre(labels, stub_centres, tolerance * 3)
            if placed is None:
                placed = dict(enumerate(labels))
            for level, cell in placed.items():
                levels[level] = cell.text
        else:
            levels[0] = labels[0].text
        staged.append((levels, mapped))

    # An outer label is printed once per block, beside whichever sub-row it
    # happens to sit next to, which is often the middle one. Each unlabelled row
    # therefore takes the label of the nearer labelled row, above or below,
    # rather than only inheriting downwards.
    for level in range(depth - 1):
        marked = [i for i, (levels, _) in enumerate(staged) if levels[level]]
        if not marked:
            continue
        for position, (levels, _) in enumerate(staged):
            if levels[level]:
                continue
            nearest = min(marked, key=lambda i: (abs(i - position), i > position))
            levels[level] = staged[nearest][0][level]

    data = []
    for levels, mapped in staged:
        group_ar, group_en = normalise_row_label(levels[0]) if depth > 1 else ("", "")
        label_ar, label_en = normalise_row_label(levels[-1])
        values = {}
        for index, cell in mapped.items():
            value, is_pct = parse_value(cell.text)
            if value is not None:
                values[index] = (value, is_pct)
        if values:
            data.append((label_ar, label_en, group_ar, group_en, values))

    raw_headers = [[c.text for c in band] for band in header_bands]
    caption = (" | ".join(caption_ar[:3]), " | ".join(caption_en[:3]))
    return caption, columns, data, raw_headers


def label_of_band(band):
    """Arabic and Latin halves of a whole band, in printed order."""
    text = to_logical(" ".join(c.text for c in band))
    arabic = " ".join(w for w in text.split() if is_arabic(w))
    latin = " ".join(w for w in text.split() if not is_arabic(w))
    return normalise_name(arabic), " ".join(latin.split()).strip(" ()")


def check_sex_identity(columns, data):
    """Count rows where a printed total does not equal male + female."""
    triples = []
    for i in range(len(columns) - 2):
        kinds = [columns[i + k]["column_kind"] for k in range(3)]
        if kinds == ["male", "female", "total"]:
            triples.append((i, i + 1, i + 2))
    checked = breached = 0
    for *_, values in data:
        for male, female, total in triples:
            if not all(k in values for k in (male, female, total)):
                continue
            if any(values[k][1] for k in (male, female, total)):
                continue          # percentages, not counts
            checked += 1
            if values[total][0] != values[male][0] + values[female][0]:
                breached += 1
    return checked, breached


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--volumes", type=int, default=0,
                        help="read only the first N volumes (for a quick test)")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RAW / "bsc_pdf_manifest.json").read_text())
    volumes = sorted([d for d in manifest if "تعداد" in d["title_ar"]],
                     key=lambda d: d["title_ar"])
    if args.volumes:
        volumes = volumes[:args.volumes]
    print(f"{len(volumes)} census volumes, 74 tables each")

    by_section = defaultdict(list)
    index = defaultdict(lambda: {"pages": 0, "rows": 0, "cells": 0,
                                 "volumes": set(), "captions": Counter(),
                                 "checked": 0, "breached": 0})
    headers = {}
    warnings = []

    for doc in volumes:
        path = RAW / "pdf" / doc["local"]
        if not path.exists():
            warnings.append(f"{doc['title_ar'][:40]}: file missing")
            continue
        volume = normalise_name(TITLE_STRIP.sub(" ", doc["title_ar"]))
        pages_read = cells_written = 0

        with pdfplumber.open(path) as pdf:
            for page_no, page in enumerate(pdf.pages):
                text = to_logical(page.extract_text() or "")
                found = TABLE_NO.search(text)
                if not found:
                    continue
                table_no = int(found.group(1))
                if not 1 <= table_no <= 74:
                    continue
                sheet = int(found.group(2)) if found.group(2) else 1

                parsed = read_page(page)
                if parsed is None:
                    continue
                caption, columns, data, raw_headers = parsed
                slug, _ = section_of(table_no)
                by_column = {c["column_index"]: c for c in columns}

                for row_label, row_label_en, group_ar, group_en, values in data:
                    for column_index, (value, is_pct) in sorted(values.items()):
                        meta = by_column[column_index + 1]
                        by_section[slug].append({
                            "shabiya_ar": volume,
                            "shabiya_en": SHABIYA_EN.get(volume, ""),
                            "table_no": table_no, "sheet": sheet,
                            "pdf_page": page_no,
                            "row_label_ar": row_label,
                            "row_label_en": row_label_en,
                            "row_group_ar": group_ar,
                            "row_group_en": group_en,
                            **meta,
                            "value": value,
                            "is_percentage": int(bool(is_pct)),
                        })
                        cells_written += 1

                entry = index[table_no]
                entry["pages"] += 1
                entry["rows"] += len(data)
                entry["cells"] += sum(len(v) for *_, v in data)
                entry["volumes"].add(volume)
                if caption[0]:
                    entry["captions"][caption] += 1
                key = (table_no, sheet)
                if key not in headers:
                    headers[key] = [
                        {"table_no": table_no, "sheet": sheet,
                         "band": band_no, "cell": cell_no, "text": to_logical(t)}
                        for band_no, band in enumerate(raw_headers)
                        for cell_no, t in enumerate(band)]
                checked, breached = check_sex_identity(columns, data)
                entry["checked"] += checked
                entry["breached"] += breached
                pages_read += 1

        print(f"  {volume:22s} {pages_read:4d} table pages, {cells_written:7,d} figures")

    total = 0
    for first, last, slug, title in SECTIONS:
        rows = by_section.get(slug)
        if not rows:
            continue
        fields = list(rows[0])
        path = OUT / f"bsc_census_2006_cells_{slug}.csv.gz"
        with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        total += len(rows)
        print(f"{path.name:44s} {len(rows):8,d} figures  "
              f"tables {first}-{last}  {path.stat().st_size / 1e6:.1f} MB")

    with (OUT / "bsc_census_2006_table_index.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "table_no", "section", "section_title", "caption_ar", "caption_en",
            "volumes", "pages", "rows", "cells", "sex_identity_checked",
            "sex_identity_breached"])
        writer.writeheader()
        for table_no in sorted(index):
            entry = index[table_no]
            slug, title = section_of(table_no)
            caption = entry["captions"].most_common(1)
            best = caption[0][0] if caption else ("", "")
            writer.writerow({
                "table_no": table_no, "section": slug, "section_title": title,
                "caption_ar": best[0], "caption_en": best[1],
                "volumes": len(entry["volumes"]), "pages": entry["pages"],
                "rows": entry["rows"], "cells": entry["cells"],
                "sex_identity_checked": entry["checked"],
                "sex_identity_breached": entry["breached"]})

    with (OUT / "bsc_census_2006_table_headers.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["table_no", "sheet", "band",
                                                "cell", "text"])
        writer.writeheader()
        for key in sorted(headers):
            writer.writerows(headers[key])

    checked = sum(e["checked"] for e in index.values())
    breached = sum(e["breached"] for e in index.values())
    print(f"\n{len(index)} distinct tables, {total:,} figures")
    if checked:
        print(f"male + female = total: {checked:,} checks, {breached:,} breaches "
              f"({100 * breached / checked:.3f}%)")
    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print("  " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
