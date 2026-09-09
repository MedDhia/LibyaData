#!/usr/bin/env python3
"""
Extract commercial banks' uses of foreign exchange from CBL releases.

Source: https://cbl.gov.ly/en/uses-of-foreign-exch/

Each release is a cumulative year-to-date report covering 1 January to a stated
end date, and contains:

  * a ranking of banks by total foreign exchange purchased, with the same
    figures for the equivalent period of the prior year;
  * a breakdown by bank and purpose (letters of credit, miscellaneous
    transfers, personal purposes, merchants' cards);
  * appendices listing every accepted letter-of-credit coverage request by
    beneficiary firm, by goods or services category, by country of origin, and
    by country of beneficiary.

Because releases are cumulative, the panel is indexed by period_end. Successive
releases within a year differ by the flow over the intervening months.

All values are US dollars as published.
"""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "cbl_fx"
OUT = ROOT / "data" / "processed"

# "rank  name  value"
ENTRY = re.compile(r"^(\d{1,5})\s+(.+?)\s+([\d,]{3,})$")
# "rank  value" -- the wrapped-name layout puts the name on the lines either side
ENTRY_SPLIT = re.compile(r"^(\d{1,5})\s+([\d,]{3,})$")
PERIOD = re.compile(r"to\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})")
MONEY = re.compile(r"^-?[\d,]+$")

# Appendix sections are identified by the line that follows "Accepted Coverage
# Requests" on a section's first page. Releases differ in which appendices they
# carry, in what order, and whether they split private from public sector, so
# sections are detected from the printed label rather than assumed by position.
# (heading variants, slug, label column). Headings are not stable across
# releases, so every observed spelling is listed rather than matched loosely.
APPENDIX_KINDS = [
    (("List of all Companies and Factories", "List of all entities",
      "List of all Companies"), "beneficiary_firm", "firm_name"),
    (("According to Goods or Services",), "goods_or_service", "category"),
    (("According to Country of Origin",), "country_of_origin", "country"),
    (("According to Country of Beneficiary", "According to Beneficiary Country",
      "According to the beneficiary country"), "country_of_beneficiary", "country"),
    (("Foreign Transfers", "Foreign Transfers - Salaries"),
     "foreign_transfers", "category"),
]


ORDER_TOKEN = re.compile(r"^-?\s*\d{1,3}$")


def to_num(tok):
    """Parse a printed figure. "-" marks a cell with no data, not a negative."""
    tok = (tok or "").strip().replace(",", "").replace("%", "").strip()
    if tok in ("", "-", "--", "0.0-"):
        return None
    neg = tok.endswith("-")            # trailing minus is an RTL artifact
    tok = tok.rstrip("-").strip()
    if tok == "":
        return None
    try:
        val = float(tok)
    except ValueError:
        return None
    return -val if neg else val


def period_end(pdf):
    """Report end date, read from the cover text rather than the filename."""
    for page in pdf.pages[:14]:
        m = PERIOD.search((page.extract_text() or "").replace("–", "-"))
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y}-{mo:02d}-{d:02d}"
    return None


def parse_ranking(page, period, prior_year, this_year, rows):
    """Bank ranking table: order and value for the prior and current year."""
    for table in page.extract_tables():
        for raw in table:
            cells = [(c or "").replace("\n", " ").strip() for c in raw]
            cells = [c for c in cells if c != ""]
            if len(cells) < 7:
                continue
            name = cells[0]
            if not name or name.lower() in ("bank", "order") or name.lower().startswith("total"):
                continue
            nums = cells[1:]
            try:
                o_prev, v_prev, s_prev, o_cur, v_cur, s_cur = nums[:6]
            except ValueError:
                continue
            rows.append({
                "period_end": period, "bank": name,
                "year": prior_year, "rank": to_num(o_prev),
                "value_usd": to_num(v_prev), "market_share_pct": to_num(s_prev),
            })
            rows.append({
                "period_end": period, "bank": name,
                "year": this_year, "rank": to_num(o_cur),
                "value_usd": to_num(v_cur), "market_share_pct": to_num(s_cur),
            })


def parse_by_purpose(page, period, prior_year, this_year, rows):
    """Bank x purpose table: prior-year and current-year columns per purpose.

    Row layout varies: the order number is sometimes blank, and bank names wrap
    across lines. Rows are therefore read as "first non-numeric cell is the bank
    name, the eight numeric cells that follow are the figures".
    """
    purposes = ["letters_of_credit", "miscellaneous_transfers",
                "personal_purposes", "merchants_cards"]
    for table in page.extract_tables():
        for raw in table:
            cells = [(c or "").replace("\n", " ").strip() for c in raw]
            cells = [c for c in cells if c != ""]
            if len(cells) < 9:
                continue

            # The bank name is the first cell that is neither a figure, an order
            # number (printed variously as "-9" or "- 10"), nor the "-"
            # placeholder used where a bank had no activity in the prior year.
            name_idx = next(
                (i for i, c in enumerate(cells)
                 if to_num(c) is None and not ORDER_TOKEN.match(c) and c != "-"),
                None)
            if name_idx is None:
                continue
            name = cells[name_idx]
            # Exact match only: real bank names begin with "Bank of ...".
            if (name.casefold() in ("bank", "order", "grand total")
                    or name.casefold().startswith("total")):
                continue

            value_cells = cells[name_idx + 1:name_idx + 9]
            if len(value_cells) != 8:
                continue
            # Positions are kept: "-" becomes a missing value, not a dropped
            # column, so prior-year gaps do not shift the purpose mapping.
            nums = [to_num(c) for c in value_cells]
            if all(n is None for n in nums):
                continue

            for i, purpose in enumerate(purposes):
                rows.append({"period_end": period, "bank": name, "purpose": purpose,
                             "year": prior_year, "value_usd": nums[2 * i]})
                rows.append({"period_end": period, "bank": name, "purpose": purpose,
                             "year": this_year, "value_usd": nums[2 * i + 1]})


def parse_appendix_lines(lines):
    """Yield (rank, label, value) handling the wrapped-name layout.

    A long label wraps so that the printed order becomes:
        <label part 1>
        <rank> <value>
        <label part 2>
    """
    out = []
    for i, line in enumerate(lines):
        m = ENTRY.match(line)
        if m:
            out.append((int(m.group(1)), m.group(2).strip(), to_num(m.group(3))))
            continue
        m = ENTRY_SPLIT.match(line)
        if m:
            before = lines[i - 1].strip() if i > 0 and not ENTRY.match(lines[i - 1]) else ""
            after = lines[i + 1].strip() if i + 1 < len(lines) and not ENTRY.match(lines[i + 1]) \
                and not ENTRY_SPLIT.match(lines[i + 1]) else ""
            label = " ".join(p for p in (before, after) if p).strip()
            if label:
                out.append((int(m.group(1)), label, to_num(m.group(2))))
    return out


def section_header(lines):
    """Return the appendix heading on a section's first page, if this is one.

    "Accepted Coverage Requests" also appears in the narrative pages, so a page
    only counts as a section start when it also carries the table's own column
    header line, which every appendix prints as "Order." followed by the label
    and value column names.
    """
    if not any(l.startswith("Order.") for l in lines[:8]):
        return None
    for i, line in enumerate(lines[:4]):
        if line.startswith("Accepted Coverage Requests") and i + 1 < len(lines):
            return lines[i + 1].strip()
        if line.startswith("Foreign Transfers"):
            return line.strip()
    return None


def classify_section(header):
    """Map a printed heading to (slug, label field, sector). None if unknown."""
    plain = header.split("-")[0].strip().casefold()
    low = header.casefold()
    sector = "unspecified"
    if "private sector" in low:
        sector = "private"
    elif "public sector" in low:
        sector = "public"
    for variants, slug, field in APPENDIX_KINDS:
        if any(plain.startswith(v.casefold()) for v in variants):
            return slug, field, sector
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs in {RAW}.")

    ranking, by_purpose = [], []
    appendix = {slug: [] for _, slug, _ in APPENDIX_KINDS}
    manifest, warnings = [], []

    for path in pdfs:
        with pdfplumber.open(path) as pdf:
            period = period_end(pdf)
            if period is None:
                warnings.append(f"{path.name}: could not read the report period; skipped")
                continue
            this_year = int(period[:4])
            prior_year = this_year - 1

            current = None        # active appendix slug
            label_field = None
            current_meta = {}
            section_seq = {}      # counts repeats of the same heading in a release
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = [l.strip() for l in text.split("\n") if l.strip()]

                if "Ranking of banks according to" in text:
                    parse_ranking(page, period, prior_year, this_year, ranking)
                    continue
                if "according to the purpose" in text:
                    parse_by_purpose(page, period, prior_year, this_year, by_purpose)
                    continue

                header = section_header(lines)
                if header is not None:
                    kind = classify_section(header)
                    if kind is None:
                        warnings.append(
                            f"{path.name} p{page.page_number}: unrecognised appendix "
                            f"heading {header!r}; pages skipped")
                        current = label_field = None
                        continue
                    slug, label_field, sector = kind
                    key = (slug, sector)
                    section_seq[key] = section_seq.get(key, 0) + 1
                    if section_seq[key] > 1:
                        warnings.append(
                            f"{path.name} p{page.page_number}: heading {header!r} "
                            f"repeats within this release; rows tagged section_seq="
                            f"{section_seq[key]} and may be a mislabelled table")
                    current = slug
                    current_meta = {"source_section_label": header,
                                    "sector": sector,
                                    "section_seq": section_seq[key]}

                if current is None:
                    continue
                for rank, label, value in parse_appendix_lines(lines):
                    if value is None:
                        continue
                    row = {"period_end": period, "rank": rank,
                           label_field: label, "value_usd": value}
                    row.update(current_meta)
                    appendix[current].append(row)

        manifest.append({
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
            "period_end": period,
        })

    def write(name, rows, fields):
        if not rows:
            warnings.append(f"{name}: no rows extracted")
            return
        # Within a release each rank appears once; drop layout-induced repeats.
        seen, out_rows = set(), []
        for r in rows:
            key = tuple(r.get(f) for f in fields)
            if key in seen:
                continue
            seen.add(key)
            out_rows.append(r)
        path = OUT / f"{name}.csv"
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(out_rows)
        periods = sorted({r["period_end"] for r in out_rows})
        print(f"{path.name:44s} {len(out_rows):6d} rows  "
              f"{len(periods)} release(s) {periods[0]} .. {periods[-1]}")

    write("cbl_fx_by_bank", ranking,
          ["period_end", "year", "bank", "rank", "value_usd", "market_share_pct"])
    write("cbl_fx_by_bank_purpose", by_purpose,
          ["period_end", "year", "bank", "purpose", "value_usd"])
    meta = ["sector", "section_seq", "source_section_label"]
    write("cbl_fx_lc_by_firm", appendix["beneficiary_firm"],
          ["period_end", "rank", "firm_name", "value_usd"] + meta)
    write("cbl_fx_lc_by_goods", appendix["goods_or_service"],
          ["period_end", "rank", "category", "value_usd"] + meta)
    write("cbl_fx_lc_by_country_origin", appendix["country_of_origin"],
          ["period_end", "rank", "country", "value_usd"] + meta)
    write("cbl_fx_lc_by_country_beneficiary", appendix["country_of_beneficiary"],
          ["period_end", "rank", "country", "value_usd"] + meta)
    write("cbl_fx_foreign_transfers", appendix["foreign_transfers"],
          ["period_end", "rank", "category", "value_usd"] + meta)

    (OUT / "cbl_fx_source_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print("  " + w, file=sys.stderr)


if __name__ == "__main__":
    main()
