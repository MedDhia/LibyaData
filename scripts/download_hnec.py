#!/usr/bin/env python3
"""
Download HNEC's 2021 polling-centre register.

Source: High National Elections Commission <https://hnec.ly>, "تحديث مراكز
الاقتراع لسنة 2021" — 24 documents, one per electoral office region, listing
every polling centre with its locality and its municipality.

HNEC's site sits behind a WAF that has intermittently refused datacenter IPs, so
this may fail from a cloud host even though the documents are public; run it from
an ordinary connection if it does. The files are found through the site's
WordPress REST API rather than by scraping the pages.

Writes data/raw/hnec/polling_centres/ and a manifest with a SHA-256 per file.
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hnec"
PDFS = RAW / "polling_centres"
SEARCH = "تحديث مراكز الاقتراع"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def main():
    PDFS.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA

    listing = session.get("https://hnec.ly/wp-json/wp/v2/media",
                          params={"search": SEARCH, "per_page": 100,
                                  "_fields": "id,title,source_url,mime_type"},
                          timeout=90)
    if listing.status_code != 200:
        sys.exit(f"HNEC media search returned {listing.status_code}; the site's "
                 f"firewall may be refusing this address.")
    items = [m for m in listing.json() if m["mime_type"] == "application/pdf"]
    print(f"{len(items)} polling-centre documents listed")

    manifest, failures = [], []
    for item in items:
        path = PDFS / f"pc_{item['id']}.pdf"
        if not path.exists():
            response = session.get(item["source_url"], timeout=180)
            if response.status_code != 200 or response.content[:4] != b"%PDF":
                failures.append((item["id"], response.status_code))
                continue
            path.write_bytes(response.content)
            time.sleep(0.3)
        manifest.append({
            "id": item["id"],
            "title": item["title"]["rendered"].replace("&#8211;", "-"),
            "url": item["source_url"],
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

    (RAW / "polling_centres_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    total = sum(m["bytes"] for m in manifest)
    print(f"{len(manifest)} documents, {total / 1e6:.1f} MB")
    for item_id, status in failures:
        print(f"  failed: {item_id} HTTP {status}", file=sys.stderr)
    print("next: python3 scripts/extract_hnec_polling_centres.py")


if __name__ == "__main__":
    main()
