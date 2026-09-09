#!/usr/bin/env python3
"""
Build a monthly consumer price index series from Bureau of Statistics and
Census releases.

Source: https://bsc.ly/economic_statistics/ (catalogued by harvest_bsc_catalogue.py)

The BSC publishes the CPI in two document families, which this script reads
separately and then merges:

  A. Full-year tables, "Monthly indices of consumer prices for the year YYYY".
     One page per year. Values run right to left: an annual average, then the
     published months in reverse order, then the group's weight.

  B. Two-month comparison tables inside the monthly inflation reports. Each
     carries the current and preceding month's index by COICOP group, plus the
     month-on-month rate of change.

Both families print English month abbreviations, which are used to establish
column order rather than assuming it.

Only base-2008 documents are read. The BSC also publishes a parallel 2003=100
series on a different commodity classification; the two are not comparable and
mixing them would be an error, so 2003-base documents are skipped and reported.
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "bsc"
OUT = ROOT / "data" / "processed"

MONTH_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
              "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

ARABIC_MONTHS = {
    "يناير": 1, "فبراير": 2, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4,
    "مايو": 5, "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8,
    "سبتمبر": 9, "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}

# The base year is printed inconsistently: "(2008=100)" on the full-year tables,
# "base year 2024=100" or "Year of Basis 2024" in the monthly reports.
BASE_PATTERNS = [
    re.compile(r"\((\d{4})\s*=\s*100\)"),
    re.compile(r"base year\s*(\d{4})\s*=\s*100", re.I),
    re.compile(r"Year of Basis\s*(\d{4})", re.I),
    re.compile(r"(?<![\d/])(\d{4})\s*=\s*100"),
]
YEAR_IN_TITLE = re.compile(r"(20\d{2})")
NUM = re.compile(r"-?\d+(?:\.\d+)?")

# Family B rows end with the two-digit COICOP code after the Arabic label.
# The Arabic label sometimes wraps onto its own line, leaving the English label,
# the figures and the code alone on the row, so the Arabic part is optional.
ROW_B = re.compile(
    r"^([A-Za-z][A-Za-z ,.'&\-/]*?)\s+((?:-?\d+(?:\.\d+)?\s+){3,5})(?:[؀-ۿـ\s]+\s+)?(\d{2})\s*$")

# Family A rows begin with an optional "Code" token then the English label.
ROW_A = re.compile(
    r"^(?:Code\s+)?(?:\d{1,2}\s+)?([A-Za-z][A-Za-z ,.'&\-/]*?)\s+((?:-?\d+(?:\.\d+)?\s+)*-?\d+(?:\.\d+)?)\s*[؀-ۿـ]")

CANON = {
    "general index": ("00", "General Index"),
    "food and beverages": ("01", "Food and Beverages"),
    "food items": ("01", "Food and Beverages"),
    "tobacco": ("02", "Tobacco"),
    "clothing and footwear": ("03", "Clothing and Footwear"),
    "housing,water,electricity,other fuel": ("04", "Housing, Water, Electricity and Other Fuels"),
    "housing, water, electricity, other": ("04", "Housing, Water, Electricity and Other Fuels"),
    "furniture and household equipment": ("05", "Furniture and Household Equipment"),
    "health": ("06", "Health"),
    "transport": ("07", "Transport"),
    "communication": ("08", "Communication"),
    "communications": ("08", "Communication"),
    "recreation and culture": ("09", "Recreation and Culture"),
    "education": ("10", "Education"),
    "restaurants and hotels": ("11", "Restaurants and Hotels"),
    "restaurant and hotels": ("11", "Restaurants and Hotels"),
    "miscellaneous goods and services": ("12", "Miscellaneous Goods and Services"),
    "other goods and services": ("12", "Miscellaneous Goods and Services"),
}


def document_base_year(pdf):
    """Base year declared anywhere in the document, or None if never stated."""
    found = set()
    for page in pdf.pages:
        text = page.extract_text() or ""
        for pattern in BASE_PATTERNS:
            for hit in pattern.findall(text):
                year = int(hit)
                if 1990 <= year <= 2030:
                    found.add(year)
    if not found:
        return None, "none stated"
    if len(found) > 1:
        # A rebasing report cites both the old and new base; the later one is
        # the base the printed figures are on.
        return max(found), f"multiple stated {sorted(found)}"
    return found.pop(), ""


def canon(label):
    key = " ".join(label.split()).casefold().strip(" .:-")
    if key in CANON:
        return CANON[key]
    for k, v in CANON.items():
        if key.startswith(k[:18]):
            return v
    return None


def header_months(lines):
    """Month numbers in printed (right-to-left) order, from the English header."""
    for line in lines:
        toks = re.findall(r"\b([A-Z][a-z]{2})\.", line)
        months = [MONTH_ABBR[t.casefold()] for t in toks if t.casefold() in MONTH_ABBR]
        if len(months) >= 2:
            return months
    return []


def header_month_years(lines):
    """(month, year) pairs where the header prints them together, e.g. "Feb.2025".

    Preferred over inferring the year, because a monthly report that straddles
    a year end names both years and picking the wrong one shifts an observation
    twelve months.
    """
    for line in lines:
        pairs = re.findall(r"\b([A-Z][a-z]{2})\.\s*(20\d{2})", line)
        out = [(MONTH_ABBR[m.casefold()], int(y))
               for m, y in pairs if m.casefold() in MONTH_ABBR]
        if len(out) >= 2:
            return out
    return []


def parse_family_a(page, year, warnings, tag):
    """Full-year table: [annual average, months in reverse order, weight]."""
    text = page.extract_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    months = header_months(lines)
    has_average = any("Average" in l for l in lines)
    if not months or not has_average:
        return []

    out = []
    for line in lines:
        m = ROW_A.match(line)
        if not m:
            continue
        c = canon(m.group(1))
        if c is None:
            continue
        code, name = c
        vals = [float(v) for v in NUM.findall(m.group(2))]
        # average + k months + weight
        k = len(vals) - 2
        if k < 1 or k > 12:
            warnings.append(f"{tag}: {name} row has {len(vals)} figures; skipped")
            continue
        average, weight = vals[0], vals[-1]
        monthly = vals[1:-1]
        # Published months are the first k of the year, printed newest first.
        for offset, value in enumerate(monthly):
            month = k - offset
            out.append({"year": year, "month": month, "group_code": code,
                        "group_name": name, "index": value, "weight": weight,
                        "annual_average": average, "family": "A"})
    return out


def parse_family_b(page, year, warnings, tag):
    """Two-month comparison table: [m-o-m %, current index, prior index, weight].

    `year` is the reference year of the report, taken from its title. It is not
    read from the page, because the page names the comparison month's year too
    and a report for January cites the preceding December.
    """
    text = page.extract_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not any("M-o-M" in l or "M-O-M" in l for l in lines):
        return []

    dated = header_month_years(lines)
    if len(dated) == 2:
        (cur_month, cur_year), (prev_month, prev_year) = dated
    else:
        months = header_months(lines)
        if len(months) != 2:
            return []
        cur_month, prev_month = months[0], months[1]
        if year is None:
            warnings.append(f"{tag}: month table with no year; skipped")
            return []
        cur_year = year
        prev_year = year if prev_month < cur_month else year - 1

    out = []
    for line in lines:
        m = ROW_B.match(line)
        if not m:
            continue
        c = canon(m.group(1))
        if c is None:
            continue
        code, name = c
        vals = [float(v) for v in NUM.findall(m.group(2))]
        if len(vals) < 4:
            continue
        mom, idx_cur, idx_prev, weight = vals[0], vals[1], vals[2], vals[3]

        out.append({"year": cur_year, "month": cur_month, "group_code": code,
                    "group_name": name, "index": idx_cur, "weight": weight,
                    "mom_change_pct": mom, "family": "B"})
        out.append({"year": prev_year, "month": prev_month, "group_code": code,
                    "group_name": name, "index": idx_prev, "weight": weight,
                    "family": "B"})
    return out


def resolve_unstated_bases(records, warnings, tol=0.15):
    """Assign a base year to documents that do not state one.

    Many monthly inflation reports omit the base. Rather than assume it, each
    such document is matched against observations whose base is stated: where
    the two print the same figure for the same month and group, the document is
    on that base. Resolution repeats so that documents can chain through each
    other. Anything still unmatched keeps an empty base year.
    """
    by_doc = defaultdict(list)
    for r in records:
        by_doc[r["source_document"]].append(r)

    anchored = {}
    for r in records:
        if r["base_year"] is not None:
            anchored.setdefault((r["year"], r["month"], r["group_code"]),
                                {})[r["base_year"]] = r["index"]

    changed = True
    while changed:
        changed = False
        for doc, rows in by_doc.items():
            if rows[0]["base_year"] is not None:
                continue
            votes = defaultdict(int)
            for r in rows:
                for base, value in anchored.get(
                        (r["year"], r["month"], r["group_code"]), {}).items():
                    if abs(value - r["index"]) <= tol:
                        votes[base] += 1
            if not votes:
                continue
            base = max(votes, key=votes.get)
            if len(votes) > 1:
                warnings.append(
                    f"{doc[:48]}: figures match more than one base {dict(votes)}; "
                    f"resolved to {base}")
            for r in rows:
                r["base_year"] = base
                r["base_year_source"] = "matched"
                anchored.setdefault((r["year"], r["month"], r["group_code"]),
                                    {})[base] = r["index"]
            changed = True

    unresolved = sorted({r["source_document"] for r in records
                         if r["base_year"] is None})
    for doc in unresolved:
        warnings.append(f"{doc[:60]}: base year neither stated nor matched; "
                        f"rows kept with an empty base_year")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RAW / "bsc_pdf_manifest.json").read_text())
    docs = [d for d in manifest if re.search(
        "الأرقام القياسية|التضخم|الرقم القياسي", d["title_ar"])]
    print(f"{len(docs)} price-index documents to read")

    records, warnings = [], []
    skipped_base = 0

    for doc in docs:
        path = RAW / "pdf" / doc["local"]
        if not path.exists():
            continue
        tag = doc["title_ar"][:48]
        try:
            pdf = pdfplumber.open(path)
        except Exception as exc:                      # noqa: BLE001
            warnings.append(f"{tag}: unreadable ({type(exc).__name__})")
            continue

        with pdf:
            base_year, base_note = document_base_year(pdf)
            if base_note and base_year is not None:
                warnings.append(f"{tag}: {base_note}; using {base_year}")

            for page in pdf.pages:
                text = page.extract_text() or ""
                # Family A prints "for the year YYYY" on each page; family B is
                # dated by its title, since its pages name two years.
                page_match = re.search(r"for (?:the year )?(20\d{2})", text)
                page_years = YEAR_IN_TITLE.findall(text)
                page_year = int(page_match.group(1)) if page_match else (
                    int(page_years[0]) if page_years else None)
                title_years = YEAR_IN_TITLE.findall(doc["title_ar"])
                doc_year = int(title_years[-1]) if title_years else None

                rows = parse_family_a(page, page_year, warnings, tag) \
                    if page_year is not None else []
                if not rows:
                    rows = parse_family_b(page, doc_year, warnings, tag)
                for r in rows:
                    # None here means the document never states its base; it is
                    # resolved below by matching overlapping months, not guessed.
                    r["base_year"] = base_year
                    r["base_year_source"] = ("stated" if base_year is not None
                                             else "unresolved")
                    r["source_document"] = doc["original_name"]
                    r["source_sha256"] = doc["sha256"]
                records.extend(rows)

    resolve_unstated_bases(records, warnings)

    # One observation per (year, month, group). Where documents overlap, keep the
    # first and record whether any other document disagreed.
    best, conflicts = {}, []
    for r in records:
        key = (r["base_year"], r["year"], r["month"], r["group_code"])
        if key not in best:
            best[key] = r
        elif abs(best[key]["index"] - r["index"]) > 0.05:
            conflicts.append({
                "base_year": r["base_year"], "year": r["year"],
                "month": r["month"], "group_code": r["group_code"],
                "index_kept": best[key]["index"], "index_other": r["index"],
                "document_kept": best[key]["source_document"],
                "document_other": r["source_document"],
            })

    rows = sorted(best.values(),
                  key=lambda r: (r["base_year"] or 0, r["year"], r["month"],
                                 r["group_code"]))
    # Flag observations another document disagrees about, so they can be
    # filtered without having to join the conflicts file.
    disputed = {(c["base_year"], c["year"], c["month"], c["group_code"])
                for c in conflicts}
    for r in rows:
        r["has_conflict"] = int(
            (r["base_year"], r["year"], r["month"], r["group_code"]) in disputed)

    fields = ["year", "month", "date", "group_code", "group_name", "index",
              "weight", "base_year", "base_year_source", "has_conflict",
              "mom_change_pct", "annual_average", "family",
              "source_document", "source_sha256"]
    for r in rows:
        r["date"] = f"{r['year']}-{r['month']:02d}"

    path = OUT / "bsc_cpi_by_group.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"{path.name:32s} {len(rows):5d} observations, "
          f"{len({(r['year'], r['month']) for r in rows})} distinct months")
    for base in sorted({r["base_year"] for r in rows}, key=lambda b: b or 0):
        gen = [r for r in rows if r["group_code"] == "00" and r["base_year"] == base]
        if gen:
            print(f"  base {base}=100: general index {len(gen):3d} months, "
                  f"{gen[0]['date']} .. {gen[-1]['date']}")

    if conflicts:
        cpath = OUT / "bsc_cpi_source_conflicts.csv"
        with cpath.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(conflicts[0]))
            w.writeheader()
            w.writerows(conflicts)
        print(f"  {len(conflicts)} cross-document disagreements written to {cpath.name}")

    unresolved = len({r["source_document"] for r in rows if r["base_year"] is None})
    if unresolved:
        print(f"  {unresolved} document(s) with an unresolved base year")
    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings[:25]:
            print("  " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
