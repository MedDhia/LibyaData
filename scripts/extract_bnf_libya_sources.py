#!/usr/bin/env python3
"""
Code the BnF's Libya holdings, and pull out the ones that carry data.

Input is the catalogue harvest from `scripts/download_bnf_catalogue.py`.

## What the counts mean before they are coded

4,391 catalogue records name Libya or one of its provinces, and 871 of them are
digitised. Neither number is a measure of usable material. 749 records across
the set are coins in the Cabinet des Médailles, Greek drachms struck at Barka
and Teuchira, which is why "Cyrénaïque" is the largest search term in the
catalogue and why most of its digitised records are photographs of objects. The
1900-1919 band holds 338 digitised records because the Italo-Turkish war of
1911 was photographed heavily, not because anybody was counting anything.

So the records are classed by what they are, and the count that matters is the
one at the end: the records that carry numbers about Libya.

## The classes

`document_class` is read from the title and subject first and the catalogue's
own document type second, because a census is a census whether the catalogue
calls it a printed text or a serial:

  population_census, statistical_abstract, trade_returns, gazetteer,
  official_serial   the data-bearing classes, flagged `is_data_source`
  map, photograph, archive_manuscript, serial, book, other

`era` is the Libyan state the document belongs to, which is what decides who
was collecting and under what categories: ottoman to 1911, italian to 1943,
allied_administration to 1951, kingdom to 1969, jamahiriya to 2011, post_2011.

## What this finds, and the one thing to know about it

The BnF holds the first two Libyan censuses, of 1954 and 1964, and a statistical
abstract running 1958 to 1974. This repository's own census data starts in 2006,
so those three fill the gap between independence and the series it already has.
**None of them is digitised.** They are catalogue records for volumes on a shelf
in Paris, and `is_digitised` says so on every row. What is digitised is the
older material: a manuscript gazetteer of the villages of the Regency of
Tripoli, consular dispatches on the commerce of Tripoli and Benghazi in the
1820s, and 295 maps.

Outputs, under data/processed/bnf/:
  bnf_libya_records.csv    every catalogue record, coded
  bnf_libya_data.csv       the data-bearing subset, the inventory to work from
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "bnf" / "catalogue_records.json"
OUT = ROOT / "data" / "processed" / "bnf"

# Title and subject patterns, most specific first: a census report also says
# "population", and a statistical abstract of trade also says "commerce".
CLASSES = (
    # Not the bare word "census": it is in the name of the department that
    # published the statistical abstracts, and it turned four of them into
    # censuses.
    ("population_census", r"population census|recensement|censiment|dénombrement|"
                          r"missione demografica|labour force|force de travail"),
    ("statistical_abstract", r"statistical abstract|statistiq|statistic|statistica|"
                             r"annuaire statistique"),
    ("trade_returns", r"movimento commerciale|commerce de|commercio|"
                      r"mouvement (?:commercial|de la navigation)|"
                      r"rapports commerciaux|bulletin consulaire|"
                      r"annales du commerce"),
    # Only a real gazetteer. "Itinéraire" and "répertoire" were here and caught
    # GPS guides for desert tourists and a directory of North African doctors.
    ("gazetteer", r"nomenclature des (?:villes|villages)|dictionnaire géographique"),
    ("scientific_mission", r"mission scientifique|géographie humaine"),
    ("official_serial", r"bollettino|bulletin officiel|gazzetta|journal officiel|"
                        r"annuaire"),
)
DATA_CLASSES = {name for name, _ in CLASSES}

# Falling back on the catalogue's own document type.
TYPES = {
    "document cartographique": "map",
    "image fixe": "photograph",
    "manuscrit moderne ou document d'archive": "archive_manuscript",
    "publication en série imprimée": "serial",
    "texte imprimé": "book",
    "monnaie ou médaille": "coin",
    "image animée": "film",
    "enregistrement sonore": "sound",
    "partition musicale": "music",
}

# The state that was doing the counting. A document is placed by its own date,
# which for a serial is the first year of its run.
ERAS = ((1911, "ottoman"), (1943, "italian"), (1951, "allied_administration"),
        (1969, "kingdom"), (2011, "jamahiriya"), (9999, "post_2011"))

YEAR = re.compile(r"(1[45678]\d\d|1[89]\d\d|20[0-2]\d)")


def year_of(record):
    found = YEAR.search(record.get("publication_date") or "")
    return int(found.group(1)) if found else None


def era_of(year):
    if not year:
        return ""
    for edge, name in ERAS:
        if year < edge:
            return name
    return ""


def class_of(record):
    haystack = (record["title"] + " " + " ".join(record["subjects"])).lower()
    for name, pattern in CLASSES:
        if re.search(pattern, haystack):
            return name
    return TYPES.get(record["document_type"], "other")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    if not RAW.exists():
        sys.exit(f"missing {RAW}. Run scripts/download_bnf_catalogue.py first.")
    harvest = json.loads(RAW.read_text())

    rows = []
    for record in harvest["records"]:
        year = year_of(record)
        document_class = class_of(record)
        rows.append({
            "record_ark": record["record_ark"],
            "title": record["title"],
            "authors": "; ".join(record["authors"]),
            "publisher": record["publisher"],
            "publication_date": record["publication_date"],
            "year": year or "",
            "era": era_of(year),
            "document_type": record["document_type"],
            "document_class": document_class,
            "is_data_source": int(document_class in DATA_CLASSES),
            "language": record["language"],
            "subjects": "; ".join(record["subjects"]),
            "is_digitised": record["is_digitised"],
            "gallica_ark": record["gallica_ark"],
            "gallica_url": record["gallica_url"],
            "catalogue_url": record["catalogue_url"],
            "found_by": ";".join(record["found_by"]),
            "holding_institution": "Bibliothèque nationale de France",
        })

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "bnf_libya_records.csv", rows)
    data = [r for r in rows if r["is_data_source"]]
    write(OUT / "bnf_libya_data.csv", data)
    report(rows, data)


def write(path, rows):
    if not rows:
        print(f"{path.name:28s} no rows")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:28s} {len(rows):5d} rows")


def report(rows, data):
    digitised = [r for r in rows if r["is_digitised"]]
    print(f"\n{len(rows)} catalogue records, {len(digitised)} digitised")
    print("by class:      ", dict(Counter(r["document_class"]
                                          for r in rows).most_common(8)))
    print("digitised:     ", dict(Counter(r["document_class"]
                                          for r in digitised).most_common(8)))
    print("by era:        ", dict(Counter(r["era"] for r in rows if r["era"])
                                  .most_common()))
    print(f"\n{len(data)} records carry data about Libya, "
          f"{sum(r['is_digitised'] for r in data)} of them digitised")
    print("  by class:", dict(Counter(r["document_class"] for r in data)))
    print("  by era:  ", dict(Counter(r["era"] for r in data if r["era"])))
    print("\nthe series that fill the gap before 2006:")
    for row in sorted(data, key=lambda r: str(r["year"])):
        if row["document_class"] in ("population_census", "statistical_abstract") \
                and row["era"] in ("kingdom", "jamahiriya", "italian"):
            mark = "digitised" if row["is_digitised"] else "not digitised"
            print(f"  {str(row['year'] or '?'):>5}  {row['title'][:72]:72s} {mark}")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
