#!/usr/bin/env python3
"""
Build a catalogue of Bureau of Statistics and Census publications.

The BSC publication listings (/our-versions/, /blog/) render client-side and
expose no document links to an HTTP client. The catalogue is instead reachable
through the WordPress sitemap index, which enumerates five publication post
types. This script walks those sitemaps, visits each publication page, and
records the document it links to.

Output: data/raw/bsc/bsc_catalogue.csv
"""

import csv
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "bsc"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
BASE = "https://bsc.ly"

# Sitemap post types that hold publications, mapped to a topical domain.
POST_TYPES = {
    "economic_statistics": "economic",
    "demog_statist": "demographic",
    "vital-administrative": "vital",
    "social_statistics": "social",
}

DOC_RE = re.compile(r"\.(pdf|xlsx|xls|csv|zip|docx?)$", re.I)
YEAR_RE = re.compile(r"(19[5-9]\d|20[0-4]\d)")


def get(session, url, tries=3):
    for attempt in range(tries):
        try:
            r = session.get(url, timeout=45)
            if r.status_code == 200:
                return r
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA

    rows = []
    for post_type, domain in POST_TYPES.items():
        sm = get(session, f"{BASE}/wp-sitemap-posts-{post_type}-1.xml")
        if sm is None:
            print(f"  sitemap unreachable: {post_type}", file=sys.stderr)
            continue
        urls = re.findall(r"<loc>([^<]+)</loc>", sm.text)
        print(f"{post_type}: {len(urls)} publication pages")

        for url in urls:
            page = get(session, url)
            if page is None:
                rows.append({
                    "domain": domain, "post_type": post_type, "page_url": url,
                    "title_ar": "", "document_url": "", "document_format": "",
                    "reference_years": "", "status": "page_unreachable",
                })
                continue

            soup = BeautifulSoup(page.text, "lxml")
            title = soup.title.get_text(strip=True) if soup.title else ""
            title = title.split("–")[0].strip()

            doc = ""
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if DOC_RE.search(href.split("?")[0]):
                    doc = urllib.parse.urljoin(BASE, href)
                    break

            decoded = urllib.parse.unquote(doc or url)
            years = sorted(set(YEAR_RE.findall(title + " " + decoded)))

            rows.append({
                "domain": domain,
                "post_type": post_type,
                "page_url": url,
                "title_ar": title,
                "document_url": doc,
                "document_format": (doc.rsplit(".", 1)[-1].lower() if doc else ""),
                "reference_years": ";".join(years),
                "status": "document_linked" if doc else "no_document_on_page",
            })
            time.sleep(0.3)

    path = OUT / "bsc_catalogue.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "domain", "post_type", "page_url", "title_ar", "document_url",
            "document_format", "reference_years", "status"])
        w.writeheader()
        w.writerows(rows)

    linked = sum(1 for r in rows if r["status"] == "document_linked")
    print(f"\n{path}: {len(rows)} pages, {linked} with a linked document")


if __name__ == "__main__":
    main()
