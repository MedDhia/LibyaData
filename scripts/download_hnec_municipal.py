#!/usr/bin/env python3
"""
Collect HNEC's decisions and announcements on the municipal council elections.

Source: High National Elections Commission <https://hnec.ly>, news posts, read
through the WordPress REST API rather than scraped.

Libya's municipal councils were run by the Central Committee for Municipal
Council Elections until HNEC took the rounds over. HNEC has since run them in
numbered groups (المجموعة الأولى, الثانية, الثالثة), and publishes each step as
a numbered council decision: candidate lists, exclusions, campaign
authorisation, polling day, preliminary results, final results, and finally
`تشكيل المجلس البلدي (X)`, which constitutes the elected council of one named
municipality.

**Those formation decisions are the municipal appointments.** Unlike the
Official Gazette, every one of them names a baladiya, so this is the subnational
half of the officeholder record.

What is here and what is not. The decision, its number, its date and the
municipality are in the post title and are recovered exactly. The **names of the
elected members are not**: HNEC publishes the decision itself as a page scan,
either a JPG in the post body or a PDF with no text layer (the group 1 and
group 2 results run to 57 and 35 scanned pages). Reading those needs optical
character recognition of Arabic, which this repository has tried and failed at
on gridded Libyan documents. The member lists are therefore recorded as absent
rather than guessed.

Search is by phrase because there is no municipal category: the four phrases
below are unioned and deduplicated by post id.

Writes data/raw/hnec/municipal_posts.json, small enough to commit, so the
extraction is reproducible without re-querying a site that has blocked
datacenter addresses before.
"""

import argparse
import html
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "hnec"
POSTS = "https://hnec.ly/wp-json/wp/v2/posts"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SEARCHES = (
    "تشكيل المجلس البلدي",
    "اعتماد النتائج النهائية لانتخابات المجالس البلدية",
    "النتائج النهائية لانتخابات المجالس البلدية",
    "انتخابات المجالس البلدية",
)


# WordPress serves a resized copy in the post body; the decision is only legible
# at full size, so the "-212x300" the theme appends is stripped off.
THUMBNAIL = re.compile(r"-\d{2,4}x\d{2,4}(?=\.(?:jpg|jpeg|png)$)", re.I)


def clean(markup):
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text)).strip()


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    session = requests.Session()
    session.headers["User-Agent"] = UA

    found = {}
    for phrase in SEARCHES:
        page = 1
        while True:
            response = session.get(POSTS, params={
                "search": phrase, "per_page": 100, "page": page,
                "orderby": "date", "order": "desc",
                "_fields": "id,date,link,title,content"}, timeout=120)
            if response.status_code != 200:
                if page == 1:
                    sys.exit(f"hnec.ly posts search returned "
                             f"{response.status_code}; the site's firewall may be "
                             f"refusing this address.")
                break
            batch = response.json()
            if not batch:
                break
            for post in batch:
                markup = post["content"]["rendered"]
                found[post["id"]] = {
                    "id": post["id"],
                    "date": post["date"],
                    "link": post["link"],
                    "title": clean(post["title"]["rendered"]),
                    "body": clean(markup)[:1200],
                    # The decision itself is published as a scan; record where.
                    "pdfs": re.findall(r'href="([^"]+\.pdf)"', markup),
                    "images": [THUMBNAIL.sub("", u) for u in
                               re.findall(r'src="([^"]+\.(?:jpg|jpeg|png))"', markup)
                               if "hnec.ly" in u],
                }
            page += 1
            time.sleep(0.2)
        print(f"  {phrase[:46]:48s} running total {len(found)}")

    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / "municipal_posts.json"
    path.write_text(json.dumps({
        "source": "https://hnec.ly",
        "endpoint": POSTS,
        "searches": list(SEARCHES),
        "retrieved": time.strftime("%Y-%m-%d"),
        "posts": sorted(found.values(), key=lambda p: p["date"]),
    }, ensure_ascii=False, indent=1) + "\n")

    scans = sum(1 for p in found.values() if p["pdfs"] or p["images"])
    print(f"\n{path.name:34s} {len(found)} posts, {scans} carrying a scan of the "
          f"decision")
    print("next: python3 scripts/extract_municipal_councils.py")


if __name__ == "__main__":
    main()
