#!/usr/bin/env python3
"""
Extract monthly monetary statistics from Central Bank of Libya PDF releases.

Source: https://cbl.gov.ly/en/monetary-and-banking/
Covers five tables published as one-page-per-year layouts, 2004 to present.

Each page carries a table title, a bare four-digit year line, and twelve month
rows. Months not yet published appear as a bare month name with no figures and
are skipped rather than written as zero.

Output: tidy CSVs in data/processed/, one wide file per table plus a combined
long file. All values are millions of Libyan dinars as published; no currency
conversion or rebasing is applied.
"""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "cbl"
OUT = ROOT / "data" / "processed"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    # The CBL layout truncates some month labels; these are the observed variants.
    "decembe": 12, "septembe": 9, "novembe": 11, "octobe": 10,
}

# Column names in the left-to-right order they appear in each table.
# Derived by reading the printed column headers on the first page of each table.
SCHEMAS = {
    "MONEY SUPPLY": [
        "currency_in_circulation",
        "demand_deposits",
        "money_m1",
        "time_deposits",
        "saving_deposits",
        "quasi_money",
        "money_supply_m2",
    ],
    "FACTORS AFFECTING MONEY SUPPLY": [
        "nfa_central_bank",
        "nfa_commercial_banks",
        "nfa_total",
        "net_claims_on_treasury",
        "claims_on_other_sectors",
        "other_items_net",
        "nda_total",
        "money_supply_m2",
    ],
    "MONETARY BASE": [
        "currency_in_circulation",
        "cash_in_vault",
        "deposits_with_central_bank",
        "bank_reserves_total",
        "public_enterprise_demand_deposits",
        "monetary_base",
    ],
    "FACTORS AFFECTING MONETARY BASE": [
        "net_foreign_assets",
        "net_claims_on_treasury",
        "claims_on_other_sectors",
        "claims_on_commercial_banks",
        "other_items_net",
        "nda_total",
        "monetary_base",
    ],
    "REQUIRED RESERVES FOR COMMERCIAL BANKS": [
        "demand_deposits",
        "time_deposits",
        "deposits_total",
        "reserve_requirements",
        "excess_reserves",
    ],
}

SLUGS = {
    "MONEY SUPPLY": "cbl_money_supply",
    "FACTORS AFFECTING MONEY SUPPLY": "cbl_money_supply_factors",
    "MONETARY BASE": "cbl_monetary_base",
    "FACTORS AFFECTING MONETARY BASE": "cbl_monetary_base_factors",
    "REQUIRED RESERVES FOR COMMERCIAL BANKS": "cbl_required_reserves",
}

# A trailing minus (e.g. "85899.1-") is a right-to-left rendering artifact in the
# source PDFs and denotes a negative value, as does a leading minus or parentheses.
NUM = re.compile(r"-?\(?\d[\d,]*\.?\d*\)?-?")
YEAR = re.compile(r"^(19|20)\d{2}$")


def parse_number(tok):
    """Convert a printed figure to float. Parentheses denote negatives."""
    tok = tok.strip()
    neg = (tok.startswith("(") and tok.endswith(")")) or tok.endswith("-")
    tok = tok.rstrip("-").strip("()").replace(",", "")
    neg = neg or tok.startswith("-")
    tok = tok.lstrip("-")
    if tok in ("", "-", "."):
        return None
    try:
        val = float(tok)
    except ValueError:
        return None
    return -val if neg else val


def month_end(year, month):
    """Last calendar day of the month, as an ISO date string."""
    if month == 12:
        return f"{year}-12-31"
    days = [31, 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return f"{year}-{month:02d}-{days[month - 1]:02d}"


def parse_page(text, warnings, source_file, page_no):
    """Return (table_title, year, [row dicts]) for one page, or None."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return None

    title = next((l for l in lines if l.upper().strip() in SCHEMAS), None)
    if title is None:
        return None
    title = title.upper().strip()
    cols = SCHEMAS[title]

    year = None
    rows = []
    for line in lines:
        if YEAR.match(line):
            year = int(line)
            continue
        first = line.split()[0].lower().strip(".")
        if first not in MONTHS:
            continue
        if year is None:
            warnings.append(f"{source_file} p{page_no}: month row before any year line")
            continue
        month = MONTHS[first]
        rest = line[len(line.split()[0]):]
        vals = [parse_number(t) for t in NUM.findall(rest)]
        vals = [v for v in vals if v is not None]
        if not vals:
            # Month not yet published. Omit rather than record as zero.
            continue
        if len(vals) != len(cols):
            warnings.append(
                f"{source_file} p{page_no} {year}-{month:02d} in '{title}': "
                f"expected {len(cols)} figures, read {len(vals)} -- row dropped"
            )
            continue
        row = {"date": month_end(year, month), "year": year, "month": month}
        row.update(dict(zip(cols, vals)))
        rows.append(row)
    return title, year, rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs in {RAW}. Run scripts/download_cbl.sh first.")

    tables = {}
    warnings = []
    manifest = []

    for pdf_path in pdfs:
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        found = set()
        with pdfplumber.open(pdf_path) as pdf:
            for page_no, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                parsed = parse_page(text, warnings, pdf_path.name, page_no)
                if parsed is None:
                    continue
                title, _, rows = parsed
                found.add(title)
                tables.setdefault(title, []).extend(rows)
        if found:
            manifest.append({
                "file": pdf_path.name,
                "sha256": digest,
                "bytes": pdf_path.stat().st_size,
                "tables": sorted(found),
            })

    long_rows = []
    for title, rows in sorted(tables.items()):
        cols = SCHEMAS[title]
        rows.sort(key=lambda r: r["date"])
        # Guard against a table appearing in more than one source PDF.
        seen, deduped = set(), []
        for r in rows:
            if r["date"] in seen:
                continue
            seen.add(r["date"])
            deduped.append(r)

        slug = SLUGS[title]
        path = OUT / f"{slug}.csv"
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["date", "year", "month"] + cols)
            w.writeheader()
            w.writerows(deduped)
        print(f"{path.name:38s} {len(deduped):5d} months  "
              f"{deduped[0]['date']} .. {deduped[-1]['date']}")

        for r in deduped:
            for c in cols:
                long_rows.append({
                    "date": r["date"], "year": r["year"], "month": r["month"],
                    "table": slug, "variable": c, "value_million_lyd": r[c],
                })

    long_path = OUT / "cbl_monetary_long.csv"
    with long_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "date", "year", "month", "table", "variable", "value_million_lyd"])
        w.writeheader()
        w.writerows(sorted(long_rows, key=lambda r: (r["table"], r["date"], r["variable"])))
    print(f"{long_path.name:38s} {len(long_rows):5d} observations")

    (OUT / "cbl_source_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if warnings:
        print(f"\n{len(warnings)} extraction warning(s):", file=sys.stderr)
        for w in warnings:
            print("  " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
