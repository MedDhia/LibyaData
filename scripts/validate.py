#!/usr/bin/env python3
"""
Check the built datasets against the accounting identities and published totals
that the sources themselves assert. Run after any extraction change.

Exit code 1 if a check that should hold exactly does not.
"""

import json
import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "processed"
TOL = 0.15          # LYD millions, one decimal place of rounding
USD_TOL = 10.0

failures = []
notes = []


def check(name, residual, tol=TOL, exact=True):
    worst = float(residual.abs().max())
    bad = int((residual.abs() > tol).sum())
    status = "ok " if bad == 0 else ("FAIL" if exact else "note")
    print(f"  [{status}] {name:52s} max |resid| {worst:12,.2f}  breaches {bad}/{len(residual)}")
    if bad and exact:
        failures.append(f"{name}: {bad} breaches, worst {worst:,.2f}")
    elif bad:
        notes.append(f"{name}: {bad} breaches, worst {worst:,.2f}")


print("Central Bank of Libya, monetary statistics")
ms = pd.read_csv(OUT / "cbl_money_supply.csv")
mf = pd.read_csv(OUT / "cbl_money_supply_factors.csv")
mb = pd.read_csv(OUT / "cbl_monetary_base.csv")
bf = pd.read_csv(OUT / "cbl_monetary_base_factors.csv")
rr = pd.read_csv(OUT / "cbl_required_reserves.csv")

check("M1 = currency + demand deposits",
      ms.money_m1 - (ms.currency_in_circulation + ms.demand_deposits))
check("quasi money = time + saving deposits",
      ms.quasi_money - (ms.time_deposits + ms.saving_deposits))
check("M2 = M1 + quasi money", ms.money_supply_m2 - (ms.money_m1 + ms.quasi_money))
check("NFA total = central bank + commercial banks",
      mf.nfa_total - (mf.nfa_central_bank + mf.nfa_commercial_banks))
check("NDA total = treasury + other sectors + other items",
      mf.nda_total - (mf.net_claims_on_treasury + mf.claims_on_other_sectors
                      + mf.other_items_net))
check("M2 = NFA + NDA", mf.money_supply_m2 - (mf.nfa_total + mf.nda_total))
check("bank reserves = vault cash + deposits at CBL",
      mb.bank_reserves_total - (mb.cash_in_vault + mb.deposits_with_central_bank))
check("monetary base = currency + reserves + PE deposits",
      mb.monetary_base - (mb.currency_in_circulation + mb.bank_reserves_total
                          + mb.public_enterprise_demand_deposits))
check("base NDA = treasury + other + comm banks + other items",
      bf.nda_total - (bf.net_claims_on_treasury + bf.claims_on_other_sectors
                      + bf.claims_on_commercial_banks + bf.other_items_net))
check("monetary base = NFA + NDA", bf.monetary_base - (bf.net_foreign_assets + bf.nda_total))
check("reserve deposits total = demand + time", rr.deposits_total
      - (rr.demand_deposits + rr.time_deposits), exact=False)

print("\nCross-table agreement (source vintage differences, not errors)")
j = ms.merge(mf, on="date", suffixes=("_ms", "_mf"))
check("M2 agrees across the two money tables",
      j.money_supply_m2_ms - j.money_supply_m2_mf, exact=False)
j = ms.merge(mb, on="date", suffixes=("_ms", "_mb"))
check("currency agrees: money supply vs monetary base",
      j.currency_in_circulation_ms - j.currency_in_circulation_mb, exact=False)
j = mb.merge(bf, on="date", suffixes=("_mb", "_bf"))
check("monetary base agrees across its two tables",
      j.monetary_base_mb - j.monetary_base_bf, exact=False)
j = mf.merge(bf, on="date")
check("central bank NFA agrees across factor tables",
      j.nfa_central_bank - j.net_foreign_assets, exact=False)

print("\nCoverage")
for name, df in [("money supply", ms), ("money supply factors", mf),
                 ("monetary base", mb), ("monetary base factors", bf),
                 ("required reserves", rr)]:
    expected = pd.period_range(df.date.min()[:7], df.date.max()[:7], freq="M")
    got = pd.PeriodIndex(pd.to_datetime(df.date), freq="M")
    missing = sorted(set(expected) - set(got))
    status = "ok " if not missing else "FAIL"
    print(f"  [{status}] {name:52s} {len(df)} months, {len(missing)} gaps")
    if missing:
        failures.append(f"{name}: {len(missing)} missing months")

print("\nUses of foreign exchange")
bank = pd.read_csv(OUT / "cbl_fx_by_bank.csv")
purp = pd.read_csv(OUT / "cbl_fx_by_bank_purpose.csv")
for period in sorted(purp.period_end.unique()):
    year = int(period[:4])
    a = purp[(purp.period_end == period) & (purp.year == year)].value_usd.sum()
    b = bank[(bank.period_end == period) & (bank.year == year)].value_usd.sum()
    ok = abs(a - b) <= USD_TOL
    print(f"  [{'ok ' if ok else 'FAIL'}] {period}  by-purpose ${a:>16,.0f}  "
          f"by-bank ${b:>16,.0f}  diff ${a - b:>+8,.0f}")
    if not ok:
        failures.append(f"FX {period}: purpose and bank totals differ by {a - b:,.0f}")

print("\nConsumer prices")
cpi = pd.read_csv(OUT / "bsc_cpi_by_group.csv", dtype={"group_code": str})
gen = cpi[cpi.group_code == "00"]
dec23 = gen[(gen.year == 2023) & (gen.month == 12) & (gen.base_year == 2008)]
if len(dec23) == 1 and abs(float(dec23["index"].iloc[0]) - 296.9) < 0.05:
    print("  [ok ] December 2023 general index = 296.9, matching the BSC homepage")
else:
    failures.append("CPI: December 2023 does not match the BSC published 296.9")
    print("  [FAIL] December 2023 general index does not match the published 296.9")

for base, group in gen.groupby("base_year"):
    group = group.sort_values(["year", "month"])
    print(f"  [ok ] base {int(base)}=100: {len(group):3d} months "
          f"{group.date.iloc[0]} .. {group.date.iloc[-1]}")
unresolved = int(gen.base_year.isna().sum())
if unresolved:
    print(f"  [note] {unresolved} general-index months with an unresolved base year")
    notes.append(f"CPI: {unresolved} months with unresolved base year")
disputed = int(cpi.has_conflict.sum())
print(f"  [note] {disputed} observations flagged has_conflict "
      f"({int(gen.has_conflict.sum())} in the general index)")

print("\n2006 population census")
mah = pd.read_csv(OUT / "bsc_census_2006_mahalla.csv")
shb = pd.read_csv(OUT / "bsc_census_2006_shabiya.csv")
PUBLISHED_POPULATION = 5_657_692
PUBLISHED_AREA = 1_676_198

for total, parts in [
        ("libyan_hh_persons", ["libyan_hh_libyans", "libyan_hh_non_libyans"]),
        ("non_libyan_hh_persons", ["non_libyan_hh_libyans", "non_libyan_hh_non_libyans"]),
        ("households", ["libyan_hh_households", "non_libyan_hh_households"]),
        ("libyans", ["libyan_hh_libyans", "non_libyan_hh_libyans"]),
        ("non_libyans", ["libyan_hh_non_libyans", "non_libyan_hh_non_libyans"]),
        ("persons", ["libyan_hh_persons", "non_libyan_hh_persons"])]:
    residual = mah[total] - mah[parts].sum(axis=1)
    breaches = int((residual != 0).sum())
    # One row carries a misprint in the source; see the codebook.
    status = "ok " if breaches <= 1 else "FAIL"
    print(f"  [{status}] mahalla identity {total:26s} breaches {breaches}/{len(mah)}")
    if breaches > 1:
        failures.append(f"census identity {total}: {breaches} breaches")

if shb.persons.sum() == PUBLISHED_POPULATION:
    print(f"  [ok ] shabiya totals sum to {PUBLISHED_POPULATION:,}, "
          f"the published 2006 census population")
else:
    failures.append(f"census: shabiya totals sum to {shb.persons.sum():,}, "
                    f"not {PUBLISHED_POPULATION:,}")
    print(f"  [FAIL] shabiya totals sum to {shb.persons.sum():,}")

if shb.area_km2.sum() == PUBLISHED_AREA:
    print(f"  [ok ] shabiya areas sum to {PUBLISHED_AREA:,} km2, as printed")
else:
    failures.append(f"census: areas sum to {shb.area_km2.sum():,}, not {PUBLISHED_AREA:,}")
    print(f"  [FAIL] shabiya areas sum to {shb.area_km2.sum():,} km2")

if len(shb) == 22 and mah.mahalla_id.nunique() == len(mah):
    print(f"  [ok ] {len(mah)} mahallas across {len(shb)} shabiyat, keys unique")
else:
    failures.append("census: shabiya count or mahalla key uniqueness is wrong")
    print(f"  [FAIL] {len(mah)} mahallas, {len(shb)} shabiyat, "
          f"{mah.mahalla_id.nunique()} unique keys")

gap = shb.persons.sum() - mah.persons.sum()
print(f"  [note] mahalla sum is {gap:,} below the shabiya totals, "
      f"accounted for by one misprinted figure in the source")
notes.append(f"census: mahalla sum {gap:,} below shabiya totals (source misprint)")

print("\n2006 census, all 74 tables")
index = pd.read_csv(OUT / "bsc_census_2006_table_index.csv")
missing = sorted(set(range(1, 75)) - set(index.table_no))
if missing:
    failures.append(f"census tables: {len(missing)} not read: {missing}")
    print(f"  [FAIL] {len(index)}/74 tables read; missing {missing}")
else:
    print(f"  [ok ] all 74 tables read, "
          f"{index.volumes.min()}-{index.volumes.max()} volumes each")

checked = int(index.sex_identity_checked.sum())
breached = int(index.sex_identity_breached.sum())
if checked:
    rate = 100 * breached / checked
    status = "ok " if rate < 0.5 else "FAIL"
    print(f"  [{status}] male + female = total: {checked:,} checks, "
          f"{breached:,} breaches ({rate:.3f}%)")
    if rate >= 0.5:
        failures.append(f"census tables: sex identity breached on {rate:.2f}% of checks")
    if breached:
        notes.append(f"census tables: {breached} sex-identity breaches "
                     f"in {int((index.sex_identity_breached > 0).sum())} tables")

sections = sorted(OUT.glob("bsc_census_2006_cells_*.csv.gz"))
figures = 0
for path in sections:
    part = pd.read_csv(path, dtype={"row_group_ar": str, "row_group_en": str,
                                    "row_label_ar": str, "row_label_en": str})
    figures += len(part)
    if part.value.isna().any():
        failures.append(f"{path.name}: contains empty values")
print(f"  [ok ] {len(sections)} section files, {figures:,} figures, "
      f"{index.cells.sum():,} expected")

print("\nImported nighttime lights, and the shabiya concordance")
import json as _json
source = OUT.parent / "external" / "nighttime_lights" / "SOURCE.json"
if not source.exists():
    print("  [note] nighttime lights not imported; "
          "run scripts/import_nighttime_lights.py")
    notes.append("nighttime lights not imported")
else:
    meta = _json.loads(source.read_text())
    import hashlib as _hashlib
    root = OUT.parent.parent
    corrupt = []
    for entry in meta["manifest"]:
        path = root / entry["path"]
        if not path.exists():
            corrupt.append(entry["path"])
        elif _hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            corrupt.append(entry["path"])
    if corrupt:
        failures.append(f"nighttime lights: {len(corrupt)} files missing or altered")
        print(f"  [FAIL] {len(corrupt)} of {len(meta['manifest'])} files "
              f"missing or altered")
    else:
        print(f"  [ok ] {len(meta['manifest'])} files match their checksums, "
              f"commit {meta['source_commit'][:12]}")

    cross = pd.read_csv(OUT / "concordance_shabiya.csv")
    for column in ("gadm_name", "codab_pcode"):
        if column not in cross.columns:
            failures.append(f"concordance_shabiya.csv is missing {column}")
    zonal = pd.read_csv(OUT.parent / "external" / "nighttime_lights" /
                        "results" / "LBY_adm1_zonal.csv")
    census = pd.read_csv(OUT / "bsc_census_2006_shabiya.csv")
    if len(cross) != 22:
        failures.append(f"concordance: {len(cross)} units, expected 22")
    unmatched_gadm = set(zonal.name) - set(cross.gadm_name)
    unmatched_census = set(census.shabiya_ar) - set(cross.shabiya_ar)
    joined = zonal.merge(cross, left_on="name", right_on="gadm_name")
    joined = joined.merge(census, on="shabiya_ar")
    if unmatched_gadm or unmatched_census or len(joined) != len(zonal):
        failures.append("concordance: does not join every unit to the census")
        print(f"  [FAIL] concordance joins {len(joined)}/{len(zonal)} zonal rows; "
              f"unmatched {sorted(unmatched_gadm)} {sorted(unmatched_census)}")
    else:
        print(f"  [ok ] concordance joins all {len(joined)} zonal rows "
              f"({zonal.year.min()}-{zonal.year.max()}) to the census")
        print(f"  [note] units share names, not boundaries: national area differs "
              f"by 3.6% between GADM and the census")

print("\nGeographic concordance")
mahalla_cross = pd.read_csv(OUT / "concordance_mahalla.csv")
census_mahalla = pd.read_csv(OUT / "bsc_census_2006_mahalla.csv")

if (len(mahalla_cross) == len(census_mahalla)
        and set(mahalla_cross.mahalla_id) == set(census_mahalla.mahalla_id)):
    print(f"  [ok ] {len(mahalla_cross)} mahallas, ids match the census exactly")
else:
    failures.append("concordance_mahalla: ids do not match the census")
    print(f"  [FAIL] {len(mahalla_cross)} rows against "
          f"{len(census_mahalla)} census mahallas")

orphans = set(mahalla_cross.shabiya_ar) - set(cross.shabiya_ar)
if orphans:
    failures.append(f"concordance_mahalla: shabiyat not in the shabiya "
                    f"concordance: {sorted(orphans)}")
    print(f"  [FAIL] {len(orphans)} shabiyat missing from the shabiya concordance")
else:
    print(f"  [ok ] every mahalla resolves to one of the "
          f"{cross.shabiya_ar.nunique()} shabiyat, in all three naming systems")

baladiya = pd.read_csv(OUT / "concordance_baladiya.csv")
centres = pd.read_csv(OUT / "hnec_polling_centres_2021.csv")
UNRESOLVED = ("ambiguous", "not_established")
mapped = int((~mahalla_cross.baladiya_source.isin(UNRESOLVED)).sum())
ambiguous = int((mahalla_cross.baladiya_source == "ambiguous").sum())

if centres.centre_code.is_unique:
    print(f"  [ok ] {len(centres)} HNEC polling centres, codes unique, "
          f"{centres.baladiya_ar.nunique()} municipalities named")
else:
    failures.append("hnec polling centres: duplicate centre codes")
    print("  [FAIL] duplicate polling-centre codes")

stray = set(mahalla_cross.baladiya_ar.dropna()) - set(baladiya.baladiya_ar)
if stray:
    failures.append(f"concordance: baladiyat not in the baladiya file: "
                    f"{sorted(stray)[:5]}")
    print(f"  [FAIL] {len(stray)} mapped baladiyat missing from "
          f"concordance_baladiya.csv")
else:
    routes = mahalla_cross.baladiya_source.value_counts()
    print(f"  [ok ] {mapped} mahallas mapped to one baladiya, "
          f"{ambiguous} ambiguous, all naming a known municipality")
    print("  [note] by route: " + ", ".join(
        f"{count} {source}" for source, count in routes.items()
        if source not in UNRESOLVED))

# A baladiya a mahalla is mapped to must be one the sources actually name, and
# every mapped mahalla must carry a source that says how the link was made.
blank = mahalla_cross[(mahalla_cross.baladiya_ar.notna())
                      & (mahalla_cross.baladiya_source.isin(UNRESOLVED))]
if len(blank):
    failures.append(f"concordance: {len(blank)} mahallas carry a baladiya with "
                    f"no route")
    print(f"  [FAIL] {len(blank)} mahallas carry a baladiya with no route")
else:
    print(f"  [ok ] every mapped mahalla records the route that mapped it")

later_path = OUT / "hnec_centre_baladiya_2024_2025.csv"
if later_path.exists():
    later = pd.read_csv(later_path, dtype={"centre_code": str})
    outside = set(later.centre_code) - set(centres.centre_code.astype(str))
    if outside:
        failures.append(f"hnec 2024-2025: {len(outside)} centre codes outside "
                        f"the 2021 register")
        print(f"  [FAIL] {len(outside)} 2024-2025 centre codes are not in the "
              f"2021 register")
    else:
        print(f"  [ok ] all {later.centre_code.nunique()} centres restated in "
              f"2024-2025 are in the 2021 register "
              f"({later.baladiya_ar.nunique()} municipalities)")

# A mahalla may only take a baladiya whose inferred shabiya is its own.
placed = baladiya.dropna(subset=["shabiya_ar"]).set_index("baladiya_ar").shabiya_ar
joined = mahalla_cross[mahalla_cross.baladiya_ar.notna()]
mismatch = [r.mahalla_id for r in joined.itertuples()
            if placed.get(r.baladiya_ar, r.shabiya_ar) != r.shabiya_ar]
if mismatch:
    failures.append(f"concordance: {len(mismatch)} mahallas mapped across shabiyat")
    print(f"  [FAIL] {len(mismatch)} mahallas mapped to a baladiya in another shabiya")
else:
    print(f"  [ok ] every mapped mahalla and its baladiya sit in the same shabiya")

linked = int((mahalla_cross.match_method != "unmatched").sum())
dupes = int((mahalla_cross.name_unique_nationally == 0).sum())
print(f"  [note] {linked} mahallas linked to a COD-AB place; "
      f"{len(mahalla_cross) - linked} unmatched")
print(f"  [note] {dupes} mahalla names recur nationally, "
      f"{int((mahalla_cross.name_unique_in_shabiya == 0).sum())} within one shabiya")
notes.append(f"concordance: {len(mahalla_cross) - mapped - ambiguous} of "
             f"{len(mahalla_cross)} mahallas have no baladiya; "
             f"{int(baladiya.shabiya_ar.isna().sum())} baladiyat unplaced")

anchors_path = (OUT.parent / "external" / "osm_places" / "mahalla_osm_anchors.csv")
if anchors_path.exists():
    anchors = pd.read_csv(anchors_path)
    stray = set(anchors.mahalla_id) - set(mahalla_cross.mahalla_id)
    placed = anchors[anchors.lon.notna()]
    inside = placed.lon.between(9, 26).all() and placed.lat.between(19, 34).all()
    if stray or not inside:
        failures.append("osm anchors: unknown mahalla ids or coordinates "
                        "outside Libya")
        print(f"  [FAIL] {len(stray)} unknown ids; all inside Libya: {inside}")
    else:
        print(f"  [ok ] {len(placed)} OSM anchors, all inside Libya, "
              f"{int((anchors.match_status == 'ambiguous').sum())} left ambiguous")

# ---------------------------------------------------------------- OpenSanctions
os_dir = OUT.parent / "external" / "sanctions"
if (os_dir / "libya_entities.csv").exists():
    print("\nOpenSanctions, Libyan subgraph")
    nodes = pd.read_csv(os_dir / "libya_entities.csv")
    edges = pd.read_csv(os_dir / "libya_edges.csv")
    spells = pd.read_csv(os_dir / "libya_positions.csv")
    designations = pd.read_csv(os_dir / "libya_sanctions.csv")
    addresses = pd.read_csv(os_dir / "libya_addresses.csv")

    # Every edge endpoint must be a node, or the network is cut.
    ids = set(nodes.entity_id)
    loose = (set(edges.source_id) | set(edges.target_id)) - ids
    if loose:
        failures.append(f"opensanctions: {len(loose)} edge endpoints are not nodes")
        print(f"  [FAIL] {len(loose)} edge endpoints have no node row")
    else:
        print(f"  [ok ] {len(nodes)} nodes, {len(edges)} edges, every endpoint resolves")

    # Every route in is one of the four the extractor documents.
    ROUTES = {"country_tagged", "libyan_office", "accredited_to_libya",
              "tie_to_libya", "tie_via_multicountry_hub"}
    unknown = set(nodes.libya_link) - ROUTES
    if unknown or nodes.entity_id.duplicated().any():
        failures.append(f"opensanctions: unexpected route or duplicate id {unknown}")
        print(f"  [FAIL] routes {unknown}, duplicate ids "
              f"{int(nodes.entity_id.duplicated().sum())}")
    else:
        by_route = nodes.libya_link.value_counts().to_dict()
        print(f"  [ok ] ids unique, every node carries a documented route: {by_route}")

    # A foreign ambassador accredited to Libya must never be coded a Libyan official.
    envoys = nodes[nodes.libya_link == "accredited_to_libya"]
    if int(envoys.is_libyan_official.sum()):
        failures.append("opensanctions: foreign envoys coded as Libyan officials")
        print(f"  [FAIL] {int(envoys.is_libyan_official.sum())} envoys coded Libyan")
    else:
        print(f"  [ok ] {len(envoys)} envoys accredited to Libya, none coded "
              f"a Libyan official ({int(nodes.is_libyan_official.sum())} are)")

    # Everything placed on the map must sit in one of the 22 shabiyat.
    placed = nodes[nodes.shabiya_en.notna()]
    outside = set(placed.shabiya_en) - set(cross.shabiya_en)
    if outside:
        failures.append(f"opensanctions: shabiyat outside the concordance: {outside}")
        print(f"  [FAIL] {len(outside)} shabiyat not in the concordance")
    else:
        print(f"  [ok ] {len(placed)} of {len(nodes)} nodes placed in a shabiya, "
              f"all 22 names from the concordance")

    # A placed node must be a Libyan one, and must say how it was placed.
    foreign_placed = placed[~placed.countries.fillna("").str.split(";").apply(
        lambda cs: "ly" in cs)]
    unlabelled = placed[placed.place_matched_level.isna()
                        | placed.place_matched_script.isna()]
    if len(foreign_placed) or len(unlabelled):
        failures.append(f"opensanctions: {len(foreign_placed)} nodes not tagged Libyan "
                        f"carry a shabiya, {len(unlabelled)} placed without a level")
        print(f"  [FAIL] {len(foreign_placed)} non-Libyan nodes placed, "
              f"{len(unlabelled)} with no matched level")
    else:
        levels = placed.groupby(["place_matched_script",
                                 "place_matched_level"]).size().to_dict()
        print(f"  [ok ] every placed node is tagged Libyan and records how it was "
              f"matched {levels}")

    # An address stated to be in another country must not carry a shabiya.
    elsewhere = addresses[addresses.shabiya_en.notna()
                          & addresses.country.fillna("").str.contains(r"[a-z]")
                          & ~addresses.country.fillna("").str.split(";").apply(
                              lambda cs: "ly" in cs)]
    if len(elsewhere):
        failures.append(f"opensanctions: {len(elsewhere)} addresses in another "
                        f"country carry a Libyan shabiya")
        print(f"  [FAIL] {len(elsewhere)} foreign addresses placed in Libya")
    else:
        located = addresses[addresses.shabiya_en.notna()]
        print(f"  [ok ] {len(located)} of {len(addresses)} address records resolve, "
              f"none of them stated to be in another country")

    # Occupancy spells must name a person the node table knows.
    orphans = set(spells.person_id) - ids
    if orphans:
        failures.append(f"opensanctions: {len(orphans)} office spells name no node")
        print(f"  [FAIL] {len(orphans)} office spells name an unknown person")
    else:
        foreign = int((spells.is_foreign_posting == 1).sum())
        print(f"  [ok ] {len(spells)} office spells, {foreign} of them foreign "
              f"postings to Libya, every holder resolves")

    notes.append(f"opensanctions: {len(placed)} of {len(nodes)} nodes carry a shabiya; "
                 f"{len(designations)} designations by "
                 f"{designations.authority.nunique()} authorities")

# -------------------------------------------------------------------- Gazette
gz_dir = OUT / "gazette"
if (gz_dir / "gazette_decisions.csv").exists():
    print("\nOfficial Gazette, House of Representatives")
    gz_issues = pd.read_csv(gz_dir / "gazette_issues.csv")
    gz_decisions = pd.read_csv(gz_dir / "gazette_decisions.csv")
    gz_appointments = pd.read_csv(gz_dir / "gazette_appointments.csv")

    # Every decision must come from an issue the manifest lists.
    known = set(gz_issues.issue_id)
    stray = set(gz_decisions.issue_id) - known
    if stray:
        failures.append(f"gazette: {len(stray)} decisions cite an unknown issue")
        print(f"  [FAIL] {len(stray)} decisions cite an issue not in the manifest")
    else:
        read = int((gz_issues.read_by == "text").sum())
        print(f"  [ok ] {len(gz_issues)} issues, {read} with a text layer, "
              f"{len(gz_decisions)} decisions, every one from a listed issue")

    # An appointment row must be flagged as one and name an act.
    bad = gz_appointments[(gz_appointments.is_appointment != 1)
                          | gz_appointments.act_en.isna()]
    if len(bad):
        failures.append(f"gazette: {len(bad)} appointment rows carry no act")
        print(f"  [FAIL] {len(bad)} appointment rows are not flagged or name no act")
    else:
        named = int(gz_appointments.person_name.notna().sum())
        print(f"  [ok ] {len(gz_appointments)} appointment rows, all flagged and "
              f"acted, {named} carrying a personal name")

    # The dataset is one side of a split state, and must say so on every row.
    if gz_decisions.publishing_authority.nunique() != 1:
        failures.append("gazette: rows disagree on the publishing authority")
        print("  [FAIL] more than one publishing authority in one file")
    else:
        print(f"  [ok ] every row names its publishing authority: "
              f"{gz_decisions.publishing_authority.iloc[0]}")

    # A signed date, where printed, must fall inside the issue's own year.
    signed = gz_decisions[gz_decisions.signed_gregorian.notna()]
    years = pd.to_datetime(signed.signed_gregorian, errors="coerce").dt.year
    outside = int(((years < 2011) | (years > 2027)).sum())
    if outside:
        failures.append(f"gazette: {outside} signature dates outside 2011-2027")
        print(f"  [FAIL] {outside} signature dates fall outside 2011-2027")
    else:
        print(f"  [ok ] {len(signed)} decisions carry a signature date, all plausible")

    # Anything placed on the map must be one of the 22 shabiyat, and the two
    # geographies must stay apart: where a decision was signed is not where its
    # office has authority.
    for column, label in (("issued_at_shabiya_en", "signature"),
                          ("office_shabiya_en", "office")):
        named = gz_decisions[gz_decisions[column].notna()]
        outside = set(named[column]) - set(cross.shabiya_en)
        if outside:
            failures.append(f"gazette: {label} shabiyat outside the concordance: "
                            f"{outside}")
            print(f"  [FAIL] {len(outside)} {label} shabiyat not in the concordance")
        else:
            print(f"  [ok ] {len(named)} of {len(gz_decisions)} decisions carry a "
                  f"{label} shabiya, all from the concordance")

    # A decision either carries a signature place with the level it matched at,
    # or says why it carries none.
    statuses = {"signed", "no signature line printed",
                "no body text: a table-of-contents entry",
                "place not in the gazetteer"}
    unknown = set(gz_decisions.issued_at_status.dropna()) - statuses
    signed_rows = gz_decisions[gz_decisions.issued_at_status == "signed"]
    inconsistent = gz_decisions[(gz_decisions.issued_at_status == "signed")
                                != gz_decisions.issued_at_shabiya_en.notna()]
    if unknown or len(inconsistent) or signed_rows.issued_at_matched_level.isna().any():
        failures.append(f"gazette: issued_at_status {unknown} or the status "
                        f"disagrees with the place column")
        print(f"  [FAIL] signature status values {unknown}, "
              f"{len(inconsistent)} rows where status and place disagree")
    else:
        why = gz_decisions.issued_at_status.value_counts().to_dict()
        print(f"  [ok ] every decision is signed with a placed city or says why "
              f"not {why}")

    # The two calendars on the signature line must agree, and where they do not
    # the gazette printed them that way: the tabular Islamic calendar is within
    # a day or two of the Umm al-Qura one the gazette follows.
    both = gz_decisions[gz_decisions.signed_gregorian.notna()
                        & gz_decisions.signed_hijri.notna()]
    gaps = []
    for _, row in both.iterrows():
        hy, hm, hd = (int(x) for x in str(row.signed_hijri).split("-"))
        jdn = hd + 29 * (hm - 1) + hm // 2 + 354 * (hy - 1) + (3 + 11 * hy) // 30
        stamp = pd.Timestamp(row.signed_gregorian)
        gaps.append(jdn + 1948439 - (stamp.toordinal() + 1721425))
    far = [g for g in gaps if abs(g) > 3]
    if len(far) > len(gaps) // 8:
        failures.append(f"gazette: {len(far)} of {len(gaps)} signature dates "
                        f"disagree across the two calendars")
        print(f"  [FAIL] {len(far)} of {len(gaps)} Hijri and Gregorian dates "
              f"disagree by more than three days")
    else:
        print(f"  [ok ] {len(gaps) - len(far)} of {len(gaps)} decisions carrying "
              f"both dates agree across the calendars to within three days")

    scopes = {"national", "subnational", "bilateral"}
    unknown = set(gz_decisions.office_scope) - scopes
    mismatch = gz_decisions[(gz_decisions.office_scope == "subnational")
                            & gz_decisions.office_shabiya_en.isna()]
    if unknown or len(mismatch):
        failures.append(f"gazette: office_scope {unknown or 'subnational with no place'}")
        print(f"  [FAIL] office_scope values {unknown}, "
              f"{len(mismatch)} subnational rows with no place")
    else:
        print(f"  [ok ] every decision carries a documented office_scope: "
              f"{gz_decisions.office_scope.value_counts().to_dict()}")

    notes.append(f"gazette: {len(signed)} of {len(gz_decisions)} decisions carry a "
                 f"signature date, {len(far)} of them printed with a Hijri and a "
                 f"Gregorian date that are not the same day")

    acts = gz_decisions[gz_decisions.act_en.notna()].act_en.value_counts().to_dict()
    notes.append(f"gazette: {int(gz_decisions.is_appointment.sum())} of "
                 f"{len(gz_decisions)} decisions are appointments {acts}; "
                 f"House of Representatives only, not the Tripoli government")

# ---------------------------------------------------- Municipal councils, HNEC
mun_dir = OUT / "municipal"
if (mun_dir / "municipal_councils.csv").exists():
    print("\nMunicipal councils, HNEC")
    mun_decisions = pd.read_csv(mun_dir / "municipal_decisions.csv")
    mun_councils = pd.read_csv(mun_dir / "municipal_councils.csv")

    # Every council must come from a decision in the decision table.
    keys = set(zip(mun_decisions.decision_number, mun_decisions.decision_year))
    stray = set(zip(mun_councils.decision_number,
                    mun_councils.decision_year)) - keys
    if stray:
        failures.append(f"municipal: {len(stray)} councils cite an unlisted decision")
        print(f"  [FAIL] {len(stray)} councils cite a decision not in the table")
    else:
        print(f"  [ok ] {len(mun_decisions)} decisions, {len(mun_councils)} councils "
              f"formed, every council from a listed decision")

    # Unlike the gazette, this record is subnational: a council with no shabiya
    # is a gap worth seeing, not a normal row.
    placed = mun_councils[mun_councils.shabiya_en.notna()]
    outside = set(placed.shabiya_en) - set(cross.shabiya_en)
    if outside:
        failures.append(f"municipal: shabiyat outside the concordance: {outside}")
        print(f"  [FAIL] {len(outside)} shabiyat not in the concordance")
    else:
        print(f"  [ok ] {len(placed)} of {len(mun_councils)} councils resolve to a "
              f"shabiya, all from the concordance "
              f"{placed.shabiya_en.value_counts().to_dict()}")

    # The member names are not in the data, and the row must say so.
    if int(mun_councils.members_listed.sum()) or mun_councils.scan_url.isna().any():
        failures.append("municipal: a council claims members or has no scan")
        print("  [FAIL] members_listed is not zero, or a council has no scan url")
    else:
        print(f"  [ok ] all {len(mun_councils)} councils record members_listed=0 "
              f"and point at the scan HNEC published")

    # A municipality the decisions name either resolves or is on record as
    # unresolved: the column must agree with the count beside it.
    named = mun_decisions.municipalities_ar.fillna("")
    missing = mun_decisions.municipalities_unresolved.fillna("")
    counted = named.apply(lambda s: len([n for n in s.split(";") if n]))
    absent = missing.apply(lambda s: len([n for n in s.split(";") if n]))
    off = mun_decisions[counted - absent != mun_decisions.municipalities_named]
    if len(off):
        failures.append(f"municipal: {len(off)} decisions miscount their "
                        f"municipalities")
        print(f"  [FAIL] {len(off)} decisions where named minus unresolved is not "
              f"the resolved count")
    else:
        every = {n for s in named for n in s.split(";") if n}
        gone = {n for s in missing for n in s.split(";") if n}
        print(f"  [ok ] {len(every)} municipalities named across the decisions, "
              f"{len(every) - len(gone)} resolved, {len(gone)} recorded unresolved")

    coded = mun_decisions[mun_decisions.act_en.notna()]
    grouped = mun_decisions[mun_decisions.electoral_group.notna()]
    notes.append(f"municipal: {len(every) - len(gone)} of {len(every)} municipalities "
                 f"named across the decisions resolve to a shabiya")
    notes.append(f"municipal: {len(mun_councils)} councils formed; "
                 f"{len(grouped)} of {len(mun_decisions)} decisions name an electoral "
                 f"group, none of them a formation decision; "
                 f"{len(mun_decisions) - len(coded)} decisions carry no act in their "
                 f"title; member names are page scans and are not extracted")

bnf_dir = OUT / "bnf"
if (bnf_dir / "bnf_libya_records.csv").exists():
    print("\nBibliothèque nationale de France, Libya holdings")
    bnf = pd.read_csv(bnf_dir / "bnf_libya_records.csv")
    bnf_data = pd.read_csv(bnf_dir / "bnf_libya_data.csv")

    # Every record must be identifiable in the catalogue it came from.
    missing = bnf[bnf.catalogue_url.isna() | ~bnf.catalogue_url.fillna("").str.contains(
        "catalogue.bnf.fr")]
    if len(missing):
        failures.append(f"bnf: {len(missing)} records carry no catalogue URL")
        print(f"  [FAIL] {len(missing)} records with no catalogue URL")
    else:
        print(f"  [ok ] {len(bnf)} catalogue records, every one resolvable at the BnF")

    # The data subset must be exactly the data-bearing classes, and nothing else.
    classes = {"population_census", "statistical_abstract", "trade_returns",
               "gazetteer", "scientific_mission", "official_serial"}
    flagged = set(bnf[bnf.is_data_source == 1].document_class)
    carried = set(bnf_data.document_class)
    if flagged - classes or carried != flagged or len(bnf_data) != int(
            bnf.is_data_source.sum()):
        failures.append(f"bnf: data subset disagrees with is_data_source "
                        f"{flagged - classes or carried ^ flagged}")
        print(f"  [FAIL] data classes {flagged - classes}, "
              f"{len(bnf_data)} rows against {int(bnf.is_data_source.sum())} flagged")
    else:
        print(f"  [ok ] {len(bnf_data)} data-bearing records, every class documented "
              f"{bnf_data.document_class.value_counts().to_dict()}")

    # A Gallica link means digitised; the reverse does not hold, because the
    # catalogue's UNIMARC service fails for part of the set and only the ARK is
    # lost. Anything claiming a link without the flag is a coding error.
    linked = bnf[bnf.gallica_url.notna()]
    unflagged = linked[linked.is_digitised != 1]
    eras = set(bnf.era.dropna()) - {"ottoman", "italian", "allied_administration",
                                    "kingdom", "jamahiriya", "post_2011"}
    if len(unflagged) or eras:
        failures.append(f"bnf: {len(unflagged)} linked records not flagged digitised, "
                        f"undocumented eras {eras}")
        print(f"  [FAIL] {len(unflagged)} Gallica links on rows not marked digitised, "
              f"eras {eras}")
    else:
        digitised = int((bnf.is_digitised == 1).sum())
        print(f"  [ok ] {digitised} digitised, {len(linked)} carrying a Gallica ARK, "
              f"every era documented")

    notes.append(f"bnf: {len(bnf)} catalogue records name Libya, "
                 f"{int((bnf.is_digitised == 1).sum())} digitised, "
                 f"{len(bnf_data)} carrying data "
                 f"({int((bnf_data.is_digitised == 1).sum())} of those digitised); "
                 f"gallica.bnf.fr blocks this address, the catalogue does not")

istat = OUT.parent / "raw" / "istat" / "manifest.json"
if istat.exists():
    print("\nISTAT digital library, Italian colonial statistics")
    book = json.loads(istat.read_text())
    entries = book["files"]
    bad = [e for e in entries
           if not e["url"].startswith("https://ebiblio.istat.it/digibib/")
           or e["group"] not in {"libya_named", "yearbook"} or e["bytes"] <= 0]
    if bad:
        failures.append(f"istat: {len(bad)} manifest entries malformed")
        print(f"  [FAIL] {len(bad)} entries with a bad URL, group or size")
    else:
        named = sum(1 for e in entries if e["group"] == "libya_named")
        print(f"  [ok ] {len(entries)} files, {named} named for Libya or the "
              f"colonies, every URL in the ISTAT library")

    # The yearbook run is the Libyan panel; a gap in it is a gap in the panel.
    years = {e["path"].split("ASI")[-1].replace(".pdf", "")
             for e in entries if e["group"] == "yearbook"}
    missing = [y for y in book["yearbook_years"] if y not in years]
    if missing:
        failures.append(f"istat: yearbook volumes missing {missing}")
        print(f"  [FAIL] {len(missing)} yearbook volumes not in the manifest: "
              f"{missing}")
    else:
        print(f"  [ok ] the yearbook run is complete, {len(years)} volumes "
              f"1911-1943")

    notes.append(f"istat: {len(entries)} files, "
                 f"{sum(e['bytes'] for e in entries) / 1e6:.0f} MB, listed not "
                 f"downloaded; three Libyan population counts (1921, 1931, 1936) "
                 f"and the Italian yearbook run 1911-1943")

loc_dir = OUT / "istat"
if (loc_dir / "libya_localities_1936.csv").exists():
    print("\n1936 Italian census, Libyan localities")
    loc = pd.read_csv(loc_dir / "libya_localities_1936.csv")
    circ = pd.read_csv(loc_dir / "libya_circoscrizioni_1936.csv")

    # Anything placed must sit in one of the 22 shabiyat.
    placed = loc[loc.shabiya_en.notna()]
    outside = set(placed.shabiya_en) - set(cross.shabiya_en)
    if outside:
        failures.append(f"1936: shabiyat outside the concordance: {outside}")
        print(f"  [FAIL] {len(outside)} shabiyat not in the concordance")
    else:
        print(f"  [ok ] {len(loc)} localities, {len(placed)} placed in a shabiya, "
              f"all 22 names from the concordance")

    # A locality's shabiya comes from its circumscription and nowhere else.
    seats = dict(zip(circ.circoscrizione_it, circ.shabiya_en))
    wrong = [row.locality_it for row in placed.itertuples()
             if seats.get(row.circoscrizione_it) != row.shabiya_en]
    if wrong:
        failures.append(f"1936: {len(wrong)} localities disagree with their "
                        f"circumscription")
        print(f"  [FAIL] {len(wrong)} localities placed away from their "
              f"circumscription")
    else:
        routes = placed.shabiya_matched_level.value_counts().to_dict()
        print(f"  [ok ] every placed locality takes its circumscription's "
              f"shabiya {routes}")

    # The join to 2006 is one to one, and every row says which rule reached it.
    joined = loc[loc.mahalla_id.notna()]
    doubled = joined.mahalla_id.duplicated().sum()
    ruleless = int(loc.match_rule.isna().sum())
    if doubled or ruleless:
        failures.append(f"1936: {doubled} mahallas claimed twice, {ruleless} rows "
                        f"with no match rule")
        print(f"  [FAIL] {doubled} mahallas claimed by two localities, "
              f"{ruleless} rows with no rule")
    else:
        rules = joined.match_rule.value_counts().to_dict()
        print(f"  [ok ] {len(joined)} localities join a 2006 mahalla, one to one "
              f"{rules}")

    notes.append(f"1936: {len(placed)} of {len(loc)} localities placed in a "
                 f"shabiya, {len(joined)} joined to a 2006 mahalla; the rest are "
                 f"wells, lodges and farms the later censuses do not count")

print()
for n in notes:
    print(f"note: {n}")
if failures:
    print(f"\n{len(failures)} FAILURE(S):")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("All exact checks passed.")
