#!/usr/bin/env python3
"""
Download the HNEC documents that state which municipality a locality sits in.

Source: High National Elections Commission <https://hnec.ly>.

Three collections, all found through the site's WordPress REST API rather than
by scraping the pages:

  polling_centres/   "تحديث مراكز الاقتراع لسنة 2021", 24 documents, one per
                     electoral office region, listing every polling centre with
                     its locality and its municipality.
  municipal_2025/    "المراكز_<office>_<baladiya>", 11 documents from October
                     2025, one per municipality holding a council election. The
                     municipality is in the file name and the centre codes are
                     in the table, so these date the register forward without
                     depending on the Arabic text layer, which is scrambled.
  card_distribution/ two voter-card distribution statistics, 2024 and 2025,
                     which list a centre code, a centre name and a municipality.

HNEC's site sits behind a WAF that has intermittently refused datacenter IPs, so
this may fail from a cloud host even though the documents are public; run it from
an ordinary connection if it does.

The commission also publishes 2,404 "قوائم الناخبين" voter lists naming
individual registered voters. Those are deliberately not downloaded: they are
personal data and no research question here needs them.

Writes the three directories under data/raw/hnec/ and a manifest per collection
with a SHA-256 for every file.
"""

import hashlib
import json
import sys
import time
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hnec"
# One entry per collection: directory, manifest, and how its documents are
# recognised among the media library's 3,500 PDFs.
COLLECTIONS = [
    ("polling_centres", "polling_centres_manifest.json", "pc",
     lambda title: title.startswith("تحديث") and "مراكز الاقتراع" in title),
    ("municipal_2025", "municipal_2025_manifest.json", "mc",
     lambda title: title.startswith("المراكز_")),
    ("card_distribution", "card_distribution_manifest.json", "cd",
     lambda title: "توزيع" in title and "احصائي" in title),
]
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def list_media(session):
    """Every PDF in the media library, paged 100 at a time."""
    items, page = [], 1
    while True:
        response = session.get(
            "https://hnec.ly/wp-json/wp/v2/media",
            params={"per_page": 100, "page": page, "mime_type": "application/pdf",
                    "_fields": "id,title,source_url,date"}, timeout=120)
        if response.status_code != 200:
            if page == 1:
                sys.exit(f"HNEC media listing returned {response.status_code}; the "
                         f"site's firewall may be refusing this address.")
            break
        batch = response.json()
        if not batch:
            break
        items += batch
        page += 1
        time.sleep(0.2)
    return items


def title_of(item):
    """The media title, with the hamza written one way.

    HNEC's own titles mix the composed ئ with the decomposed ي + U+0654, so a
    plain substring test finds one 2024 statistic and misses the other.
    """
    title = item["title"]["rendered"].replace("&#8211;", "-").strip()
    return unicodedata.normalize("NFC", title)


def fetch(session, items, directory, prefix):
    """Download one collection, returning its manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest, failures = [], []
    for item in items:
        path = directory / f"{prefix}_{item['id']}.pdf"
        if not path.exists():
            response = session.get(item["source_url"], timeout=180)
            if response.status_code != 200 or response.content[:4] != b"%PDF":
                failures.append((item["id"], response.status_code))
                continue
            path.write_bytes(response.content)
            time.sleep(0.3)
        manifest.append({
            "id": item["id"],
            "title": title_of(item),
            "date": item.get("date", ""),
            "url": item["source_url"],
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return manifest, failures


def main():
    session = requests.Session()
    session.headers["User-Agent"] = UA
    media = list_media(session)
    print(f"{len(media)} PDFs in the media library")

    failures = []
    for name, manifest_name, prefix, matches in COLLECTIONS:
        items = [m for m in media if matches(title_of(m))]
        manifest, failed = fetch(session, items, RAW / name, prefix)
        failures += failed
        (RAW / manifest_name).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
        total = sum(m["bytes"] for m in manifest)
        print(f"  {name:20s} {len(manifest):3d} documents, {total / 1e6:5.1f} MB")

    for item_id, status in failures:
        print(f"  failed: {item_id} HTTP {status}", file=sys.stderr)
    print("next: python3 scripts/extract_hnec_polling_centres.py")


if __name__ == "__main__":
    main()
