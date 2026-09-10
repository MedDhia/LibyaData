#!/usr/bin/env bash
# Download the reference geography this repository's concordance is built from.
#
# 1. COD-AB, the common operational dataset of Libyan administrative boundaries.
#    P-codes and a 78-place gazetteer. CC BY-IGO. Sourced from UNITAR-UNOSAT,
#    the Libyan Bureau of Statistics, WFP, the Global Logistics Cluster and IOM.
#    https://data.humdata.org/dataset/cod-ab-lby
#
# 2. Populated Places of Libya, from OpenStreetMap via HOT. ODbL.
#    https://data.humdata.org/dataset/hotosm_lby_populated_places
#
# Neither is committed; both are re-downloadable and their terms differ from the
# rest of this repository. Checksums are printed so a rebuild can be checked.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw/hdx
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'

resource_url() {   # dataset id, filename suffix
  curl -fsSL --max-time 60 -A "$UA" \
    "https://data.humdata.org/api/3/action/package_show?id=$1" \
  | python3 -c "
import json,sys
for r in json.load(sys.stdin)['result']['resources']:
    if r['name'].endswith('$2'):
        print(r['url']); break
"
}

curl -fsSL --max-time 180 -A "$UA" -o data/raw/hdx/lby_admin_boundaries.xlsx \
  "$(resource_url cod-ab-lby .xlsx)"
curl -fsSL --max-time 300 -A "$UA" -o data/raw/hdx/hotosm_lby_populated_places.zip \
  "$(resource_url hotosm_lby_populated_places osm_geojson.zip)"

for f in data/raw/hdx/*; do
  printf '%-52s %9s bytes  sha256 %s\n' "$f" "$(stat -c%s "$f")" \
    "$(sha256sum "$f" | cut -d' ' -f1)"
done
echo "next: python3 scripts/build_concordance.py"
echo "      python3 scripts/match_osm_places.py --places data/raw/hdx/hotosm_lby_populated_places.zip"
