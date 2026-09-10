#!/usr/bin/env python3
"""
Build the geographic concordance: stable identifiers for Libya's subnational
units, and the links between the naming systems this repository has to join.

Three naming systems are in play, and no two of them agree:

  * the **2006 census**, which names 22 shabiyat and 667 mahallas within them;
  * **GADM 4.1**, whose admin-1 layer is those same 22 units under different
    romanisations (Darnah, Surt, Misratah) and with post-2006 boundaries;
  * **COD-AB**, the humanitarian common operational dataset, which P-codes the
    same 22 units but names four of them after their capital city instead
    (Tobruk for Butnan, Ejdabia for Al Wahat, Zwara for Nuqat al Khams, Ubari
    for Wadi al Hayaa).

Outputs:
  concordance_shabiya.csv    22 first-level units across all three systems
  concordance_mahalla.csv    667 localities, keyed and linked as far as the
                             evidence goes

## Mahalla to baladiya

The census predates the 2013 municipal reorganisation and no published crosswalk
relates its 667 mahallat to today's baladiyat. Neither GADM 4.1 nor COD-AB
carries a Libyan boundary layer below the 22 shabiyat, so it cannot be derived
geometrically either.

HNEC's 2021 polling-centre register supplies the missing link directly: each
centre is listed with its locality **and** its municipality (see
`scripts/extract_hnec_polling_centres.py`). Joining the census's mahalla to that
register's locality gives the mapping.

The join is constrained to the shabiya, never made on name alone, because names
repeat: سوق الجمعة is a Murqub mahalla in the census and a Tripoli locality in
the gazetteers, and الزهراء exists in both Jafara and Wadi al Shatii. HNEC does
not state the shabiya, so it is inferred first: a census mahalla whose name
occurs in only one shabiya votes, weighted by polling centres, for the shabiya
of every baladiya it appears in, and each baladiya takes the shabiya with the
most votes. A mahalla is then linked only to a baladiya whose inferred shabiya
matches its own.

Mahallas matching more than one baladiya even after that are recorded as
ambiguous with their candidates listed, not resolved to a guess. Mahallas the
register does not name are left `not_established`.
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import normalise_name  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed"
HNEC_PAIRS = OUT / "hnec_locality_baladiya.csv"
HDX = ROOT / "data" / "raw" / "hdx" / "lby_admin_boundaries.xlsx"

# GADM 4.1 admin-1 name -> census shabiya. Same 22 units, different romanisation.
GADM_TO_CENSUS = {
    "Al Butnan": "البطنان", "Al Jabal al Akhdar": "الجبل الأخضر",
    "Al Jabal al Gharbi": "الجبل الغربي", "Al Jifarah": "الجفارة",
    "Al Jufrah": "الجفرة", "Al Kufrah": "الكفرة", "Al Marj": "المرج",
    "Al Marqab": "المرقب", "Al Wahat": "الواحات", "An Nuqat al Khams": "النقاط الخمس",
    "Az Zawiyah": "الزاوية", "Benghazi": "بنغازي", "Darnah": "درنة", "Ghat": "غات",
    "Misratah": "مصراته", "Murzuq": "مرزق", "Nalut": "نالوت", "Sabha": "سبها",
    "Surt": "سرت", "Tripoli": "طرابلس", "Wadi al Hayat": "وادي الحياة",
    "Wadi ash Shati'": "وادي الشاطئ",
}

# COD-AB admin-2 name -> census shabiya. The same 22 units again, but four are
# named for their capital rather than the region.
CODAB_TO_CENSUS = {
    "Derna": "درنة", "Almarj": "المرج", "Benghazi": "بنغازي",
    "Tobruk": "البطنان",                # capital of Butnan
    "Ejdabia": "الواحات",               # Ajdabiya, capital of Al Wahat
    "Al Jabal Al Akhdar": "الجبل الأخضر", "Alkufra": "الكفرة", "Sirt": "سرت",
    "Nalut": "نالوت", "Almargeb": "المرقب", "Tripoli": "طرابلس",
    "Aljfara": "الجفارة", "Azzawya": "الزاوية", "Misrata": "مصراته",
    "Zwara": "النقاط الخمس",            # Zuwara, capital of Nuqat al Khams
    "Al Jabal Al Gharbi": "الجبل الغربي", "Aljufra": "الجفرة",
    "Wadi Ashshati": "وادي الشاطئ", "Sebha": "سبها",
    "Ubari": "وادي الحياة",             # Ubari, capital of Wadi al Hayaa
    "Murzuq": "مرزق", "Ghat": "غات",
}


def join_key(name):
    """Normalise an Arabic place name into a key that survives spelling drift.

    Folds the alef and ya variants and ta marbuta, drops the definite article
    and all spacing. Sources differ on every one of these: the census writes
    مصراته where GADM romanises Misratah, COD-AB writes درنه for درنة.

    Also folds lam-alef to alef-lam. Several of these PDFs emit the lam-alef
    ligature with its two letters the wrong way round, so العجيلات is extracted
    as العجيالت, and the two forms would otherwise never meet. Folding gains 17
    further matches against the census and merges no distinct names.
    """
    text = normalise_name(str(name))
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"[ىي]", "ي", text)
    text = text.replace("ة", "ه")
    text = re.sub(r"^ال", "", text)
    text = re.sub(r"\s+", "", text)
    return text.replace("لا", "ال")


def infer_baladiya_shabiya(pairs, mahallas):
    """Infer each baladiya's shabiya from the census mahallas it contains.

    HNEC's register names a locality and its municipality but not the shabiya.
    A census mahalla whose name occurs in only one shabiya is unambiguous
    evidence, so those vote — weighted by how many polling centres back them —
    and each baladiya takes the shabiya with the most votes.
    """
    by_name = defaultdict(set)
    for record in mahallas:
        by_name[join_key(record["mahalla_ar"])].add(record["shabiya_ar"])

    votes = defaultdict(Counter)
    for pair in pairs:
        shabiyat = by_name.get(join_key(pair["mahalla_ar"]))
        if shabiyat and len(shabiyat) == 1:
            votes[join_key(pair["baladiya_ar"])][next(iter(shabiyat))] += int(
                pair["polling_centres"])

    inferred = {}
    for baladiya, counted in votes.items():
        shabiya, top = counted.most_common(1)[0]
        inferred[baladiya] = {"shabiya_ar": shabiya, "votes": top,
                              "total_votes": sum(counted.values()),
                              "unanimous": int(top == sum(counted.values()))}
    return inferred


def read_sheet(workbook, sheet):
    rows = list(workbook[sheet].iter_rows(values_only=True))
    header = rows[0]
    return header, [r for r in rows[1:] if r and r[0]]


def load_codab():
    """Return (admin-2 units, gazetteer places) from the COD-AB workbook."""
    if not HDX.exists():
        sys.exit(f"missing {HDX}. Run scripts/download_hdx_codab.sh first.")
    workbook = openpyxl.load_workbook(HDX, read_only=True)

    header, body = read_sheet(workbook, "lby_admin2")
    units = [{
        "pcode": row[header.index("adm2_pcode")],
        "name_en": row[header.index("adm2_name")],
        "name_ar": row[header.index("adm2_name1")],
        "area_km2": float(row[header.index("area_sqkm")]),
    } for row in body]

    header, body = read_sheet(workbook, "lby_populatedplaces")
    places = [{
        "pcode": row[header.index("pcode")],
        "name_en": row[header.index("featurename_en")],
        "name_ar": row[header.index("featurename_ar")],
        "adm2_en": row[header.index("adm2_en")],
    } for row in body]
    return units, places


def build_shabiya(codab_units):
    census_path = OUT / "bsc_census_2006_shabiya.csv"
    with census_path.open() as fh:
        census = {row["shabiya_ar"]: row for row in csv.DictReader(fh)}

    gadm_by_census = {v: k for k, v in GADM_TO_CENSUS.items()}
    codab_by_census = {}
    for unit in codab_units:
        target = CODAB_TO_CENSUS.get(unit["name_en"])
        if target is None:
            sys.exit(f"COD-AB unit not mapped: {unit['name_en']}")
        codab_by_census[target] = unit

    for name, mapping in (("census", census), ("GADM", gadm_by_census),
                          ("COD-AB", codab_by_census)):
        missing = sorted(set(census) - set(mapping))
        if missing:
            sys.exit(f"{name} does not cover every shabiya: {missing}")

    rows = []
    for arabic, record in sorted(census.items()):
        codab = codab_by_census[arabic]
        rows.append({
            "shabiya_ar": arabic,
            "shabiya_en": record["shabiya_en"],
            "gadm_name": gadm_by_census[arabic],
            "gadm_gid": "",
            "codab_pcode": codab["pcode"],
            "codab_name_en": codab["name_en"],
            "codab_name_ar": codab["name_ar"],
            "codab_renamed_for_capital": int(codab["name_en"] not in
                                             (record["shabiya_en"], arabic)
                                             and arabic in
                                             ("البطنان", "الواحات",
                                              "النقاط الخمس", "وادي الحياة")),
            "census_area_km2": record["area_km2"],
            "codab_area_km2": round(codab["area_km2"], 2),
            "census_persons_2006": record["persons"],
            "census_mahalla_count": record["mahalla_count"],
        })

    # GADM gids come from the imported nighttime-lights tables, when present.
    aridity = (ROOT / "data" / "external" / "nighttime_lights" / "results"
               / "LBY_adm1_aridity.csv")
    if aridity.exists():
        with aridity.open() as fh:
            gids = {r["name"]: r["gid"] for r in csv.DictReader(fh)}
        for row in rows:
            row["gadm_gid"] = gids.get(row["gadm_name"], "")

    path = OUT / "concordance_shabiya.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:34s} {len(rows)} units across census, GADM and COD-AB")
    return rows


def build_mahalla(shabiya_rows, places):
    with (OUT / "bsc_census_2006_mahalla.csv").open() as fh:
        mahallas = list(csv.DictReader(fh))
    by_shabiya = {r["shabiya_ar"]: r for r in shabiya_rows}

    pairs = []
    if HNEC_PAIRS.exists():
        with HNEC_PAIRS.open() as fh:
            pairs = list(csv.DictReader(fh))
    inferred = infer_baladiya_shabiya(pairs, mahallas)
    by_locality = defaultdict(list)
    for pair in pairs:
        by_locality[join_key(pair["mahalla_ar"])].append(pair)
    write_baladiya(pairs, inferred)

    # The gazetteer is keyed to COD-AB's own admin-2 names.
    gazetteer = {}
    for place in places:
        shabiya = CODAB_TO_CENSUS.get(place["adm2_en"])
        if shabiya:
            gazetteer.setdefault((shabiya, join_key(place["name_ar"])), []).append(place)

    with_baladiya = [0, 0]
    keys = Counter(join_key(r["mahalla_ar"]) for r in mahallas)
    keys_in_shabiya = Counter((r["shabiya_ar"], join_key(r["mahalla_ar"]))
                              for r in mahallas)

    rows, linked = [], 0
    for record in mahallas:
        key = join_key(record["mahalla_ar"])
        parent = by_shabiya[record["shabiya_ar"]]
        candidates = gazetteer.get((record["shabiya_ar"], key), [])
        # Only a single candidate inside the same shabiya counts as a link.
        place = candidates[0] if len(candidates) == 1 else None
        if place:
            linked += 1
        # Only baladiyat inferred to sit in this mahalla's own shabiya count.
        consistent = {p["baladiya_ar"] for p in by_locality.get(key, [])
                      if inferred.get(join_key(p["baladiya_ar"]), {})
                      .get("shabiya_ar") == record["shabiya_ar"]}
        if len(consistent) == 1:
            baladiya, baladiya_source = consistent.pop(), "hnec_polling_centres_2021"
        elif consistent:
            baladiya, baladiya_source = "", "ambiguous"
        else:
            baladiya, baladiya_source = "", "not_established"
        if baladiya:
            with_baladiya[0] += 1
        elif baladiya_source == "ambiguous":
            with_baladiya[1] += 1

        rows.append({
            "mahalla_id": record["mahalla_id"],
            "mahalla_ar": record["mahalla_ar"],
            "mahalla_key": key,
            "shabiya_ar": record["shabiya_ar"],
            "shabiya_en": record["shabiya_en"],
            "shabiya_gadm_name": parent["gadm_name"],
            "shabiya_codab_pcode": parent["codab_pcode"],
            "name_unique_nationally": int(keys[key] == 1),
            "name_unique_in_shabiya": int(
                keys_in_shabiya[(record["shabiya_ar"], key)] == 1),
            "codab_place_pcode": place["pcode"] if place else "",
            "codab_place_en": place["name_en"] if place else "",
            "codab_place_ar": place["name_ar"] if place else "",
            "match_method": "codab_gazetteer_same_shabiya" if place else "unmatched",
            "baladiya_ar": baladiya,
            "baladiya_source": baladiya_source,
            "baladiya_candidates": ";".join(sorted(
                {p["baladiya_ar"] for p in by_locality.get(key, [])})),
            "census_persons_2006": record["persons"],
            "census_households_2006": record["households"],
        })

    path = OUT / "concordance_mahalla.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    duplicated = sum(1 for r in rows if not r["name_unique_nationally"])
    in_shabiya = sum(1 for r in rows if not r["name_unique_in_shabiya"])
    print(f"{path.name:34s} {len(rows)} mahallas; {linked} linked to a COD-AB "
          f"place, {len(rows) - linked} unmatched")
    print(f"{'':34s} {duplicated} share a name with another mahalla nationally, "
          f"{in_shabiya} within their own shabiya")
    print(f"{'':34s} {with_baladiya[0]} mapped to one baladiya, "
          f"{with_baladiya[1]} ambiguous, "
          f"{len(rows) - sum(with_baladiya)} not established")
    return rows


def write_baladiya(pairs, inferred):
    """The municipalities HNEC's register names, with their inferred shabiya."""
    if not pairs:
        return
    localities = defaultdict(set)
    centres = Counter()
    names = {}
    for pair in pairs:
        key = join_key(pair["baladiya_ar"])
        names.setdefault(key, pair["baladiya_ar"])
        localities[key].add(pair["mahalla_ar"])
        centres[key] += int(pair["polling_centres"])

    rows = []
    for key, name in sorted(names.items(), key=lambda kv: kv[1]):
        guess = inferred.get(key, {})
        rows.append({
            "baladiya_ar": name,
            "shabiya_ar": guess.get("shabiya_ar", ""),
            "shabiya_inferred_from": "census_mahalla_votes" if guess else "",
            "inference_unanimous": guess.get("unanimous", ""),
            "localities": len(localities[key]),
            "polling_centres": centres[key],
        })
    path = OUT / "concordance_baladiya.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    placed = sum(1 for r in rows if r["shabiya_ar"])
    print(f"{path.name:34s} {len(rows)} baladiyat from HNEC; {placed} placed in a "
          f"shabiya ({sum(1 for r in rows if r['inference_unanimous'] == 1)} unanimous)")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    codab_units, places = load_codab()
    shabiya_rows = build_shabiya(codab_units)
    build_mahalla(shabiya_rows, places)
    if not HNEC_PAIRS.exists():
        print("\nHNEC register absent, so no baladiya mapping: run "
              "scripts/extract_hnec_polling_centres.py first.")


if __name__ == "__main__":
    main()
