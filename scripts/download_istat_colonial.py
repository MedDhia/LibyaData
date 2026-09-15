#!/usr/bin/env python3
"""
Find the Italian colonial statistics on Libya in ISTAT's digital library.

Source: Istituto Nazionale di Statistica, Biblioteca digitale
<https://ebiblio.istat.it/digibib/>. The library is served as a plain Apache
directory index, so it can be walked rather than searched, and every file is a
direct PDF download with no session, no viewer and no rate limit beyond what
politeness requires.

## Why Italy holds Libya's earliest statistics

Italy ruled Libya from 1911 to 1943 and counted it. The Istituto Centrale di
Statistica del Regno d'Italia ran the colony into the national census twice, in
1931 and 1936, and the two colonial volumes are in this library under the
censuses they belong to:

  VII censimento 1931, Volume V   Colonie e possedimenti          215 pages
  VIII censimento 1936, Volume V  Libia, Isole italiane dell'Egeo,
                                  Tientsin                        252 pages

Both carry a text layer. The 1936 volume ends with `ELENCO ALFABETICO DELLE
LOCALITÀ DELLA LIBIA`, a list of every locality with the administrative
circumscription it belonged to on 21 April 1936, against the population table it
indexes. That is the same object as this repository's mahalla concordance,
seventy years earlier, and it is the reason this library is worth walking.

This repository's own census data begins in 2006, and the BnF inventory
(`sources/bnf_README.md`) found the Libyan censuses of 1954 and 1964 catalogued
but not digitised. These two are digitised and downloadable.

## The yearbooks, which the filter cannot see

The library holds thousands of files, nearly all of them Italian domestic
statistics. A path is kept when it names Libya, a Libyan province, the colonies
as a category, or the Italian Africa the colonies were folded into. That reads
file and directory names, not contents, and the largest Libyan series in the
library is invisible to it.

The `Annuario statistico italiano` is here in a complete run, every volume from
1911 to 1943, named by year. Its Libyan chapter is inside. In the volume for
1938, chapter XIX, `Africa Italiana - Possedimenti`, section B, runs from page
325 to page 335 and tabulates: the 1936 census by province, the movement of the
national, foreign and assimilated population, the census of agricultural
holdings and the population living on them, shipping in the ports of western and
eastern Libya, foreign trade, migration through the Commissariato per le
migrazioni, agricultural credit, and schools. Thirty-odd volumes of that is a
colonial-era panel, and it is why the yearbook years are listed by name here
rather than left to the filter.

The default run walks the branches that hold colonial material rather than the
whole library, which is large and answers slowly once it has been walked once.
`--all` walks everything, and the manifest records which was done.

Writes data/raw/istat/manifest.json. With `--fetch` it also downloads the files
it found, with a SHA-256 for each; without it the manifest records size and URL
only, because the two census volumes alone are 35 MB and the yearbook run is
about 25 MB a volume.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
LIBRARY = "https://ebiblio.istat.it/digibib/"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
LINK = re.compile(r'<a href="([^"]+)">')
RETRIES = 4

# A path is Libyan when it says so. "Africa italiana" and "colonie" are here
# because the colonial volumes are titled by the empire rather than the country.
# The library is large and answers slowly under load, so the default run walks
# the branches that hold colonial material rather than all of it. `--all` walks
# everything; the manifest records which was done.
SUBTREES = (
    "Censimenti%20popolazione/",
    "Annuario%20Statistico%20Italiano/",
    "Commercio/",
    "Demografia/",
    "Agricoltura/",
    "Emigrazione/",
    "Storia/",
    "Sommario%20Statistiche%20Storiche/",
)

LIBYA = re.compile(
    r"(?i)libia|libya|tripolitania|cirenaica|fezzan|bengasi|tripoli|"
    r"colonie|coloniale|possediment|africa[_ ]?italiana|oltremare")

# The Italian statistical yearbook, whose Libyan chapter is inside the volume and
# not in its file name. Every volume from the invasion to the loss of the colony
# is taken.
YEARBOOK = "Annuario Statistico Italiano/RAV0040597ASI{}.pdf"
YEARBOOK_YEARS = [str(y) for y in range(1911, 1917)] + [
    "1917_1918", "1919_1921", "1922_1925"] + [
    str(y) for y in range(1927, 1944)]

# Series that carry Libyan numbers under an Italian title and are not tied to a
# single year, so they are reported rather than collected.
COLONIAL_SECTIONS = {
    "Commercio/Movimento_Commerciale":
        "trade of the Kingdom, annual volumes 1881-1938, with the colonies "
        "from 1912",
    "Censimenti agricoltura":
        "the agricultural census; the Libyan farm census is reported in the "
        "yearbook's chapter XIX",
}


def read(url):
    """One directory listing, retried: the server resets under load."""
    for attempt in range(RETRIES):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read().decode("utf-8", "replace")
        except Exception as exc:                                  # noqa: BLE001
            if attempt == RETRIES - 1:
                print(f"  unreadable: {url} ({type(exc).__name__})",
                      file=sys.stderr)
                return ""
            time.sleep(2 ** attempt)
    return ""


def walk(start, pause=0.15):
    """Every file under one directory of the library."""
    seen, files, queue = set(), [], [start]
    while queue:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        for href in LINK.findall(read(url)):
            if href.startswith(("?", "/", "http")):
                continue
            target = url + href
            (queue if href.endswith("/") else files).append(target)
        if len(seen) % 10 == 0:
            print(f"  {len(seen):4d} directories, {len(files):5d} files",
                  flush=True)
        time.sleep(pause)
    return files, len(seen)


def head(url):
    """Size and type of one file, without downloading it.

    Retried like a listing: a dropped connection here writes a zero into the
    manifest, which reads as a missing file rather than a missing answer.
    """
    request = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": UA})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return (int(response.headers.get("content-length") or 0),
                        response.headers.get("content-type", ""))
        except Exception as exc:                                  # noqa: BLE001
            if attempt == RETRIES - 1:
                print(f"  unmeasured: {url} ({type(exc).__name__})",
                      file=sys.stderr)
                return 0, ""
            time.sleep(2 ** attempt)
    return 0, ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true",
                        help="download the files, not just the manifest")
    parser.add_argument("--subtree", default="",
                        help="walk one directory instead of the default set")
    parser.add_argument("--all", action="store_true",
                        help="walk the whole library, which takes far longer")
    args = parser.parse_args()

    if args.all:
        branches = [""]
    elif args.subtree:
        branches = [args.subtree]
    else:
        branches = list(SUBTREES)

    files, directories = [], 0
    for branch in branches:
        print(f"walking {LIBRARY}{branch}")
        found, seen = walk(LIBRARY + branch)
        files += found
        directories += seen
    print(f"{directories} directories, {len(files)} files")

    found = [f for f in files if LIBYA.search(urllib.parse.unquote(f))]
    print(f"{len(found)} whose path names Libya, a province, or the colonies")

    # The yearbooks are named by year, not by colony, so they are added by name.
    yearbooks = [LIBRARY + urllib.parse.quote(YEARBOOK.format(year))
                 for year in YEARBOOK_YEARS]
    known = set(files)
    found += [url for url in yearbooks if url in known or not files]
    print(f"{len(yearbooks)} yearbook volumes 1911-1943 added by name\n")

    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    for url in sorted(set(found)):
        path = urllib.parse.unquote(url[len(LIBRARY):])
        size, kind = head(url)
        entry = {"path": path, "url": url, "bytes": size, "content_type": kind,
                 "group": "yearbook" if "ASI" in path else "libya_named"}
        if args.fetch:
            target = RAW / re.sub(r"[^A-Za-z0-9._-]+", "_", path)
            if not target.exists():
                request = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(request, timeout=600) as response:
                    target.write_bytes(response.read())
                time.sleep(0.3)
            entry["file"] = target.name
            entry["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest.append(entry)
        print(f"  {size / 1e6:7.1f} MB  {path}")

    (RAW / "manifest.json").write_text(json.dumps({
        "source": "https://ebiblio.istat.it/digibib/",
        "publication": "Istituto Nazionale di Statistica, Biblioteca digitale",
        "retrieved": time.strftime("%Y-%m-%d"),
        "branches_walked": branches,
        "directories_walked": directories,
        "files_seen": len(files),
        "filter": LIBYA.pattern,
        "yearbook_years": YEARBOOK_YEARS,
        "colonial_sections_to_search_by_hand": COLONIAL_SECTIONS,
        "files": manifest,
    }, ensure_ascii=False, indent=1) + "\n")

    total = sum(e["bytes"] for e in manifest)
    print(f"\nmanifest.json  {len(manifest)} files, {total / 1e6:.1f} MB"
          f"{' downloaded' if args.fetch else ' listed, not downloaded'}")
    print("series that carry a colonial section under an Italian title, "
          "to be searched inside:")
    for series, note in COLONIAL_SECTIONS.items():
        print(f"  {series:36s} {note}")


if __name__ == "__main__":
    main()
