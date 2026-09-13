#!/usr/bin/env python3
"""
Mirror the Official Gazette issues published by the House of Representatives.

Source: الجريدة الرسمية, دولة ليبيا, ديوان مجلس النواب, published at
<https://parliament.ly> and printed "نُشرت بأمر رئيس مجلس النواب". Statutory
basis is Law 8 of 2011 on organising the Official Gazette, amended by Law 10 of
2022.

Since the 2014 institutional split there is no single national gazette. This is
the House of Representatives' own series, which began with its first issue in
January 2023 and is the only Libyan gazette with a reachable, machine-readable
archive: the site runs WordPress with the REST API open, so issues are
enumerated through `wp-json/wp/v2/media` rather than scraped.

That provenance is a property of the data, not a footnote. The series records
decisions of the House, its Presidency Board and its Speaker, together with
Supreme Constitutional Court judgments and public notices. It does **not**
record the Tripoli government's own appointments, so an appointments dataset
built from it is an eastern-institution record and has to be read as one. The
Government of National Unity's channel, pm.gov.ly, is a placeholder with an
injected link farm; see `sources/access_notes.md`.

The commission's own site blocked datacenter addresses when Phase 1 probed it;
it answered when this was written. If it refuses, run from an ordinary
connection.

Writes data/raw/gazette/ and a manifest with a SHA-256 per issue.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "gazette"
MEDIA = "https://parliament.ly/wp-json/wp/v2/media"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# A media item is an issue when its title names the gazette. Titles are not
# uniform: "العدد الأول من الجريدة الرسمية", "الجريدة الرسمية _ العدد السابع",
# "العدد الخامس – السنة الثانية من الجريدة الرسمية".
GAZETTE = "الجريدة الرسمية"


def title_of(item):
    title = item["title"]["rendered"]
    title = title.replace("&#8211;", "-").replace("&amp;", "&").strip()
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", title))


def list_issues(session):
    """Every gazette PDF in the media library, paged 100 at a time."""
    items, page = [], 1
    while True:
        response = session.get(MEDIA, params={
            "per_page": 100, "page": page, "mime_type": "application/pdf",
            "_fields": "id,title,source_url,date"}, timeout=120)
        if response.status_code != 200:
            if page == 1:
                sys.exit(f"parliament.ly media listing returned "
                         f"{response.status_code}; the site's firewall may be "
                         f"refusing this address.")
            break
        batch = response.json()
        if not batch:
            break
        items += batch
        page += 1
        time.sleep(0.2)
    return [m for m in items if GAZETTE in title_of(m)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA

    issues = list_issues(session)
    print(f"{len(issues)} gazette issues in the media library")

    manifest, failures = [], []
    for item in sorted(issues, key=lambda m: m["date"]):
        path = RAW / f"gz_{item['id']}.pdf"
        if not path.exists():
            response = session.get(item["source_url"], timeout=300)
            if response.status_code != 200 or response.content[:4] != b"%PDF":
                failures.append((item["id"], response.status_code))
                continue
            path.write_bytes(response.content)
            time.sleep(0.2)
        manifest.append({
            "id": item["id"],
            "title": title_of(item),
            "date": item["date"],
            "url": item["source_url"],
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

    (RAW / "manifest.json").write_text(json.dumps({
        "source": "https://parliament.ly",
        "publication": "الجريدة الرسمية - دولة ليبيا - ديوان مجلس النواب",
        "publishing_authority": "House of Representatives",
        "statutory_basis": "Law 8 of 2011, amended by Law 10 of 2022",
        "retrieved": time.strftime("%Y-%m-%d"),
        "issues": manifest,
    }, ensure_ascii=False, indent=1) + "\n")

    total = sum(m["bytes"] for m in manifest)
    print(f"{len(manifest)} issues, {total / 1e6:.1f} MB, "
          f"{manifest[0]['date'][:10]} to {manifest[-1]['date'][:10]}")
    for item_id, status in failures:
        print(f"  failed: {item_id} HTTP {status}", file=sys.stderr)
    print("next: python3 scripts/extract_gazette_appointments.py")


if __name__ == "__main__":
    main()
