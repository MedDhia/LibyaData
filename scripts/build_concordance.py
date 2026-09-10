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

Two later HNEC collections restate the municipality of a subset of the same
polling centres, keyed on the centre code (see
`scripts/extract_hnec_municipal_baladiyat.py`). They do two things here. They
merge the municipality spellings: two of the 24 register documents embed a font
whose text layer drops and transposes letters, printing رست for سرت and طربق for
طبرق, and two names that share a polling centre and differ by at most two
characters are the same municipality. And they carry a municipality for centres
whose 2021 locality was mangled beyond matching.

The census's own naming then supplies three further routes, each recorded under
its own `baladiya_source` so that a user who wants only the exact evidence can
keep it:

  * a compound name — الشمالية / زوارة, الوسط \\ جادو — is a part of the place
    after the separator, so the register is asked about that place;
  * a name that is a register locality plus a direction — قمينس الشرقية,
    الصابري الغربي — is asked about without the direction;
  * a locality that only the damaged documents name is matched to the census
    name one character away from it, and only when that pairing is the single
    possibility in both directions and the census name matches nothing exactly.

Mahallas matching more than one baladiya even after that are recorded as
ambiguous with their candidates listed, not resolved to a guess. Mahallas no
route reaches are left `not_established`.
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
HNEC_REGISTER = OUT / "hnec_polling_centres_2021.csv"
HNEC_LATER = OUT / "hnec_centre_baladiya_2024_2025.csv"
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


# Directions a census mahalla's name is qualified with. Stripping one leaves the
# settlement the register names: قمينس الشرقية and قمينس الغربية are both in
# قمينس, الصابري الشرقي and الصابري الغربي both in بنغازي.
DIRECTIONS = ["الشرقية", "الغربية", "الشمالية", "الجنوبية", "الوسطى", "القبلية",
              "البحرية", "الشرقي", "الغربي", "الشمالي", "الجنوبي", "القبلي",
              "البحري", "الوسط"]

# Words that name a part rather than a place, so they are never asked about on
# their own: الوادي \ ككلة is in ككلة, and every shabiya has a المركز.
PART_KEYS = {join_key(word) for word in
             DIRECTIONS + ["المركز", "الوادي", "العين", "القصبة", "المدينة"]}

# Two municipality names this far apart in a shared polling centre are one
# municipality misspelt, not two municipalities. رست and سرت differ by two.
SPELLING_EDITS = 2


def edit_distance(first, second, limit):
    """Levenshtein distance, reported as limit + 1 once it exceeds the limit."""
    if abs(len(first) - len(second)) > limit:
        return limit + 1
    previous = list(range(len(second) + 1))
    for i, a in enumerate(first, 1):
        current = [i]
        for j, b in enumerate(second, 1):
            current.append(min(previous[j] + 1, current[-1] + 1,
                               previous[j - 1] + (a != b)))
        previous = current
    return min(previous[-1], limit + 1)


# How much a spelling of a municipality's name is to be trusted, by where it was
# read. The 2025 file names are WordPress titles and never passed through a PDF
# font; the 2021 register is the primary source; the card-distribution
# statistics visibly substitute Latin letters into Arabic words.
SPELLING_RANK = {"municipal_2025": 3, "polling_centres_2021": 2,
                 "card_distribution": 1}

ARABIC_ONLY = re.compile(r"^[\u0620-\u064a\u0670-\u06d3 ]+$")


def canonical_baladiyat(register, later):
    """Map every municipality spelling to one name per municipality.

    Two of the 24 register documents were read through a font that drops and
    transposes letters, so the same municipality is written طربق in one document
    and طبرق in another, رست and سرت, توكرا and توكره. Left alone these split a
    municipality in two and make its localities look ambiguous.

    Two spellings are the same municipality when they are at most
    SPELLING_EDITS apart **and** a polling centre or a locality is filed under
    both. A locality belongs to one municipality, so co-occurrence is what
    separates a misspelling from a neighbour with a similar name; distance alone
    would merge درج into درنة.

    The surviving name is the best-attested spelling in the group, by the rank
    of the source it was read from, then by whether it is Arabic throughout,
    then by how many documents print it.
    """
    parent = {}

    def find(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    spellings = defaultdict(lambda: {"rank": 0, "documents": set(), "rows": 0})
    together = defaultdict(set)
    for row in register + later:
        collection = row.get("source_collection", "polling_centres_2021")
        key, name = join_key(row["baladiya_ar"]), row["baladiya_ar"]
        record = spellings[(key, name)]
        record["rank"] = max(record["rank"], SPELLING_RANK[collection])
        record["documents"].add(row.get("source_document", collection))
        record["rows"] += 1
        find(key)
        if row.get("centre_code"):
            together[("centre", row["centre_code"])].add(key)
        together[("locality", join_key(row["mahalla_ar"]))].add(key)

    for keys in together.values():
        keys = sorted(keys)
        for i, first in enumerate(keys):
            for second in keys[i + 1:]:
                if edit_distance(first, second, SPELLING_EDITS) <= SPELLING_EDITS:
                    parent[find(first)] = find(second)

    groups = defaultdict(list)
    for (key, name), record in spellings.items():
        groups[find(key)].append((key, name, record))

    canonical, merged = {}, {}
    for members in groups.values():
        _, name, _ = max(members, key=lambda m: (
            m[2]["rank"], bool(ARABIC_ONLY.match(m[1])), len(m[2]["documents"]),
            m[2]["rows"], m[1]))
        for member_key, member_name, _ in members:
            canonical[member_key] = name
            merged.setdefault(name, set()).add(member_name)
    return canonical, merged


def name_variants(name):
    """Other names to ask the register about, when the census name is unknown."""
    text = normalise_name(name)
    variants = []
    for separator in ("/", "\\"):
        if separator in text:
            head, tail = (part.strip() for part in text.split(separator, 1))
            # The part after the separator is the settlement, the part before it
            # is which part of it, but a few are written the other way round.
            variants += [part for part in (tail, head)
                         if part and join_key(part) not in PART_KEYS]
            break
    for direction in DIRECTIONS:
        if text.endswith(direction):
            stem = text[:-len(direction)].strip()
            if len(stem) > 2:
                variants.append(stem)
                break
    return variants


def infer_baladiya_shabiya(pairs, mahallas):
    """Infer each baladiya's shabiya from the census mahallas it contains.

    HNEC's register names a locality and its municipality but not the shabiya.
    A census mahalla whose name occurs in only one shabiya is unambiguous
    evidence, so those vote — weighted by how many polling centres back them —
    and each baladiya takes the shabiya with the most votes. A statement from a
    2024 or 2025 document is one centre and votes once.
    """
    by_name = defaultdict(set)
    for record in mahallas:
        by_name[join_key(record["mahalla_ar"])].add(record["shabiya_ar"])

    votes = defaultdict(Counter)
    for pair in pairs:
        shabiyat = by_name.get(join_key(pair["mahalla_ar"]))
        if shabiyat and len(shabiyat) == 1:
            votes[join_key(pair["baladiya_ar"])][next(iter(shabiyat))] += int(
                pair.get("polling_centres", 1))

    inferred = {}
    for baladiya, counted in votes.items():
        shabiya, top = counted.most_common(1)[0]
        inferred[baladiya] = {"shabiya_ar": shabiya, "votes": top,
                              "total_votes": sum(counted.values()),
                              "unanimous": int(top == sum(counted.values()))}
    return inferred


class Resolver:
    """Which baladiya a census mahalla sits in, and on what evidence.

    Five routes, tried in order and each labelled in `baladiya_source`, so the
    weaker ones can be dropped:

      hnec_polling_centres_2021   the 2021 register names the locality
      hnec_municipal_2024_2025    a later document names one of its centres
      hnec_name_variant           the register names the settlement the census
                                  name qualifies or is part of
      hnec_city_2021              the register names it as a city rather than a
                                  locality, so the mahalla is that city's core
      hnec_near_match             the register names it one character away

    Every route is confined to the mahalla's own shabiya, because names repeat:
    سوق الجمعة is a Murqub mahalla and a Tripoli locality, الزهراء is in both
    Jafara and Wadi al Shatii.
    """

    # A census name and a register locality this far apart are the same place,
    # once nothing else can claim either of them.
    NEAR_EDITS = 1

    def __init__(self, pairs, later, inferred, mahallas):
        self.inferred = inferred
        self.register = defaultdict(set)
        self.municipal = defaultdict(set)
        self.city = defaultdict(set)
        for pair in pairs:
            self._add(self.register, pair["mahalla_ar"], pair["baladiya_ar"])
            self._add(self.city, pair["city_ar"], pair["baladiya_ar"])
        for row in later:
            self._add(self.municipal, row["mahalla_ar"], row["baladiya_ar"])
            self._add(self.city, row["city_ar"], row["baladiya_ar"])
        self.named = defaultdict(set)
        for index in (self.register, self.municipal, self.city):
            for key, names in index.items():
                self.named[key] |= names
        self.near = self._near_matches(mahallas)

    def _add(self, index, locality, baladiya):
        """Record a locality-municipality pair under the baladiya's shabiya."""
        shabiya = self.inferred.get(join_key(baladiya), {}).get("shabiya_ar")
        if locality and shabiya:
            index[(shabiya, join_key(locality))].add(baladiya)

    @staticmethod
    def _only(index, key):
        found = index.get(key, ())
        return next(iter(found)) if len(found) == 1 else None

    def _near_matches(self, mahallas):
        """Pair each unclaimed census name with the locality one edit away.

        The register's locality names come partly from documents whose font
        dropped letters, so سيدي حسين is printed سيدي حسي and بنينة is بنينا.
        A pairing is accepted only when the census name matches no locality
        exactly, the locality matches no census name exactly, and each is the
        other's only candidate, which is what stops الحمدية from absorbing the
        separate الحميدية.
        """
        census = defaultdict(set)
        for record in mahallas:
            census[record["shabiya_ar"]].add(join_key(record["mahalla_ar"]))

        orphans = defaultdict(list)
        for shabiya, key in self.named:
            if key not in census[shabiya]:
                orphans[shabiya].append(key)

        forward, backward = defaultdict(list), Counter()
        for shabiya, keys in census.items():
            for key in keys:
                if (shabiya, key) in self.named:
                    continue
                for other in orphans[shabiya]:
                    if edit_distance(key, other, self.NEAR_EDITS) <= self.NEAR_EDITS:
                        forward[(shabiya, key)].append(other)
                        backward[(shabiya, other)] += 1

        near = {}
        for (shabiya, key), others in forward.items():
            if len(others) != 1 or backward[(shabiya, others[0])] != 1:
                continue
            baladiya = self._only(self.named, (shabiya, others[0]))
            if baladiya:
                near[(shabiya, key)] = baladiya
        return near

    def candidates(self, record):
        """Every baladiya any route offers, for the record of what was rejected."""
        shabiya, key = record["shabiya_ar"], join_key(record["mahalla_ar"])
        found = set(self.named.get((shabiya, key), ()))
        for variant in name_variants(record["mahalla_ar"]):
            found |= self.named.get((shabiya, join_key(variant)), set())
        if (shabiya, key) in self.near:
            found.add(self.near[(shabiya, key)])
        return found

    def resolve(self, record):
        """Return (baladiya, source) for one census mahalla."""
        shabiya, key = record["shabiya_ar"], join_key(record["mahalla_ar"])
        for index, source in ((self.register, "hnec_polling_centres_2021"),
                              (self.municipal, "hnec_municipal_2024_2025")):
            found = self._only(index, (shabiya, key))
            if found:
                return found, source
        for variant in name_variants(record["mahalla_ar"]):
            found = self._only(self.named, (shabiya, join_key(variant)))
            if found:
                return found, "hnec_name_variant"
        found = self._only(self.city, (shabiya, key))
        if found:
            return found, "hnec_city_2021"
        if (shabiya, key) in self.near:
            return self.near[(shabiya, key)], "hnec_near_match"
        if self.named.get((shabiya, key)):
            return "", "ambiguous"
        return "", "not_established"


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

    pairs, register, later = [], [], []
    for path, target in ((HNEC_PAIRS, pairs), (HNEC_REGISTER, register),
                         (HNEC_LATER, later)):
        if path.exists():
            with path.open() as fh:
                target += list(csv.DictReader(fh))

    canonical, spellings = canonical_baladiyat(register, later)
    for row in pairs + register + later:
        row["baladiya_ar"] = canonical.get(join_key(row["baladiya_ar"]),
                                           row["baladiya_ar"])

    inferred = infer_baladiya_shabiya(pairs + later, mahallas)
    resolver = Resolver(pairs, later, inferred, mahallas)
    write_baladiya(pairs, later, inferred, spellings)

    # The gazetteer is keyed to COD-AB's own admin-2 names.
    gazetteer = {}
    for place in places:
        shabiya = CODAB_TO_CENSUS.get(place["adm2_en"])
        if shabiya:
            gazetteer.setdefault((shabiya, join_key(place["name_ar"])), []).append(place)

    routes = Counter()
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
        baladiya, baladiya_source = resolver.resolve(record)
        routes[baladiya_source] += 1

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
                resolver.candidates(record))),
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
    mapped = sum(count for source, count in routes.items()
                 if source not in ("ambiguous", "not_established"))
    print(f"{'':34s} {mapped} mapped to one baladiya, "
          f"{routes['ambiguous']} ambiguous, "
          f"{routes['not_established']} not established")
    for source, count in routes.most_common():
        if source not in ("ambiguous", "not_established"):
            print(f"{'':38s} {count:4d} {source}")
    return rows


def write_baladiya(pairs, later, inferred, spellings):
    """The municipalities HNEC names, with their inferred shabiya."""
    if not pairs and not later:
        return
    localities = defaultdict(set)
    centres_2021, centres_later = Counter(), Counter()
    names = {}
    for pair in pairs:
        key = join_key(pair["baladiya_ar"])
        names.setdefault(key, pair["baladiya_ar"])
        localities[key].add(pair["mahalla_ar"])
        centres_2021[key] += int(pair["polling_centres"])
    for row in later:
        key = join_key(row["baladiya_ar"])
        names.setdefault(key, row["baladiya_ar"])
        localities[key].add(row["mahalla_ar"])
        centres_later[key] += 1

    rows = []
    for key, name in sorted(names.items(), key=lambda kv: kv[1]):
        guess = inferred.get(key, {})
        rows.append({
            "baladiya_ar": name,
            "shabiya_ar": guess.get("shabiya_ar", ""),
            "shabiya_inferred_from": "census_mahalla_votes" if guess else "",
            "inference_unanimous": guess.get("unanimous", ""),
            "localities": len(localities[key]),
            "polling_centres_2021": centres_2021[key],
            "centres_restated_2024_2025": centres_later[key],
            "spellings": ";".join(sorted(spellings.get(name, {name}))),
        })
    path = OUT / "concordance_baladiya.csv"
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    placed = sum(1 for r in rows if r["shabiya_ar"])
    later_only = sum(1 for r in rows if not r["polling_centres_2021"])
    print(f"{path.name:34s} {len(rows)} baladiyat from HNEC; {placed} placed in a "
          f"shabiya ({sum(1 for r in rows if r['inference_unanimous'] == 1)} unanimous)")
    print(f"{'':34s} {later_only} named only by the 2024-2025 documents")


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
