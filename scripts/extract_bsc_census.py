#!/usr/bin/env python3
"""
Extract the 2006 general population census, Table 1, from the Bureau of
Statistics and Census volumes.

Source: https://bsc.ly/demog_statist/ (catalogued by harvest_bsc_catalogue.py)

One volume per shabiya, 22 volumes, each 208-335 pages. Table 1 —
"Distribution of Libyan and Non-Libyan Households and Individuals by Mahalla" —
gives, for every mahalla (locality), the number of households and the resident
population split by nationality of the household and nationality of the
individual. It is the finest geographic breakdown Libya's last full enumeration
published.

Four properties of the source shape the approach:

  * The text is typeset in Arabic presentation forms in visual order, so it is
    converted to logical order by `arabic_text.to_logical` before anything else.
  * Thousands are separated by a space and the separator is inconsistent
    ("10 759" and "10046" both occur), so the text stream cannot be tokenised
    into cells. Cells are rebuilt from word coordinates.
  * A printed row can straddle two vertical bands, and figures are centred in
    their columns rather than aligned, so cells are assigned to columns by
    matching their centres against column positions learned from the page's own
    unambiguous rows. A column left blank in the source then shows up as a
    missing cell instead of silently shifting every figure to its right.
  * Every row carries six accounting identities. They are used to *find*
    Table 1 — page numbers and captions differ between volumes — then to fill
    blanks that the source's own arithmetic determines, and finally to validate.

Every volume also reprints Table 3, a national summary giving each shabiya's
area, population and density. It is extracted separately: it supplies the
canonical shabiya names (volume titles do not always use them), the areas, and
an independent check on each volume's own total.

Outputs:
  bsc_census_2006_mahalla.csv   one row per mahalla
  bsc_census_2006_shabiya.csv   one row per shabiya, with area and density
  bsc_census_2006_checks.csv    every identity failure and reconciliation
"""

import csv
import json
import re
import statistics
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import is_arabic, normalise_name, to_logical  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "bsc"
OUT = ROOT / "data" / "processed"

# Columns as printed, right to left. Each of the three blocks runs
# households, Libyans, non-Libyans, total.
COLUMNS = [
    "libyan_hh_households", "libyan_hh_libyans",
    "libyan_hh_non_libyans", "libyan_hh_persons",
    "non_libyan_hh_households", "non_libyan_hh_libyans",
    "non_libyan_hh_non_libyans", "non_libyan_hh_persons",
    "households", "libyans", "non_libyans", "persons",
]

IDENTITIES = [
    ("libyan_hh_persons", ["libyan_hh_libyans", "libyan_hh_non_libyans"]),
    ("non_libyan_hh_persons", ["non_libyan_hh_libyans", "non_libyan_hh_non_libyans"]),
    ("households", ["libyan_hh_households", "non_libyan_hh_households"]),
    ("libyans", ["libyan_hh_libyans", "non_libyan_hh_libyans"]),
    ("non_libyans", ["libyan_hh_non_libyans", "non_libyan_hh_non_libyans"]),
    ("persons", ["libyan_hh_persons", "non_libyan_hh_persons"]),
]

TOTAL_LABELS = {"المجموع", "الاجمالي", "الإجمالي", "المجموع الكلي", "الجملة"}

# The 22 shabiyat of the 2006 census, keyed by the name Table 3 prints. Romanised
# forms follow the spellings in common use for Libyan first-level units; the
# Arabic remains authoritative.
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

NUMERIC = re.compile(r"^\d[\d\s ]*$")
TITLE_STRIP = re.compile(r"نتائج|تعداد|العام|لسكان|مدينة|المنطقة|لسنة|2006\s*م?|م$")


def shabiya_name(title):
    return normalise_name(TITLE_STRIP.sub(" ", title))


def as_int(cell_text):
    text = to_logical(cell_text).replace(" ", " ").strip()
    if not NUMERIC.match(text):
        return None
    return int(re.sub(r"\s", "", text))


def page_bands(page, cell_gap=8.0, row_gap=6.0):
    """Group words into rows, then into cells, reading right to left.

    A printed row spans a couple of points because figures and Arabic sit on
    different baselines, while the row pitch is around 12 points, so a vertical
    gap wider than `row_gap` starts a new row.

    Returns a list of rows, each a list of (text, centre_x) cells ordered right
    to left.
    """
    words = sorted(page.extract_words(), key=lambda w: w["top"])
    if not words:
        return []

    bands, current = [], [words[0]]
    for previous, word in zip(words, words[1:]):
        if word["top"] - previous["top"] > row_gap:
            bands.append(current)
            current = [word]
        else:
            current.append(word)
    bands.append(current)

    rows = []
    for band in bands:
        ordered = sorted(band, key=lambda w: -w["x0"])
        groups, current = [], [ordered[0]]
        for previous, word in zip(ordered, ordered[1:]):
            # Reading right to left, the gap is the previous word's left edge
            # minus this word's right edge.
            if previous["x0"] - word["x1"] > cell_gap:
                groups.append(current)
                current = [word]
            else:
                current.append(word)
        groups.append(current)
        rows.append([(" ".join(w["text"] for w in reversed(g)),
                      (min(w["x0"] for w in g) + max(w["x1"] for w in g)) / 2)
                     for g in groups])
    return rows


def merge_orphan_labels(rows):
    """Reunite a total row whose label is printed on a line of its own.

    Several volumes set "المجموع" below its figures rather than beside them,
    leaving a band of figures with no name next to a band holding only a label.
    """
    out = [list(r) for r in rows]
    for i, cells in enumerate(out):
        if not cells or any(is_arabic(to_logical(t)) for t, _ in cells):
            continue
        if not all(as_int(t) is not None for t, _ in cells):
            continue
        for j in (i + 1, i - 1):
            if not 0 <= j < len(out) or len(out[j]) != 1:
                continue
            label = to_logical(out[j][0][0])
            if normalise_name(label) in TOTAL_LABELS:
                out[i] = [out[j][0]] + cells
                out[j] = []
                break
    return [r for r in out if r]


def split_row(cells):
    """Split a row into (name, [(value, centre)]) or None if it is not a data row."""
    if not cells:
        return None
    name_text, _ = cells[0]
    name = to_logical(name_text)
    if not is_arabic(name):
        return None
    values = []
    for text, centre in cells[1:]:
        value = as_int(text)
        if value is None:
            return None
        values.append((value, centre))
    return normalise_name(name), values


def learn_column_centres(rows):
    """Column centres, taken from the rows that already have all twelve cells."""
    complete = []
    for cells in rows:
        split = split_row(cells)
        if split and len(split[1]) == len(COLUMNS):
            complete.append([c for _, c in split[1]])
    if len(complete) < 3:
        return None
    return [statistics.median(col) for col in zip(*complete)]


def assign_columns(values, centres, tolerance):
    """Map (value, centre) pairs onto columns by position.

    Returns a dict of column to value, with columns the source left blank simply
    absent, and None if two figures compete for one column.
    """
    out = {}
    for value, centre in values:
        distances = [(abs(centre - c), i) for i, c in enumerate(centres)]
        distance, index = min(distances)
        if distance > tolerance:
            return None
        column = COLUMNS[index]
        if column in out:
            return None
        out[column] = value
    return out


def solve_blanks(values):
    """Fill cells the source left blank, where its own arithmetic determines them.

    Only fills a cell when an identity leaves exactly one unknown, and never
    overwrites a printed figure. Returns the number of cells filled.
    """
    filled = 0
    changed = True
    while changed:
        changed = False
        for total, parts in IDENTITIES:
            members = [total] + parts
            missing = [m for m in members if m not in values]
            if len(missing) != 1:
                continue
            unknown = missing[0]
            if unknown == total:
                values[total] = sum(values[p] for p in parts)
            else:
                others = [p for p in parts if p != unknown]
                values[unknown] = values[total] - sum(values[o] for o in others)
            filled += 1
            changed = True
    return filled


def row_failures(values):
    return [total for total, parts in IDENTITIES
            if any(m not in values for m in [total] + parts)
            or values[total] != sum(values[p] for p in parts)]


# Table 3 columns as printed, right to left.
T3_COLUMNS = ["area_km2", "area_pct", "libyans", "libyans_pct",
              "libyan_density_per_km2", "persons", "persons_pct",
              "density_per_km2"]
T3_INTEGER = {"area_km2", "libyans", "persons"}


def parse_table3(page):
    """Return {shabiya: {column: value}} if this page is Table 3, else None."""
    rows = []
    for cells in page_bands(page):
        if len(cells) != len(T3_COLUMNS) + 1:
            continue
        name = to_logical(cells[0][0])
        if not is_arabic(name):
            continue
        values = {}
        for column, (text, _) in zip(T3_COLUMNS, cells[1:]):
            token = to_logical(text).replace(" ", " ").strip()
            token = re.sub(r"\s(?=\d)", "", token) if column in T3_INTEGER else token
            try:
                values[column] = int(token) if column in T3_INTEGER else float(token)
            except ValueError:
                values = None
                break
        if values:
            rows.append((normalise_name(name), values))

    if len(rows) < 20:
        return None
    printed_total = next((v for n, v in rows if n in TOTAL_LABELS), None)
    body = {n: v for n, v in rows if n not in TOTAL_LABELS}
    if printed_total is None or len(body) < 20:
        return None
    # The shabiya rows must add up to the printed national row.
    for column in T3_INTEGER:
        if sum(v[column] for v in body.values()) != printed_total[column]:
            return None
    return body


def scan_table3(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:30]:
            table = parse_table3(page)
            if table:
                return table
    return None


def scan_volume(path):
    """Find Table 1 and return (mahalla rows, printed total rows, pages used)."""
    mahallas, totals, pages_used = [], [], []
    with pdfplumber.open(path) as pdf:
        # Table 1 sits at the front of every volume; 30 pages is ample margin.
        for index, page in enumerate(pdf.pages[:30]):
            rows = merge_orphan_labels(page_bands(page))
            centres = learn_column_centres(rows)
            if centres is None:
                continue
            spacing = min(abs(a - b) for a, b in zip(centres, centres[1:]))
            tolerance = spacing / 2

            parsed = []
            for cells in rows:
                split = split_row(cells)
                if split is None:
                    continue
                name, values = split
                mapped = assign_columns(values, centres, tolerance)
                if mapped is None or len(mapped) < len(COLUMNS) - 3:
                    continue
                imputed = solve_blanks(mapped)
                parsed.append((name, mapped, imputed))

            if len(parsed) < 3:
                continue
            # A page is Table 1 only if its rows satisfy the identities. No other
            # table in these volumes has this column structure.
            clean = sum(1 for _, v, _ in parsed if not row_failures(v))
            if clean < 0.8 * len(parsed):
                continue

            pages_used.append(index)
            for name, values, imputed in parsed:
                record = {"mahalla_ar": name, "page": index,
                          "imputed_cells": imputed, **values}
                (totals if name in TOTAL_LABELS else mahallas).append(record)
    return mahallas, totals, pages_used


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RAW / "bsc_pdf_manifest.json").read_text())
    volumes = [d for d in manifest if "تعداد" in d["title_ar"]]
    if not volumes:
        sys.exit("No census volumes found. Run scripts/download_bsc_pdfs.py first.")
    print(f"{len(volumes)} census volumes")

    mahalla_rows, shabiya_rows, checks, warnings = [], [], [], []

    # Table 3 is reprinted in every volume. Read them all and require agreement
    # before using it as the canonical reference.
    national, disagreeing = None, []
    for doc in volumes:
        path = RAW / "pdf" / doc["local"]
        if not path.exists():
            continue
        try:
            table = scan_table3(path)
        except Exception:                              # noqa: BLE001
            continue
        if table is None:
            continue
        if national is None:
            national = table
        elif table != national:
            disagreeing.append(shabiya_name(doc["title_ar"]))
    if national is None:
        warnings.append("Table 3 not found in any volume; areas unavailable")
        national = {}
    else:
        print(f"Table 3 read from the volumes: {len(national)} shabiyat, "
              f"{sum(v['persons'] for v in national.values()):,} people"
              + (f"; {len(disagreeing)} volume(s) disagree" if disagreeing else
                 "; all volumes agree"))
        for name in disagreeing:
            checks.append({"shabiya_ar": name, "check": "table_3_agreement",
                           "result": "fail",
                           "detail": "this volume's copy of Table 3 differs"})

    # Volume titles do not always use the shabiya's formal name, so each volume
    # is matched to its Table 3 entry by its own population total.
    by_population = {v["persons"]: n for n, v in national.items()}

    for doc in sorted(volumes, key=lambda d: d["title_ar"]):
        path = RAW / "pdf" / doc["local"]
        if not path.exists():
            warnings.append(f"{doc['title_ar'][:40]}: file missing")
            continue
        shabiya = shabiya_name(doc["title_ar"])

        try:
            mahallas, totals, pages = scan_volume(path)
        except Exception as exc:                       # noqa: BLE001
            warnings.append(f"{shabiya}: unreadable ({type(exc).__name__}: {exc})")
            continue

        if not mahallas:
            warnings.append(f"{shabiya}: Table 1 not found in the first 30 pages")
            checks.append({"shabiya_ar": shabiya, "check": "table_1_located",
                           "result": "fail", "detail": "no qualifying page"})
            print(f"  {shabiya:22s} TABLE 1 NOT FOUND")
            continue

        bad = 0
        for row in mahallas:
            failures = row_failures(row)
            row["identity_failures"] = len(failures)
            if failures:
                bad += 1
                implied = {}
                for total, parts in IDENTITIES:
                    if total in failures and all(p in row for p in parts):
                        implied[total] = sum(row[p] for p in parts)
                checks.append({
                    "shabiya_ar": shabiya, "check": "row_identity", "result": "fail",
                    "detail": f"{row['mahalla_ar']} (page {row['page']}): "
                              + "; ".join(f"{k} printed {row.get(k)}, components imply "
                                          f"{v}" for k, v in implied.items())})

        # The volume prints its own total row; compare it with the sum of the
        # mahallas rather than trusting either on its own.
        result, detail = "missing", "no printed total row"
        if totals:
            printed = totals[0]
            diffs = {c: sum(r.get(c, 0) for r in mahallas) - printed.get(c, 0)
                     for c in COLUMNS
                     if sum(r.get(c, 0) for r in mahallas) != printed.get(c, 0)}
            result = "ok" if not diffs else "fail"
            detail = "" if not diffs else "; ".join(f"{k} off by {v:+d}"
                                                    for k, v in diffs.items())
            canonical = by_population.get(printed.get("persons"))
            reference = national.get(canonical, {})
            shabiya_rows.append({
                "shabiya_ar": canonical or shabiya,
                "shabiya_en": SHABIYA_EN.get(canonical or shabiya, ""),
                "volume_title_ar": shabiya,
                "mahalla_count": len(mahallas),
                **{c: printed.get(c) for c in COLUMNS},
                "area_km2": reference.get("area_km2"),
                "density_per_km2": reference.get("density_per_km2"),
                "source_document": doc["original_name"],
                "source_sha256": doc["sha256"]})
            checks.append({
                "shabiya_ar": canonical or shabiya, "check": "volume_total_vs_table_3",
                "result": "ok" if canonical else "fail",
                "detail": "" if canonical else
                          f"population {printed.get('persons')} matches no Table 3 row"})
            if canonical and reference.get("libyans") != printed.get("libyans"):
                checks.append({
                    "shabiya_ar": canonical, "check": "volume_libyans_vs_table_3",
                    "result": "fail",
                    "detail": f"volume {printed.get('libyans')}, "
                              f"Table 3 {reference.get('libyans')}"})
        checks.append({"shabiya_ar": shabiya, "check": "printed_total_vs_sum",
                       "result": result, "detail": detail})

        canonical = by_population.get(totals[0].get("persons")) if totals else None
        for position, row in enumerate(mahallas, start=1):
            row["shabiya_ar"] = canonical or shabiya
            row["shabiya_en"] = SHABIYA_EN.get(canonical or shabiya, "")
            # Mahalla names repeat within a shabiya, so the printed order gives
            # the stable key rather than the name.
            row["mahalla_id"] = f"{SHABIYA_EN.get(canonical or shabiya, 'NA')}-{position:03d}"
            row["source_document"] = doc["original_name"]
            row["source_sha256"] = doc["sha256"]
        mahalla_rows.extend(mahallas)

        imputed = sum(r["imputed_cells"] for r in mahallas)
        notes = []
        if bad:
            notes.append(f"{bad} row(s) failing identities")
        if imputed:
            notes.append(f"{imputed} blank cell(s) solved")
        print(f"  {shabiya:22s} {len(mahallas):4d} mahallas  pages {pages}"
              f"  total row {result}" + ("  " + ", ".join(notes) if notes else ""))

    fields = (["mahalla_id", "shabiya_ar", "shabiya_en", "mahalla_ar"] + COLUMNS
              + ["identity_failures", "imputed_cells", "page",
                 "source_document", "source_sha256"])
    with (OUT / "bsc_census_2006_mahalla.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(mahalla_rows)

    sfields = (["shabiya_ar", "shabiya_en", "volume_title_ar", "mahalla_count"] + COLUMNS
               + ["area_km2", "density_per_km2", "source_document", "source_sha256"])
    with (OUT / "bsc_census_2006_shabiya.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=sfields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(shabiya_rows)

    with (OUT / "bsc_census_2006_checks.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["shabiya_ar", "check", "result", "detail"])
        writer.writeheader()
        writer.writerows(checks)

    shabiyat = len({r["shabiya_ar"] for r in mahalla_rows})
    print(f"\nmahallas {len(mahalla_rows)} across {shabiyat} shabiyat")
    print(f"population, summed from mahallas : "
          f"{sum(r.get('persons', 0) for r in mahalla_rows):,}")
    if shabiya_rows:
        print(f"population, printed shabiya totals: "
              f"{sum(r.get('persons') or 0 for r in shabiya_rows):,}")
    print("published 2006 census total       : 5,657,692")
    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print("  " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
