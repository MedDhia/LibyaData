#!/usr/bin/env python3
"""
Import the Libya subset of the LRCC-DVNL nighttime-lights analysis.

Source: https://github.com/MedDhia/SatelliteImagery — reproducible importers for
the LRCC-DVNL long-term global nighttime light series, 1992-2022 at 1 km
(Tang et al. 2025, Scientific Data 12, 971).

That repository publishes results and figures for 146 countries. This copies the
Libya subset into `data/external/nighttime_lights/`: the five result tables, the
31 annual rasters clipped to Libya, and the 321 figures, together with the
upstream licence notice and a manifest recording the source commit and a
SHA-256 for every file taken.

The imported tables are keyed by GADM 4.1 romanised names ("Darnah", "Surt",
"Wadi ash Shati'") while the census is keyed by its own ("Derna", "Sirte",
"Wadi al Shatii"), and only seven of the 22 agree. Run
`scripts/build_concordance.py` afterwards to produce the crosswalk that joins
them.

Usage:
    git clone --depth 1 https://github.com/MedDhia/SatelliteImagery <path>
    python3 scripts/import_nighttime_lights.py --source <path>
"""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "external" / "nighttime_lights"
PROCESSED = ROOT / "data" / "processed"

ISO3 = "LBY"
SOURCE_REPO = "https://github.com/MedDhia/SatelliteImagery"

def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def copy_tree(source, destination):
    """Copy a directory, returning one manifest entry per file."""
    entries = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        entries.append({
            "path": str(target.relative_to(ROOT)),
            "source_path": str(path.relative_to(source.parents[1])),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        })
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/home/user/meddhia/satelliteimagery",
                        help="checkout of the SatelliteImagery repository")
    args = parser.parse_args()
    source = Path(args.source).resolve()

    results = source / "results" / ISO3
    figures = source / "figures" / ISO3
    for path in (results, figures):
        if not path.is_dir():
            sys.exit(f"not found: {path}. Clone {SOURCE_REPO} first.")

    try:
        commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit = "unknown"

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)

    manifest = []
    manifest += copy_tree(results, DEST / "results")
    manifest += copy_tree(figures, DEST / "figures")

    # The upstream licence notice travels with the files it covers.
    notice = source / "figures" / "NOTICE.md"
    if notice.exists():
        shutil.copy2(notice, DEST / "NOTICE.md")

    tables = sum(1 for e in manifest if e["path"].endswith(".csv"))
    rasters = sum(1 for e in manifest if e["path"].endswith(".tif"))
    images = sum(1 for e in manifest if e["path"].endswith(".png"))
    total = sum(e["bytes"] for e in manifest)

    (DEST / "SOURCE.json").write_text(json.dumps({
        "source_repository": SOURCE_REPO,
        "source_commit": commit,
        "subset": f"results/{ISO3} and figures/{ISO3}",
        "dataset": "LRCC-DVNL global nighttime lights, 1992-2022, 1 km",
        "dataset_doi": "https://doi.org/10.7910/DVN/15IKI5",
        "paper_doi": "https://doi.org/10.1038/s41597-025-05246-8",
        "boundaries": "GADM 4.1 (gadm.org), non-commercial; see NOTICE.md",
        "files": len(manifest),
        "bytes": total,
        "manifest": manifest,
    }, indent=2, ensure_ascii=False) + "\n")

    print(f"{tables} tables, {rasters} rasters, {images} figures  "
          f"{total / 1e6:.1f} MB  from {commit[:12]}")
    print("next: python3 scripts/build_concordance.py")


if __name__ == "__main__":
    main()
