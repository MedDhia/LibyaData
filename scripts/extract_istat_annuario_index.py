#!/usr/bin/env python3
"""
Map the Libyan statistics in the Italian statistical yearbook, 1911 to 1943.

Source: Istituto Centrale di Statistica, `Annuario Statistico Italiano`, the 26
volumes ISTAT has digitised for the colonial period, listed in
`data/raw/istat/manifest.json` and downloaded by this script.

## What this is and why it is an index rather than a panel

Every volume carries one chapter on the colonies. This script finds that chapter
in each of the 26 volumes and walks it page by page, listing every table it
carries that says something about Libya: what the table is called, in the
volume's own words, and the page it is on.

The chapter is walked rather than read off its contents page because half the
run has no contents page. The volumes of the early 1930s open the chapter with
an `INDICE` naming each table; from 1934 the chapter drops it and starts
straight into the tables, and the late volumes never had one. Walking the pages
works for all three.

An index rather than a harmonised panel because the chapter is not one thing
across the run. It is called **Possessi e Protettorati italiani** while Libya is
a new conquest, **Colonie e Possedimenti** once the colonial state is settled,
and **Africa Italiana - Possedimenti** after 1938, and each renaming brings a
different set of tables and a different geography: one `Libia` in 1913, a
separate Tripolitania and Cirenaica through the 1920s and 1930s, four Libyan
provinces and a Sahara Libico at the end. A single table built across all of
that would harmonise things the source keeps apart. What a researcher needs
first is to know what exists, which is this.

The entries are the volumes' own words, in Italian, exactly as each contents
page prints them, with an English gloss of the recurring ones in `subject`.

## What counts as a Libyan table

Through the 1920s and early 1930s the chapter is divided by colony, so a table
under the heading `Tripolitania` is Tripolitania's and `scope` says so. From
1934 the chapter is one set of tables with the colonies as rows, and a table is
Libyan if Tripolitania, Cirenaica or Libia is one of those rows; `scope` then
reads `all colonies`. A table that names no Libyan row and sits under no Libyan
heading is not listed.

## Reading it

The scans split capitals off their own words, so `Colonie e Possedimenti` can
arrive as `.C OLONIE' E POSSEDIMENTI.` and `POSSESSI E PROTETTORATI` as
`POSSESSI lt PROTETTORATI`. Every heading match is therefore made against the
text with all punctuation and spacing removed. Page numbers are printed with
the same damage, `4°5` for 405, and are read with the same tolerance.

The chapter is found twice over: the volume's general index gives its printed
page, and the chapter's own opening page is then located in a window around it,
which is what fixes the offset between printed and PDF pages. Both numbers are
published, so a reader can open the file at the right place and check.

Outputs, under data/processed/istat/:
  libya_annuario_volumes.csv   one row per volume: the chapter and where it is
  libya_annuario_index.csv     one row per Libyan table the volume carries
"""

import argparse
import csv
import json
import re
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
BOOKS = RAW / "annuario"
OUT = ROOT / "data" / "processed" / "istat"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# The colonial chapter under each of the names the run gives it, matched
# against text stripped of everything but letters and digits.
CHAPTER = re.compile(
    r"possess\w{0,4}protettorat|coloni\w{0,3}possediment|africaitaliana|"
    r"possediment\w{0,3}colonial|coloni\w{0,3}protettorat|"
    r"impero\w{0,3}coloni", re.I)
# Two volumes call the chapter nothing but `Colonie`, which is too common a
# word to look for anywhere on a page. It is accepted only when it is the whole
# of a line, once the chapter numeral, the leader dots and the page number are
# taken off, which is what a chapter title looks like and a sentence does not.
BARE = re.compile(r"^(le)?coloni[ae](italian\w*)?$", re.I)
NUMERAL = re.compile(r"^[\s»)(]*(?:[IVXLC]{1,6}|\d{1,2})\s*[.\-)]\s*", re.I)


def is_chapter(line):
    if CHAPTER.search(flat(line)):
        return True
    core = NUMERAL.sub("", line.strip())
    core = re.sub(r"[.\u00b7\u2022\s»)(]*[\d\u00b0lIoO]{0,4}\s*$", "", core)
    return bool(BARE.fullmatch(flat(core)))

# The headings inside the chapter that open a Libyan section, and those that
# close one by opening somebody else's. Libya is one colony, then two, then
# four provinces and a desert, so the first list grows with the run.
LIBYAN = re.compile(
    r"^(libia|tripolitania|cirenaica|tripolitaniaecirenaica|"
    r"africasettentrionale\w*|provinci\w*dellalibia|saharalibico|"
    r"libiaesaharalibico)$", re.I)
FOREIGN = re.compile(
    r"^(eritrea|somalia\w*|africaorientale\w*|etiopia|isoleegee|"
    r"possedimento\w*dellisoleegee|isoleitaliane\w*|concessionedi\w*|"
    r"tientsin|tiensin|saseno|isoladisaseno|albania|"
    r"coloniaeritrea|somaliaitaliana)", re.I)

# An English gloss for the table names that recur across the run. Matched on
# the Italian stripped to letters, longest first, and left blank when the
# volume prints something this list does not carry.
SUBJECTS = [
    ("commerciomarittimo", "maritime trade"),
    ("movimentocommerciale", "trade"),
    ("movimentocommerciat", "trade"),
    ("commerciofral", "trade"),
    ("navigazionemarittima", "shipping"),
    ("navigazionemultt", "shipping"),
    ("trafllcoferroviario", "railway traffic"),
    ("trafficoferroviario", "railway traffic"),
    ("movimentodellanavigazione", "shipping"),
    ("superficieepopolazione", "area and population"),
    ("superficiepopolazione", "area and population"),
    ("popolazione", "population"),
    ("postetelegrafi", "posts and telegraphs"),
    ("posteetelegrafi", "posts and telegraphs"),
    ("trafficoferroviario", "railway traffic"),
    ("ferrovie", "railways"),
    ("pescadellespugne", "sponge fishing"),
    ("pesca", "fishing"),
    ("cassadirisparmio", "savings bank"),
    ("depositipresso", "savings bank deposits"),
    ("creditoagrario", "agricultural credit"),
    ("colonizzazioneagraria", "agrarian settlement"),
    ("datimetereologici", "weather"),
    ("datimeteorologici", "weather"),
    ("bilanciocoloniale", "colonial budget"),
    ("contoconsuntivo", "colonial budget"),
    ("forzemilitari", "garrison"),
    ("forzadeicomandi", "garrison"),
    ("truppecoloniali", "garrison"),
    ("corpidioccupazione", "garrison"),
    ("speseperloccupazione", "cost of the occupation"),
    ("occupazionedella", "cost of the occupation"),
    ("censimentoindustriale", "industrial census"),
    ("consistenzadelbestiame", "livestock"),
    ("produzioneagraria", "farm output"),
    ("religione", "religion"),
    ("generalita", "general note"),
    ("istruzione", "schooling"),
    ("movimentodelporto", "port traffic"),
    ("autoveicoli", "motor vehicles"),
]

# An index entry: a name, the leader dots, and the page or page range it ends
# on. The page may be a range, `422-423`, which is kept whole.
ENTRY = re.compile(r"^(?P<name>.*?\S)\s*[.·•\s»)]{2,}\s*"
                   r"(?P<page>\d[\d\s]{0,4}(?:\s*-\s*\d[\d\s]{0,4})?)\s*$")


def flat(text):
    return re.sub(r"[^A-Za-z0-9]+", "", text or "")


def page_number(token):
    """A printed page number, through OCR that sets 0 as o or a degree sign."""
    cleaned = re.sub(r"[^0-9]", "", token.translate(str.maketrans("oO°lI|",
                                                                 "000111")))
    return int(cleaned) if cleaned and len(cleaned) <= 4 else None


def subject_of(name):
    key = flat(name).lower()
    for needle, gloss in SUBJECTS:
        if needle in key:
            return gloss
    return ""


def volumes():
    """The yearbook volumes of the manifest, with the years each covers."""
    book = json.loads((RAW / "manifest.json").read_text())
    found = []
    for entry in book["files"]:
        if entry["group"] != "yearbook":
            continue
        name = Path(entry["path"]).name
        years = [int(y) for y in re.findall(r"(19\d\d)", name)]
        found.append({"file": name, "url": entry["url"],
                      "year_from": min(years), "year_to": max(years)})
    return sorted(found, key=lambda v: v["year_from"])


def fetch(volume):
    path = BOOKS / volume["file"]
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    BOOKS.mkdir(parents=True, exist_ok=True)
    print(f"  fetching {volume['file']}")
    request = urllib.request.Request(volume["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=900) as response:
        path.write_bytes(response.read())
    return path


def find_chapter(pdf):
    """The chapter's printed page, from the volume's general index, and the PDF
    page its own opening carries.

    Two readings rather than one: the general index says which printed page the
    chapter starts on, and the opening page is then looked for in a window
    around it. A volume whose front matter and plates are not paginated puts the
    two forty pages apart, which is exactly the offset this recovers.
    """
    pages = len(pdf.pages)
    printed, line_seen = None, ""
    for i in range(min(26, pages)):
        for line in (pdf.pages[i].extract_text() or "").splitlines():
            if len(line) > 140 or not is_chapter(line):
                continue
            number = page_number(line.split()[-1] if line.split() else "")
            if number and number > 20 and printed is None:
                printed, line_seen = number, " ".join(line.split())
    window = ((max(0, printed - 40), min(pages, printed + 50)) if printed
              else (int(pages * 0.55), pages))
    for i in range(*window):
        head = (pdf.pages[i].extract_text() or "")[:300]
        if CHAPTER.search(flat(head)) or any(is_chapter(line)
                                             for line in head.splitlines()[:5]):
            return printed, i, line_seen
    return printed, None, line_seen


def chapter_pages(pdf, start, limit=30):
    """The pages of the colonial chapter, from its opening to its last.

    The chapter is followed to its end by its own running head: every page of it
    carries the chapter's name at the top, and the first page that stops
    carrying it belongs to whatever comes next. Two pages in a row without it
    end the chapter, because a full-page table sometimes drops the head.
    """
    found, misses = [], 0
    for i in range(start, min(start + limit, len(pdf.pages))):
        text = pdf.pages[i].extract_text() or ""
        head = text[:300]
        if (i == start or CHAPTER.search(flat(head))
                or any(is_chapter(line) for line in head.splitlines()[:3])):
            found.append((i, text))
            misses = 0
        else:
            misses += 1
            if misses >= 2:
                break
            found.append((i, text))
    while len(found) > 1 and not CHAPTER.search(flat(found[-1][1][:300])):
        found.pop()
    
    return found


# A table heading: `2. Commercio marittimo`, `A. Notizie generali`, `b. Popola-
# zione libica`. The chapter numbers its tables and nothing else on the page,
# but it also prints its own contents the same way, so a line carrying a run of
# leader dots is an index entry and not a heading.
HEADING = re.compile(r"^\s*(?P<mark>[0-9IlO]{1,2}|[A-Za-z])\s*[.)]\s+"
                     r"(?P<name>[A-ZÀÈÉÌÒÙ].{5,88})$")
# The chapter prints its own contents in the same shape as a table heading, so
# a line that ends in a page number after leader dots is an index entry.
LEADERS = re.compile(r"[.·•»]\s*[.·•»]?\s*[\d°lIoO]{2,4}\s*$")
# A heading names a table; a line of the table itself carries its figures.
FIGURES = re.compile(r"(?:\b[\d°lIoO]{2,}\b.*){3}")
# Running section heads carry `Segue` when a colony's tables run over a page,
# and the scans letter-space them, so both are stripped before matching.
SEGUE = re.compile(r"^(segue|seguo|sesue)", re.I)


# A row label naming Libya in a table that runs the colonies down the side. The
# scans break the words, so this is matched against flattened text.
LIBYAN_ROW = re.compile(r"tripo[l1i]{1,3}tania|cirenaica|\blibia\b|"
                        r"saharalibico|libico", re.I)


def chapter_tables(pages):
    """Every table of the chapter that says something about Libya.

    A page is read line by line. A colony heading opens a section and any table
    heading below it belongs to that colony; a heading naming another colony
    closes it. A table under no colony heading is kept only if one of its rows
    names a Libyan territory, which is how the volumes from 1934 on carry Libya:
    one table for all the colonies with Tripolitania and Cirenaica as rows.
    """
    found, section, order = [], "", 0
    for number, text in pages:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        # Some volumes open the chapter with its own contents. That page names
        # every table and is not one, so listing from it would double the
        # chapter and give page numbers in the volume's printing rather than
        # the file's. A page with six entries ending in a page number is it.
        if sum(1 for line in lines if LEADERS.search(line)) >= 6:
            continue
        # Which tables on this page have a Libyan row, by the heading above
        # each line that names one.
        libyan_below = set()
        last_heading = None
        for index, line in enumerate(lines):
            match = HEADING.match(line)
            if match:
                last_heading = index
            elif last_heading is not None and LIBYAN_ROW.search(flat(line)):
                libyan_below.add(last_heading)
        for index, line in enumerate(lines):
            if not line:
                continue
            # A colony name is never a table name, so the section is decided
            # before the line is considered as a heading.
            bare = SEGUE.sub("", flat(re.sub(r"^[A-Za-z]\s*[-.)]\s*|[:.]\s*$",
                                             "", line)))
            if len(line) < 70:
                if LIBYAN.match(bare):
                    section = normalise(line)
                    continue
                if FOREIGN.match(bare):
                    section = ""
                    continue
            match = HEADING.match(line)
            if not match or LEADERS.search(line) or FIGURES.search(line):
                continue
            name = " ".join(match.group("name").split()).strip(" .·•»-")
            if len(flat(name)) < 6 or len(name) > 90:
                continue
            scope = section or ("all colonies" if index in libyan_below else "")
            if not scope:
                continue
            order += 1
            found.append({"scope": scope, "table": name,
                          "subject": subject_of(name), "pdf_page": number,
                          "order_in_chapter": order})
    return dedupe(found)


def normalise(scope):
    """`Segue - Tripoli tania.` and `TRIPOLITANIA` are the same section."""
    key = SEGUE.sub("", flat(re.sub(r"^[A-Za-z]\s*[-.)]\s*", "", scope))).lower()
    names = {"tripolitania": "Tripolitania", "cirenaica": "Cirenaica",
             "libia": "Libia", "saharalibico": "Sahara Libico",
             "africasettentrionale": "Africa Settentrionale Italiana",
             "provincie": "Provincie italiane della Libia",
             "provincia": "Provincie italiane della Libia"}
    for name, full in names.items():
        if key.startswith(name):
            return full
    return " ".join(scope.strip(" :.-").split())


def dedupe(rows):
    """A table continued over two pages is one table, not two.

    The chapter reprints a heading under `Segue` when a table runs on, so the
    same name on consecutive pages in the same section is one entry, kept at the
    page it started on.
    """
    kept = []
    for row in rows:
        twin = next((k for k in kept
                     if k["scope"] == row["scope"]
                     and flat(k["table"]).lower() == flat(row["table"]).lower()
                     and row["pdf_page"] - k["pdf_page"] <= 2), None)
        if twin:
            twin["pdf_pages"] = f"{twin['pdf_page']}-{row['pdf_page']}"
        else:
            row["pdf_pages"] = str(row["pdf_page"])
            kept.append(row)
    return kept


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    import pdfplumber

    rows, books = [], []
    for volume in volumes():
        path = fetch(volume)
        with pdfplumber.open(path) as pdf:
            printed, start, line_seen = find_chapter(pdf)
            entries, pages = [], []
            if start is not None:
                pages = chapter_pages(pdf, start)
                entries = chapter_tables(pages)
            books.append({
                "year_from": volume["year_from"], "year_to": volume["year_to"],
                "file": volume["file"], "pages": len(pdf.pages),
                "chapter_line": line_seen,
                "chapter_printed_page": printed if printed else "",
                "chapter_pdf_page": start if start is not None else "",
                "chapter_pdf_last": pages[-1][0] if pages else "",
                "page_offset": (start - printed
                                if start is not None and printed else ""),
                "libyan_tables": len(entries),
                "url": volume["url"]})
        for entry in entries:
            entry.update(year_from=volume["year_from"],
                         year_to=volume["year_to"], file=volume["file"])
            rows.append(entry)
        print(f"{volume['year_from']}-{volume['year_to']}: chapter pdf "
              f"{books[-1]['chapter_pdf_page']}-{books[-1]['chapter_pdf_last']}, "
              f"{len(entries)} Libyan tables", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "libya_annuario_volumes.csv", books,
          ["year_from", "year_to", "file", "pages", "chapter_printed_page",
           "chapter_pdf_page", "chapter_pdf_last", "page_offset",
           "libyan_tables", "chapter_line", "url"])
    write(OUT / "libya_annuario_index.csv", rows,
          ["year_from", "year_to", "scope", "table", "subject", "pdf_page",
           "pdf_pages", "order_in_chapter", "file"])
    report(books, rows)


def write(path, rows, fields):
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:32s} {len(rows):5d} rows")


def report(books, rows):
    print()
    missing = [b for b in books if b["chapter_pdf_page"] == ""]
    print(f"{len(books)} volumes, chapter found in {len(books) - len(missing)}")
    if missing:
        print("  no colonial chapter located:",
              ", ".join(str(b["year_from"]) for b in missing))
    empty = [b for b in books if b["chapter_pdf_page"] != ""
             and b["libyan_tables"] == 0]
    if empty:
        print("  chapter found but no Libyan table in it:",
              ", ".join(str(b["year_from"]) for b in empty))
    print(f"{len(rows)} Libyan tables indexed across "
          f"{len({r['year_from'] for r in rows})} volumes")
    print("  by scope:", dict(Counter(r["scope"] for r in rows)))
    subjects = Counter(r["subject"] for r in rows if r["subject"])
    print("  by subject:", dict(subjects.most_common(14)))
    unglossed = [r["table"] for r in rows if not r["subject"]]
    if unglossed:
        print(f"  {len(unglossed)} with no English gloss, e.g.", unglossed[:5])
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
