#!/usr/bin/env python3
"""
Download the Bureau of Statistics and Census publications catalogued by
harvest_bsc_catalogue.py.

Files are stored under data/raw/bsc/pdf/ named by a hash of their source URL,
because the published filenames are Arabic, long, and not stable between
releases. data/raw/bsc/bsc_pdf_manifest.json maps each stored file back to its
title, source URL and SHA-256.

By default only the series the extraction scripts read are fetched. Pass --all
to mirror the whole catalogue (roughly 1 GB).
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "bsc"
PDF_DIR = RAW / "pdf"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# Series currently used downstream: price indices and inflation, censuses,
# statistical yearbooks, foreign trade, vital statistics and household surveys.
WANTED = ("الرقم القياسي|الأرقام القياسية|التضخم|تعداد|الكتاب الإحصائي"
          "|الكتاب الاحصائي|التجارة الخارجية|الإحصاءات الحيوية"
          "|الاحصاءات الحيوية|مسح")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="download the entire catalogue, not just used series")
    args = ap.parse_args()

    catalogue = RAW / "bsc_catalogue.csv"
    if not catalogue.exists():
        sys.exit("Run scripts/harvest_bsc_catalogue.py first.")

    df = pd.read_csv(catalogue)
    df = df[df.status == "document_linked"]
    if not args.all:
        df = df[df.title_ar.str.contains(WANTED, regex=True, na=False)]
    print(f"{len(df)} documents to fetch")

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA

    manifest, failures = [], []
    for i, row in enumerate(df.itertuples(), 1):
        original = urllib.parse.unquote(row.document_url.rsplit("/", 1)[-1])
        local = hashlib.sha1(row.document_url.encode()).hexdigest()[:12] + ".pdf"
        path = PDF_DIR / local

        if not path.exists():
            try:
                resp = session.get(row.document_url, timeout=90)
            except requests.RequestException as exc:
                failures.append((original, type(exc).__name__))
                continue
            if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                failures.append((original, f"HTTP {resp.status_code}"))
                continue
            path.write_bytes(resp.content)
            time.sleep(0.4)

        manifest.append({
            "local": local,
            "original_name": original,
            "url": row.document_url,
            "title_ar": row.title_ar,
            "domain": row.domain,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        })
        if i % 25 == 0:
            print(f"  {i}/{len(df)}")

    (RAW / "bsc_pdf_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    total = sum(m["bytes"] for m in manifest)
    print(f"{len(manifest)} documents, {total / 1e6:.0f} MB")

    if failures:
        print(f"\n{len(failures)} failed:", file=sys.stderr)
        for name, why in failures:
            print(f"  {why:12s} {name[:70]}", file=sys.stderr)


if __name__ == "__main__":
    main()
