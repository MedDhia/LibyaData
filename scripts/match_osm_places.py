#!/usr/bin/env python3
"""
Anchor census mahallas to OpenStreetMap places, giving them coordinates.

The concordance built by `scripts/build_concordance.py` identifies every mahalla
and places it in its shabiya, but carries no geometry: no boundary layer for
Libya goes below the 22 shabiyat. This attaches a point to each mahalla it can
match, which is what lets a mahalla be assigned to any future boundary layer, or
mapped at all.

Source: Populated Places of Libya, OpenStreetMap via HOT
<https://data.humdata.org/dataset/hotosm_lby_populated_places>.

Matching is on the normalised Arabic name **and** the shabiya, never the name
alone: the census has سوق الجمعة in Murqub while the gazetteers place it in
Tripoli, and الزهراء exists in both Jafara and Wadi al Shatii. OSM features
already carry a COD-AB `adm2_pcode`, so the shabiya constraint costs nothing.

Where several OSM features share a name inside one shabiya, they are treated as
one place if they sit within `--cluster-km` of each other, which is the common
case of a settlement tagged as both a node and an area. If they are further
apart they are genuinely different places and the mahalla is recorded as
ambiguous rather than resolved to a guess.

Output is written under `data/external/` and not into the concordance itself,
because OpenStreetMap is ODbL: a database built from it carries share-alike
terms that the rest of this repository does not.
"""

import argparse
import csv
import json
import math
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_concordance import CODAB_TO_CENSUS, HDX, join_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "external" / "osm_places"
PROCESSED = ROOT / "data" / "processed"

ARABIC = re.compile(r"[؀-ۿ]")

# Rough ordering of OSM place tags, most settlement-like first. Used only to
# pick a representative among features that are already agreed to be one place.
PLACE_RANK = {"city": 0, "town": 1, "village": 2, "suburb": 3, "hamlet": 4,
              "isolated_dwelling": 5}


def centroid(geometry):
    """Representative point of an OSM feature."""
    kind = geometry["type"]
    if kind == "Point":
        return tuple(geometry["coordinates"][:2])
    rings = geometry["coordinates"]
    if kind == "MultiPolygon":
        rings = rings[0]
    ring = rings[0]
    return (sum(p[0] for p in ring) / len(ring),
            sum(p[1] for p in ring) / len(ring))


def km_between(a, b):
    """Great-circle distance in km, good enough for a clustering threshold."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def load_places(path):
    """Read the OSM populated places, keyed by (shabiya, normalised name)."""
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".geojson"))
            data = json.loads(archive.read(name))
    else:
        data = json.loads(path.read_text())

    places = defaultdict(list)
    for feature in data["features"]:
        properties = feature["properties"]
        name = properties.get("name_ar") or properties.get("name")
        if not name or not ARABIC.search(name):
            continue
        shabiya = CODAB_TO_CENSUS.get(properties.get("adm2_name"))
        if not shabiya:
            continue
        lon, lat = centroid(feature["geometry"])
        places[(shabiya, join_key(name))].append({
            "osm_id": properties["id"],
            "name_ar": name,
            "place": properties.get("place") or "",
            "lon": round(lon, 5),
            "lat": round(lat, 5),
        })
    return places


def resolve(candidates, cluster_km):
    """Return (chosen, status) for the OSM features matching one mahalla."""
    if len(candidates) == 1:
        return candidates[0], "single"
    far = any(km_between((a["lon"], a["lat"]), (b["lon"], b["lat"])) > cluster_km
              for i, a in enumerate(candidates) for b in candidates[i + 1:])
    if far:
        return None, "ambiguous"
    chosen = min(candidates, key=lambda c: (PLACE_RANK.get(c["place"], 9),
                                            c["osm_id"]))
    return chosen, "clustered"


def shabiya_centroids():
    """COD-AB's own centroid for each shabiya, for a sanity column on anchors."""
    if not HDX.exists():
        return {}
    workbook = openpyxl.load_workbook(HDX, read_only=True)
    rows = list(workbook["lby_adminpoints"].iter_rows(values_only=True))
    header = rows[0]
    out = {}
    for row in rows[1:]:
        if not row or str(row[header.index("admin_level")]) != "2":
            continue
        shabiya = CODAB_TO_CENSUS.get(row[header.index("adm2_name")])
        if shabiya:
            out[shabiya] = (float(row[header.index("x_coord")]),
                            float(row[header.index("y_coord")]))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--places", required=True,
                        help="hotosm_lby_populated_places geojson or its zip")
    parser.add_argument("--cluster-km", type=float, default=5.0,
                        help="same-name features closer than this are one place")
    args = parser.parse_args()

    places = load_places(Path(args.places))
    centroids = shabiya_centroids()
    with (PROCESSED / "concordance_mahalla.csv").open() as fh:
        mahallas = list(csv.DictReader(fh))

    rows = []
    counts = defaultdict(int)
    for record in mahallas:
        key = (record["shabiya_ar"], record["mahalla_key"])
        candidates = places.get(key, [])
        if not candidates:
            counts["unmatched"] += 1
            continue
        chosen, status = resolve(candidates, args.cluster_km)
        counts[status] += 1
        rows.append({
            "mahalla_id": record["mahalla_id"],
            "mahalla_ar": record["mahalla_ar"],
            "shabiya_ar": record["shabiya_ar"],
            "shabiya_en": record["shabiya_en"],
            "match_status": status,
            "candidates": len(candidates),
            "osm_id": chosen["osm_id"] if chosen else "",
            "osm_name_ar": chosen["name_ar"] if chosen else "",
            "osm_place_type": chosen["place"] if chosen else "",
            "lon": chosen["lon"] if chosen else "",
            "lat": chosen["lat"] if chosen else "",
            # Distance to the shabiya's centroid, for inspection only. Large
            # values are expected: several shabiyat exceed 70,000 km2 and are
            # long strips, so an edge settlement sits far from the centre and
            # can even be nearer a small neighbour's centroid. The authority for
            # which shabiya a point falls in is the COD-AB adm2_pcode already on
            # the OSM feature, not this distance.
            "distance_to_shabiya_centroid_km": (
                round(km_between((chosen["lon"], chosen["lat"]),
                                 centroids[record["shabiya_ar"]]))
                if chosen and record["shabiya_ar"] in centroids else ""),
            "osm_candidate_ids": ";".join(c["osm_id"] for c in candidates),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "mahalla_osm_anchors.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["mahalla_id"]))

    anchored = counts["single"] + counts["clustered"]
    print(f"{path.name:32s} {len(rows)} of {len(mahallas)} mahallas matched by "
          f"name within their own shabiya")
    print(f"{'':32s} {anchored} anchored to a point "
          f"({counts['single']} single, {counts['clustered']} clustered), "
          f"{counts['ambiguous']} left ambiguous")
    print(f"{'':32s} {counts['unmatched']} with no same-shabiya name match")


if __name__ == "__main__":
    main()
