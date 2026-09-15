#!/usr/bin/env python3
"""
Search the Bibliothèque nationale de France for material on Libya.

Source: BnF Catalogue général <https://catalogue.bnf.fr>, read through its SRU
service rather than scraped. The catalogue is the index to Gallica: where a
record is digitised, its UNIMARC `856$u` carries the Gallica ARK and the
document is readable at gallica.bnf.fr.

## Why the catalogue and not Gallica

**gallica.bnf.fr refuses this repository's addresses.** Every path on that host,
the SRU service and the IIIF manifests included, answers `403 Access Interdit`
from a datacenter address, while `catalogue.bnf.fr/api/SRU` answers normally.
The catalogue carries the Gallica ARK for every digitised record, so the
inventory is built here and the documents themselves are fetched from an
ordinary connection. See `sources/access_notes.md`.

## Why the BnF at all

Libya's own statistical record starts late and breaks in 2011: the census of
2006 is the last one published. What exists before independence was published
by somebody else. Libya was Ottoman until 1911, Italian until 1943, then
divided between a British administration in Tripolitania and Cyrenaica and a
French one in Fezzan until 1951. The BnF holds the French half of that record,
the Fezzan administration's own publications among it, and a long run of French
consular, geographical and military reporting on the Regency of Tripoli before
it.

Search terms cover the place under every name it has been catalogued by: the
three provinces in French and Italian, the country in both, the Ottoman name,
and the towns that recur in colonial-era titles. `bib.anywhere` reads the
catalogue record, not the text of the document, so a hit means the record names
Libya, not that the word appears somewhere inside a thousand-page volume.

## Two schemas, because one of them breaks

Records are read as Dublin Core, which the service returns for everything, and
the digitised subset is read again as UNIMARC, which carries the Gallica ARK.
UNIMARC is not requested for the whole set because the service answers `erreur
de traitement` instead of a record for part of it: on "Cyrénaïque" it fails for
every one of the 1,021. Where it fails for a digitised record the row still
says the document is digitised, and only the ARK is missing.

`document_type` comes from Dublin Core and is worth reading before any count is
believed. "Cyrénaïque" looks like the richest term in the catalogue until the
type column shows that most of its digitised records are photographs of Greek
coins in the Cabinet des Médailles.

Writes data/raw/bnf/catalogue_records.json, one entry per record, deduplicated
on the catalogue ARK across search terms.
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "bnf"
SRU = "https://catalogue.bnf.fr/api/SRU"
PAGE = 50
RETRIES = 4

# Every name Libya and its parts are catalogued under. Italian and Ottoman
# forms are here because the colonial record was published in those languages
# and the BnF catalogues a title in the language it was printed in.
TERMS = (
    "Tripolitaine", "Cyrénaïque", "Fezzan", "Libye", "Tripoli de Barbarie",
    "Libia", "Tripolitania", "Cirenaica", "Trablus",
    "Ghadamès", "Mourzouk", "Koufra", "Misurata", "Benghazi", "Bengasi",
    "Ghat Libye", "Syrte", "Derna",
)

# Series whose volumes carry Libyan numbers but whose titles never say Libya,
# so a place-name search cannot reach them. The consular series are the ones
# that matter: a French consul in Tripoli filed an annual commercial report for
# forty years, and both series are digitised in full.
SERIES = {
    "Bulletin consulaire français":
        'bib.title all "Bulletin consulaire français"',
    "Rapports commerciaux des agents consulaires de France":
        'bib.title all "Rapports commerciaux des agents diplomatiques et '
        'consulaires de France"',
    # The Annales run to 184 country volumes; only the Tripolitanian and
    # Ottoman ones are wanted.
    "Annales du commerce extérieur (Tripolitaine)":
        'bib.title all "Annales du commerce extérieur" and bib.anywhere all '
        '"Tripolitaine"',
    "Mission scientifique du Fezzan":
        'bib.title all "Mission scientifique du Fezzan"',
}

MARC = "{info:lc/xmlns/marcxchange-v2}"
SRW = "{http://www.loc.gov/zing/srw/}"
DC = "{http://purl.org/dc/elements/1.1/}"
OAI_DC = "{http://www.openarchives.org/OAI/2.0/oai_dc/}"
FREE = 'bib.digitized all "freeAccess"'


def fetch(query, schema, start):
    """One page of results, retried: the service drops connections under load."""
    url = SRU + "?" + urllib.parse.urlencode({
        "version": "1.2", "operation": "searchRetrieve", "query": query,
        "recordSchema": schema, "maximumRecords": PAGE, "startRecord": start})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=180) as response:
                return ElementTree.fromstring(response.read())
        except Exception as exc:                                  # noqa: BLE001
            if attempt == RETRIES - 1:
                raise
            print(f"      retry {attempt + 1} after {type(exc).__name__}",
                  file=sys.stderr, flush=True)
            time.sleep(2 ** attempt)
    return None


def texts(record, tag):
    return [re.sub(r"\s+", " ", node.text).strip()
            for node in record.iter(f"{DC}{tag}") if node.text]


def one(record, tag):
    got = texts(record, tag)
    return got[0] if got else ""


def code_record(record):
    """One Dublin Core record, flattened."""
    identifiers = texts(record, "identifier")
    catalogue = next((i for i in identifiers if "catalogue.bnf.fr" in i), "")
    types = [t for t in texts(record, "type")
             if t not in ("text", "image", "physical object", "still image")]
    return {
        "record_ark": catalogue.rsplit("/", 1)[-1],
        "catalogue_url": catalogue.replace("http://", "https://"),
        "title": one(record, "title"),
        "authors": texts(record, "creator")[:4] or texts(record, "contributor")[:4],
        "publisher": one(record, "publisher"),
        "publication_date": one(record, "date"),
        "extent": one(record, "format"),
        "language": one(record, "language"),
        "document_type": types[0] if types else "",
        "subjects": texts(record, "subject")[:8],
        "description": one(record, "description")[:300],
        "gallica_url": "",
        "gallica_ark": "",
        "is_digitised": 0,
    }


def search(query, pause=0.4):
    """Every catalogue record for one query, with the Gallica ARKs it has."""
    records, start, total = {}, 1, None
    while True:
        tree = fetch(query, "dublincore", start)
        if total is None:
            node = tree.find(f"{SRW}numberOfRecords")
            total = int(node.text) if node is not None else 0
        batch = [code_record(r) for r in tree.iter(f"{OAI_DC}dc")]
        if not batch:
            break
        for record in batch:
            records.setdefault(record["record_ark"] or record["title"], record)
        start += len(batch)
        if start > total:
            break
        time.sleep(pause)

    # Second pass: the digitised subset in UNIMARC, for the Gallica ARK.
    digitised, start = 0, 1
    while True:
        tree = fetch(f"{query} and {FREE}", "unimarcxchange", start)
        node = tree.find(f"{SRW}numberOfRecords")
        subtotal = int(node.text) if node is not None else 0
        seen = 0
        for marc in tree.iter(f"{MARC}record"):
            seen += 1
            ark = gallica = ""
            for field in marc:
                tag = field.attrib.get("tag")
                if field.tag == f"{MARC}controlfield" and tag == "003":
                    ark = (field.text or "").strip().rsplit("/", 1)[-1]
                elif field.tag == f"{MARC}datafield" and tag == "856":
                    for sub in field:
                        if sub.attrib.get("code") == "u" and "gallica" in (
                                sub.text or ""):
                            gallica = sub.text.strip().replace("http://", "https://")
            row = records.get(ark)
            if row:
                row["is_digitised"] = 1
                digitised += 1
                if gallica:
                    row["gallica_url"] = gallica
                    # A serial's link ends in /date, the calendar of its runs,
                    # so the ARK is the segment after the naming authority.
                    found = re.search(r"ark:/12148/([^/?#]+)", gallica)
                    row["gallica_ark"] = found.group(1) if found else ""
        # The service answers "erreur de traitement" instead of a record for
        # part of the catalogue; those pages come back empty and are skipped.
        step = max(seen, PAGE)
        start += step
        if start > subtotal or subtotal == 0:
            break
        time.sleep(pause)
    return records, total, subtotal, digitised


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    collected, by_term = {}, {}
    searches = [(term, f'bib.anywhere all "{term}"') for term in TERMS]
    searches += list(SERIES.items())
    for term, query in searches:
        try:
            records, total, subtotal, arked = search(query)
        except Exception as exc:                                  # noqa: BLE001
            print(f"  {term:22s} {type(exc).__name__}: {exc}", file=sys.stderr)
            by_term[term] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        fresh = 0
        for key, record in records.items():
            if key not in collected:
                collected[key] = dict(record, found_by=[term])
                fresh += 1
            else:
                kept = collected[key]
                if term not in kept["found_by"]:
                    kept["found_by"].append(term)
                if record["is_digitised"] and not kept["is_digitised"]:
                    kept.update(is_digitised=1, gallica_url=record["gallica_url"],
                                gallica_ark=record["gallica_ark"])
        by_term[term] = {"records": total, "read": len(records),
                         "digitised": subtotal, "arks_read": arked, "new": fresh}
        print(f"  {term:22s} {total:5d} records, {subtotal:4d} digitised "
              f"({arked:4d} with an ARK), {fresh:4d} new", flush=True)

    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / "catalogue_records.json"
    path.write_text(json.dumps({
        "source": "https://catalogue.bnf.fr",
        "service": SRU,
        "publication": "Catalogue général de la Bibliothèque nationale de France",
        "retrieved": time.strftime("%Y-%m-%d"),
        "terms": list(TERMS),
        "series_titles": dict(SERIES),
        "by_term": by_term,
        "records": sorted(collected.values(),
                          key=lambda r: (r["publication_date"], r["title"])),
    }, ensure_ascii=False, indent=1) + "\n")

    digitised = sum(r["is_digitised"] for r in collected.values())
    arked = sum(1 for r in collected.values() if r["gallica_ark"])
    print(f"\n{path.name:28s} {len(collected)} records, {digitised} digitised, "
          f"{arked} carrying a Gallica ARK")
    print("next: python3 scripts/extract_bnf_libya_sources.py")


if __name__ == "__main__":
    main()
