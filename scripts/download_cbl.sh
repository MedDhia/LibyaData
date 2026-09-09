#!/usr/bin/env bash
# Download the Central Bank of Libya source PDFs that the extraction scripts read.
#
#   scripts/download_cbl.sh
#
# Monetary and banking statistics land in data/raw/cbl/, the uses-of-foreign-
# exchange releases in data/raw/cbl_fx/. Both directories are gitignored; the
# checksums of what was actually read are recorded in the manifests written to
# data/processed/ by the extraction scripts.
set -euo pipefail

cd "$(dirname "$0")/.."
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'

mkdir -p data/raw/cbl data/raw/cbl_fx

fetch_listing() {
  curl -fsSL --max-time 60 -A "$UA" "$1"
}

# The listing pages link each release; the CBL renames files between releases,
# so links are read from the page rather than constructed.
echo "Monetary and banking statistics"
i=0
fetch_listing "https://cbl.gov.ly/en/monetary-and-banking/" \
  | grep -oE 'href="[^"]+\.pdf"' | sed 's/href="//;s/"$//' \
  | grep -v micifaf | grep -v 'حوكمة' | sort -u \
  | while read -r path; do
      i=$((i + 1))
      out="data/raw/cbl/cbl_mb_${i}.pdf"
      curl -fsSL --max-time 120 -A "$UA" -o "$out" "https://cbl.gov.ly${path}"
      printf '  %s  %s bytes\n' "$out" "$(stat -c%s "$out")"
    done

echo "Uses of foreign exchange"
fetch_listing "https://cbl.gov.ly/en/uses-of-foreign-exch/" \
  | grep -oE 'href="[^"]+\.pdf"' | sed 's/href="//;s/"$//' \
  | grep -iE 'uses-of-fx' | sort -u \
  | while read -r path; do
      out="data/raw/cbl_fx/$(basename "$path")"
      curl -fsSL --max-time 120 -A "$UA" -o "$out" "https://cbl.gov.ly${path}"
      printf '  %s  %s bytes\n' "$out" "$(stat -c%s "$out")"
    done

echo "Done. Next: python3 scripts/extract_cbl_monetary.py && python3 scripts/extract_cbl_fx.py"
