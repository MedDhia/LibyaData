#!/usr/bin/env python3
"""
Download the OpenSanctions bulk collections that the Libya subgraph is cut from.

Source: OpenSanctions <https://www.opensanctions.org>, bulk distribution at
<https://data.opensanctions.org/datasets/latest/>.

Two collections are taken, both as FollowTheMoney entity streams (one JSON object
per line, so they can be filtered without loading 1.3 GB into memory):

  peps        politically exposed persons, 1.9m entities / 711k targets
  sanctions   consolidated sanctions lists, 293k entities / 73k targets

These are the **global** files. Libya is not a published subset, so the Libyan
part is cut locally by `scripts/extract_opensanctions_libya.py`.

The FollowTheMoney model puts relationships in the same stream as the things
they connect: a Person and a Company are entities, and so are the Directorship,
Ownership, Family and Occupancy records that link them. That is what makes a
network extractable from these files and not from the flat `targets.simple.csv`.

**Licence: CC BY-NC 4.0.** Non-commercial, attribution required. The output is
written under `data/external/sanctions/` rather than `data/processed/`, with
a NOTICE beside it, for the same reason the GADM-derived nighttime lights and the
ODbL OpenStreetMap anchors are kept there.

The index records a versioned artifact URL and a SHA-1 for every file, so a
rebuild can be checked against the exact export used here. Writes
data/raw/opensanctions/ and a manifest.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "opensanctions"
INDEX = "https://data.opensanctions.org/datasets/latest/index.json"
COLLECTIONS = ("peps", "sanctions")
RESOURCE = "entities.ftm.json"
UA = "LibyaData/1.0 (research; https://github.com/MedDhia/LibyaData)"


def digests(path):
    """SHA-1 to check against the index, SHA-256 for this repository's manifest."""
    sha1, sha256 = hashlib.sha1(), hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            sha1.update(chunk)
            sha256.update(chunk)
    return sha1.hexdigest(), sha256.hexdigest()


def download(session, url, path, expected_bytes):
    """Stream one file to disk, resuming nothing: a short read is an error."""
    with session.get(url, stream=True, timeout=600) as response:
        response.raise_for_status()
        written = 0
        with path.open("wb") as fh:
            for chunk in response.iter_content(1 << 22):
                fh.write(chunk)
                written += len(chunk)
                if written % (1 << 28) < (1 << 22):
                    print(f"    {written / 1e6:8.0f} MB of {expected_bytes / 1e6:.0f}",
                          flush=True)
    if written != expected_bytes:
        path.unlink(missing_ok=True)
        sys.exit(f"{path.name}: got {written} bytes, index says {expected_bytes}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="re-download even when the local file matches")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = UA

    index = session.get(INDEX, timeout=300).json()
    by_name = {d["name"]: d for d in index["datasets"]}

    manifest = []
    for name in COLLECTIONS:
        dataset = by_name.get(name)
        if dataset is None:
            sys.exit(f"collection not in the index: {name}")
        resource = next((r for r in dataset["resources"] if r["name"] == RESOURCE), None)
        if resource is None:
            sys.exit(f"{name}: no {RESOURCE} in the index")

        path = RAW / f"{name}.entities.ftm.json"
        if args.force or not path.exists() or path.stat().st_size != resource["size"]:
            print(f"  {name}: {resource['size'] / 1e6:.0f} MB", flush=True)
            download(session, resource["url"], path, resource["size"])
            time.sleep(0.5)
        else:
            print(f"  {name}: already present", flush=True)

        sha1, sha256 = digests(path)
        if sha1 != resource["checksum"]:
            sys.exit(f"{path.name}: SHA-1 {sha1} does not match the index "
                     f"({resource['checksum']})")
        manifest.append({
            "collection": name,
            "title": dataset["title"],
            "version": dataset["version"],
            "updated_at": dataset["updated_at"],
            "entity_count": dataset["entity_count"],
            "target_count": dataset["target_count"],
            "url": resource["url"],
            "file": path.name,
            "bytes": path.stat().st_size,
            "sha1_upstream": resource["checksum"],
            "sha256": sha256,
        })

    (RAW / "manifest.json").write_text(json.dumps({
        "source": "https://www.opensanctions.org",
        "index": INDEX,
        "export_run_time": index.get("run_time"),
        "ftm_model_version": index["model"].get("version"),
        "licence": "CC BY-NC 4.0",
        "retrieved": time.strftime("%Y-%m-%d"),
        "files": manifest,
    }, ensure_ascii=False, indent=1) + "\n")

    total = sum(m["bytes"] for m in manifest)
    print(f"\n{len(manifest)} collections, {total / 1e6:.0f} MB, checksums match the index")
    print("next: python3 scripts/extract_opensanctions_libya.py")


if __name__ == "__main__":
    main()
