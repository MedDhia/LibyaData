#!/usr/bin/env python3
"""
Cut the Libyan subgraph out of the OpenSanctions bulk collections.

Input is the two global FollowTheMoney streams fetched by
`scripts/download_opensanctions.py`: 1.9m PEP entities and 293k sanctions
entities, 2.24m lines in all. Neither is published as a country subset, so the
Libyan part is selected here, and how it is selected is the whole method.

## Selecting Libya

Three routes in, each recorded in `libya_link` so a user can keep or drop it:

  country_tagged        the entity itself carries `ly` in country, nationality,
                        citizenship, birthCountry, jurisdiction, mainCountry or
                        registrationCountry.
  libyan_office         the entity holds, or has held, a Libyan Position whose
                        topics are governmental. This is the route that matters:
                        the PEP collection describes people through the office
                        they hold, and most Libyan officeholders carry no country
                        property of their own.
  accredited_to_libya   the entity holds a Position whose country is `ly` but
                        whose topic is `role.diplo`. These are foreign
                        ambassadors to Libya, and 63 of the 156 office spells in
                        the source are exactly that. They are Libyan only in the
                        sense of being posted there, so they are separated rather
                        than counted as Libyan officials.
  tie_to_libya          the entity is not Libyan by any test but is one edge away
                        from something that is: a spouse, a business partner, a
                        company a Libyan official directs.

Expansion to `tie_to_libya` runs only through **Libya-specific** seeds, meaning
those whose country set is `ly` and nothing else, or who hold a Libyan office.
Sanctions lists record every country an organisation operates in, so the Islamic
Revolutionary Guard Corps arrives tagged `ir;ly;sy`; expanding through it imports
138 Iranian entities that have nothing to do with Libya. Such a hub is kept as a
node, with its edges to other Libyan entities, and is not used to pull in
strangers. A degree cap backs the rule up, and both are reported.

Selection is a fixed five-pass stream, never loading a file into memory:

  1  entities carrying `ly`, and the ids and topics of Libyan Positions
  2  Occupancy edges pointing at those Positions, adding their holders
  3  every edge touching the seed set, adding the entity on the other side of
     an edge from a Libya-specific seed
  4  materialise every entity now wanted, plus the Address, Identification and
     Position records they reference
  5  Sanction records naming any of them

## Coding

FollowTheMoney gives a schema and a topic vocabulary; both are kept verbatim and
also reduced to flat columns, because `role.pep` and `gov.national` inside a
semicolon-joined list are not something a regression reads. Positions become one
row per person per office per spell, with start and end dates, which is the
officeholder table an elite-survival design needs.

## Geography

Libyan geography here is thin and has to be said so: an entity's birthPlace or
address is free text, often just "Libya". Four fields are read for a place, in
order of how directly each states one: birthPlace, the address on the entity or
on an Address record it points at, the `subnationalArea` of an office held, and
the office name itself, which in this source often carries the city. Where a
place is named, it is matched against this repository's own concordance — the 22 shabiyat under their census,
GADM and COD-AB romanisations, the COD-AB gazetteer places, and an explicit
alias table for the romanisations that recur in sanctions lists (Misurata,
Misratah, Tarabulus, Banghazi, Surt). A match assigns the shabiya and its COD-AB
pcode; anything else is left empty rather than guessed, and the rate is reported.

**Licence: CC BY-NC 4.0**, so output goes to `data/external/opensanctions/`
beside a NOTICE, not into `data/processed/`.

Outputs, all under data/external/opensanctions/:
  libya_entities.csv    one row per node, coded
  libya_edges.csv       one row per relationship
  libya_positions.csv   one row per person, office and spell
  libya_addresses.csv   address records, with the shabiya where one resolves
  libya_sanctions.csv   one row per designation
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "opensanctions"
OUT = ROOT / "data" / "external" / "opensanctions"
PROCESSED = ROOT / "data" / "processed"

COLLECTIONS = ("peps", "sanctions")
LIBYA = "ly"

# Properties that make an entity Libyan in its own right.
COUNTRY_PROPS = ("country", "nationality", "citizenship", "birthCountry",
                 "jurisdiction", "mainCountry", "registrationCountry")

# FollowTheMoney edge schemata, with the property holding each endpoint. Taken
# from the model's own `edge` declaration rather than assumed.
EDGES = {
    "Occupancy": ("holder", "post"), "Family": ("person", "relative"),
    "Associate": ("person", "associate"), "UnknownLink": ("subject", "object"),
    "Ownership": ("owner", "asset"), "Directorship": ("director", "organization"),
    "Control": ("controller", "controlled"), "Employment": ("employee", "employer"),
    "Membership": ("member", "organization"), "Representation": ("agent", "client"),
    "Succession": ("predecessor", "successor"), "Payment": ("payer", "beneficiary"),
    "Debt": ("debtor", "creditor"), "ContractAward": ("supplier", "contract"),
    "CourtCaseParty": ("party", "case"), "ProjectParticipant": ("participant", "project"),
    "Documentation": ("entity", "document"),
}
# Occupancy is a person-to-office statement, not a social tie; it is written to
# libya_positions.csv instead and excluded from the network edge list.
SOCIAL_EDGES = tuple(k for k in EDGES if k != "Occupancy")

# Topic prefixes reduced to flat indicator columns.
TOPIC_FLAGS = {
    "role.pep": "is_pep", "role.rca": "is_relative_or_associate",
    "role.diplo": "is_diplomat", "role.judge": "is_judge",
    "role.oligarch": "is_oligarch", "sanction": "is_sanctioned",
    "sanction.linked": "is_sanction_linked", "sanction.counter": "is_counter_sanctioned",
    "export.control": "is_export_controlled", "poi": "is_person_of_interest",
    "gov.head": "is_head_of_state_or_government",
}
CRIME = "crime"
GOV = "gov."
DIPLO = "role.diplo"

# A seed with more edges than this is a hub whose Libyan tag is one operational
# country among several, not an identity. Kept as a node, not expanded through.
HUB_DEGREE = 25

# Schemas that are entities in their own right. Passport, Identification,
# Address and Sanction describe an entity rather than being one, and are written
# to their own files or folded into columns.
NODE_SCHEMAS = ("Person", "Company", "Organization", "LegalEntity", "PublicBody",
                "Position", "Vessel", "Airplane", "Security", "Trust", "Asset")


def norm(text):
    """Casefold, strip accents and punctuation, for gazetteer matching."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z\s]", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


# Romanisations that recur in sanctions and PEP lists and are not in any of the
# three naming systems the concordance already carries.
ALIASES = {
    "tripoli": "طرابلس", "tarabulus": "طرابلس", "tarabulous": "طرابلس",
    "benghazi": "بنغازي", "banghazi": "بنغازي", "bengasi": "بنغازي",
    "benghasi": "بنغازي", "bengazi": "بنغازي",
    "misrata": "مصراته", "misratah": "مصراته", "misurata": "مصراته",
    "musrata": "مصراته", "misratha": "مصراته",
    "sirte": "سرت", "sirt": "سرت", "surt": "سرت", "sirta": "سرت",
    "sabha": "سبها", "sebha": "سبها", "sabhah": "سبها", "subha": "سبها",
    "derna": "درنة", "darnah": "درنة", "darna": "درنة",
    "tobruk": "البطنان", "tubruq": "البطنان", "tobruq": "البطنان",
    "ajdabiya": "الواحات", "ajdabiyah": "الواحات", "agedabia": "الواحات",
    "ejdabia": "الواحات", "jalu": "الواحات",
    "bayda": "الجبل الأخضر", "al bayda": "الجبل الأخضر", "beida": "الجبل الأخضر",
    "shahat": "الجبل الأخضر", "cyrene": "الجبل الأخضر",
    "zawiya": "الزاوية", "zawiyah": "الزاوية", "azzawiya": "الزاوية",
    "zuwara": "النقاط الخمس", "zuwarah": "النقاط الخمس", "zwara": "النقاط الخمس",
    "zintan": "الجبل الغربي", "gharyan": "الجبل الغربي", "gharian": "الجبل الغربي",
    "yefren": "الجبل الغربي", "nalut": "نالوت", "ghadames": "نالوت",
    "khums": "المرقب", "al khums": "المرقب", "homs": "المرقب",
    "zliten": "مصراته", "bani walid": "مصراته", "beni walid": "مصراته",
    "murzuq": "مرزق", "murzuk": "مرزق", "ubari": "وادي الحياة",
    "ghat": "غات", "kufra": "الكفرة", "al kufrah": "الكفرة", "koufra": "الكفرة",
    "brak": "وادي الشاطئ", "sokna": "الجفرة", "hun": "الجفرة", "waddan": "الجفرة",
    "marj": "المرج", "al marj": "المرج", "tocra": "المرج",
    "sabratha": "النقاط الخمس", "surman": "الزاوية", "gharyan city": "الجبل الغربي",
}


def gazetteer():
    """Place name to (shabiya_ar, shabiya_en, codab_pcode), Latin script.

    Built from this repository's own concordance so the three naming systems
    already reconciled there are all accepted, plus the alias table above.
    """
    path = PROCESSED / "concordance_shabiya.csv"
    if not path.exists():
        sys.exit(f"missing {path}. Run scripts/build_concordance.py first.")
    with path.open() as fh:
        shabiyat = list(csv.DictReader(fh))
    by_arabic = {r["shabiya_ar"]: r for r in shabiyat}

    places = {}
    for row in shabiyat:
        for name in (row["shabiya_en"], row["gadm_name"], row["codab_name_en"],
                     row["shabiya_ar"]):
            if name:
                places[norm(name) or name] = row
    for alias, arabic in ALIASES.items():
        row = by_arabic.get(arabic)
        if row is None:
            sys.exit(f"alias {alias} points at an unknown shabiya: {arabic}")
        places.setdefault(norm(alias), row)

    # COD-AB gazetteer places that the mahalla concordance resolved, which carry
    # their own romanisation and their parent shabiya.
    path = PROCESSED / "concordance_mahalla.csv"
    if path.exists():
        with path.open() as fh:
            for row in csv.DictReader(fh):
                if row["codab_place_en"] and row["shabiya_ar"] in by_arabic:
                    places.setdefault(norm(row["codab_place_en"]),
                                      by_arabic[row["shabiya_ar"]])
    return places


def locate(text, places):
    """Return (shabiya row, matched token) for a free-text place, or (None, '')."""
    if not text:
        return None, ""
    clean = norm(text)
    if not clean:
        return None, ""
    # Longest name first, so "wadi al hayaa" is not shadowed by "wadi".
    for name in sorted(places, key=len, reverse=True):
        if len(name) < 4:
            continue
        if re.search(rf"(?:^|\s){re.escape(name)}(?:$|\s)", clean):
            return places[name], name
    return None, ""


def values(entity, prop):
    return entity.get("properties", {}).get(prop, [])


def first(entity, prop):
    got = values(entity, prop)
    return got[0] if got else ""


def stream(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def is_libyan(entity):
    """Which country property, if any, makes this entity Libyan."""
    for prop in COUNTRY_PROPS:
        if LIBYA in values(entity, prop):
            return prop
    return ""


def endpoints(entity):
    """(source id, target id) for an edge entity, or (None, None)."""
    pair = EDGES.get(entity["schema"])
    if not pair:
        return None, None
    return first(entity, pair[0]), first(entity, pair[1])


def select(paths):
    """The selection passes. Returns (seeds, neighbours, edges, occupancies, notes)."""
    seeds, positions_ly = {}, {}
    for collection, path in paths.items():
        for entity in stream(path):
            prop = is_libyan(entity)
            if prop:
                countries = {c for p in COUNTRY_PROPS for c in values(entity, p)}
                seeds.setdefault(entity["id"],
                                 ["country_tagged", prop, frozenset(countries)])
                if entity["schema"] == "Position":
                    positions_ly[entity["id"]] = set(values(entity, "topics"))
    print(f"  pass 1  {len(seeds)} entities carry ly, "
          f"{len(positions_ly)} of them are Libyan offices", flush=True)

    occupancies, diplomatic = [], 0
    for collection, path in paths.items():
        for entity in stream(path):
            if entity["schema"] != "Occupancy":
                continue
            holder, post = endpoints(entity)
            if post not in positions_ly or not holder:
                continue
            occupancies.append(entity)
            # A Libyan Position tagged role.diplo is a foreign embassy posting.
            diplo = DIPLO in positions_ly[post]
            diplomatic += diplo
            route = "accredited_to_libya" if diplo else "libyan_office"
            if holder in seeds and seeds[holder][0] == "country_tagged":
                continue
            seeds.setdefault(holder, [route, "post", frozenset()])
    print(f"  pass 2  {len(occupancies)} office spells, {diplomatic} of them "
          f"foreign postings to Libya; seed set now {len(seeds)}", flush=True)

    # Only Libya-specific seeds pull in strangers.
    def expandable(seed):
        route, _, countries = seed
        if route in ("libyan_office", "accredited_to_libya"):
            return route == "libyan_office"
        return not countries or countries == {LIBYA}

    degree = Counter()
    for collection, path in paths.items():
        for entity in stream(path):
            if entity["schema"] not in EDGES:
                continue
            source, target = endpoints(entity)
            for node in (source, target):
                if node in seeds:
                    degree[node] += 1

    hubs = {i for i, d in degree.items() if d > HUB_DEGREE}
    edges, neighbours = [], {}
    for collection, path in paths.items():
        for entity in stream(path):
            if entity["schema"] not in EDGES:
                continue
            source, target = endpoints(entity)
            if not source or not target:
                continue
            if source not in seeds and target not in seeds:
                continue
            edges.append(entity)
            for near, far in ((source, target), (target, source)):
                if near not in seeds or far in seeds:
                    continue
                # The edge is kept either way, so the network is not silently
                # cut; what changes is how the entity on the far side is
                # labelled, and a hub neighbour can be filtered out in one step.
                direct = expandable(seeds[near]) and near not in hubs
                route = "tie_to_libya" if direct else "tie_via_multicountry_hub"
                current = neighbours.get(far)
                if current is None or (direct and current[0] != "tie_to_libya"):
                    neighbours[far] = [route, f"{entity['schema']}:{near}",
                                       frozenset()]
    held_back = sum(1 for i in seeds if not expandable(seeds[i]) or i in hubs)
    via_hub = sum(1 for v in neighbours.values() if v[0] == "tie_via_multicountry_hub")
    print(f"  pass 3  {len(edges)} edges touch the seed set, "
          f"{len(neighbours)} entities one hop away "
          f"({via_hub} of them only through a multi-country hub); "
          f"{held_back} seeds not treated as Libya-specific "
          f"({len(hubs)} over the degree cap of {HUB_DEGREE})", flush=True)
    notes = {"office_spells": len(occupancies), "diplomatic_spells": diplomatic,
             "seeds_not_libya_specific": held_back, "hubs_over_degree_cap": len(hubs),
             "hub_degree_cap": HUB_DEGREE, "neighbours_via_hub_only": via_hub}
    return seeds, neighbours, edges, occupancies, notes


def materialise(paths, wanted):
    """Pass 4: pull every wanted entity, and the records they point at."""
    kept, extra = {}, set()
    for collection, path in paths.items():
        for entity in stream(path):
            if entity["id"] not in wanted:
                continue
            entity["collection"] = collection
            kept[entity["id"]] = entity
            for prop in ("addressEntity", "identification", "passport", "position"):
                extra.update(values(entity, prop))
    support = {}
    if extra:
        for collection, path in paths.items():
            for entity in stream(path):
                if entity["id"] in extra and entity["id"] not in kept:
                    entity["collection"] = collection
                    support[entity["id"]] = entity
    return kept, support


def sanctions_for(paths, targets):
    """Sanction records naming any of these entities."""
    found = defaultdict(list)
    for collection, path in paths.items():
        for entity in stream(path):
            if entity["schema"] != "Sanction":
                continue
            for target in values(entity, "entity"):
                if target in targets:
                    found[target].append(entity)
    return found


def code_entity(entity, link, evidence, places, offices, addresses):
    """One coded node row.

    `offices` maps a person id to the Libyan offices they hold, which is where
    the governmental topics live: FollowTheMoney puts `gov.executive` on the
    Position, not on the minister, so a person row reads as untagged unless the
    office's topics are carried across. `addresses` maps an Address id to the
    shabiya it resolves to, because an entity's address is often not free text
    on the entity but a pointer to a separate Address record.
    """
    props = entity.get("properties", {})
    topics = list(props.get("topics", []))
    held = offices.get(entity["id"], [])
    office_topics = sorted({t for o in held for t in values(o, "topics")})
    combined = set(topics) | set(office_topics)

    row = {
        "entity_id": entity["id"],
        "name": entity.get("caption", ""),
        "schema": entity["schema"],
        "is_person": int(entity["schema"] == "Person"),
        "is_organisation": int(entity["schema"] in
                               ("Company", "Organization", "LegalEntity", "PublicBody")),
        "libya_link": link,
        "libya_link_evidence": evidence,
        "collection": entity.get("collection", ""),
        "is_target": int(bool(entity.get("target"))),
        "countries": ";".join(sorted({c for p in COUNTRY_PROPS for c in props.get(p, [])})),
        "country_is_libya_only": int({c for p in COUNTRY_PROPS
                                      for c in props.get(p, [])} == {LIBYA}),
        "topics": ";".join(topics),
        "office_topics": ";".join(office_topics),
    }
    for topic, column in TOPIC_FLAGS.items():
        row[column] = int(topic in combined)
    row["is_criminal_designation"] = int(any(t.startswith(CRIME) for t in combined))
    row["gov_branch"] = ";".join(sorted(t[len(GOV):] for t in combined
                                        if t.startswith(GOV)))
    # A Libyan official, as against a foreign envoy accredited to Libya, an
    # organisation that merely operates there, or a sanctioned Libyan who never
    # held office. Either they hold a Libyan office that is not an embassy
    # posting, or they carry a governmental topic and Libyan nationality.
    holds_libyan_office = any(DIPLO not in values(o, "topics") for o in held)
    row["is_libyan_official"] = int(
        entity["schema"] == "Person"
        and link != "accredited_to_libya"
        and (holds_libyan_office
             or (any(t.startswith(GOV) for t in combined)
                 and LIBYA in {c for p in COUNTRY_PROPS for c in props.get(p, [])})))
    row["offices_held"] = len(held)
    row["office_names"] = "; ".join(o.get("caption", "") for o in held[:4])
    row["birth_date"] = first(entity, "birthDate")
    row["death_date"] = first(entity, "deathDate")
    row["birth_place"] = "; ".join(values(entity, "birthPlace"))
    row["address_text"] = "; ".join(values(entity, "address")[:3])
    row["position_text"] = "; ".join(values(entity, "position"))
    row["aliases"] = "; ".join(values(entity, "alias")[:8])

    # Four fields are read for a place, most direct first, and which one
    # answered is recorded so a user can keep only the strong ones.
    row["shabiya_ar"] = row["shabiya_en"] = row["shabiya_pcode"] = ""
    row["place_source"] = row["place_matched_on"] = ""

    # An Address record the entity points at is as good as an address written on
    # it, and in this source it is commoner.
    linked = [addresses[a] for a in values(entity, "addressEntity") if a in addresses]
    candidates = [
        ("birth_place", row["birth_place"]),
        ("address", row["address_text"]),
        ("address_record", linked[0][1] if linked else ""),
        ("office_subnational_area",
         " ".join(first(o, "subnationalArea") for o in held)),
        ("office_name", row["office_names"]),
    ]
    for source, text in candidates:
        if source == "address_record" and linked:
            shabiya, token = linked[0][0], linked[0][1]
        else:
            shabiya, token = locate(text, places)
        if shabiya:
            row["shabiya_ar"] = shabiya["shabiya_ar"]
            row["shabiya_en"] = shabiya["shabiya_en"]
            row["shabiya_pcode"] = shabiya["codab_pcode"]
            row["place_source"] = source
            row["place_matched_on"] = token
            break

    row["datasets"] = ";".join(entity.get("datasets", [])[:12])
    row["first_seen"] = (entity.get("first_seen") or "")[:10]
    row["last_seen"] = (entity.get("last_seen") or "")[:10]
    row["source_urls"] = " ".join(values(entity, "sourceUrl")[:3])
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    paths = {c: RAW / f"{c}.entities.ftm.json" for c in COLLECTIONS}
    for collection, path in paths.items():
        if not path.exists():
            sys.exit(f"missing {path}. Run scripts/download_opensanctions.py first.")
    places = gazetteer()
    print(f"gazetteer: {len(places)} Latin-script place names for 22 shabiyat")

    seeds, neighbours, edges, occupancies, notes = select(paths)
    wanted = set(seeds) | set(neighbours)
    kept, support = materialise(paths, wanted)
    print(f"  pass 4  {len(kept)} entities materialised, "
          f"{len(support)} supporting records", flush=True)
    designations = sanctions_for(paths, set(kept))
    print(f"  pass 5  {sum(len(v) for v in designations.values())} sanction records")

    OUT.mkdir(parents=True, exist_ok=True)
    link_of = dict(seeds)
    link_of.update(neighbours)

    # Which Libyan offices each person holds, so the office's topics can be
    # carried onto the person.
    offices = defaultdict(list)
    for entity in occupancies:
        holder, post = endpoints(entity)
        office = kept.get(post) or support.get(post)
        if holder and office:
            offices[holder].append(office)

    # Address records resolved once, so an entity pointing at one inherits it.
    resolved = {}
    for entity in list(kept.values()) + list(support.values()):
        if entity["schema"] != "Address":
            continue
        shabiya, token = locate(" ".join(values(entity, "full")
                                         + values(entity, "city")
                                         + values(entity, "region")), places)
        if shabiya:
            resolved[entity["id"]] = (shabiya, token)

    # Nodes: entities in their own right. Passports, identifications, addresses
    # and sanctions describe an entity and are written separately.
    rows = [code_entity(e, link_of[i][0], link_of[i][1], places, offices, resolved)
            for i, e in sorted(kept.items()) if e["schema"] in NODE_SCHEMAS]
    write(OUT / "libya_entities.csv", rows)

    # Edges, excluding Occupancy
    edge_rows, dangling = [], 0
    for entity in edges:
        if entity["schema"] not in SOCIAL_EDGES:
            continue
        source, target = endpoints(entity)
        if source not in kept or target not in kept:
            # An endpoint that lives only in the wider `default` collection.
            dangling += 1
            continue
        edge_rows.append({
            "edge_id": entity["id"],
            "edge_schema": entity["schema"],
            "source_id": source,
            "source_name": kept[source].get("caption", ""),
            "target_id": target,
            "target_name": kept[target].get("caption", ""),
            "relationship": first(entity, "relationship") or first(entity, "role"),
            "start_date": first(entity, "startDate"),
            "end_date": first(entity, "endDate"),
            "datasets": ";".join(entity.get("datasets", [])[:8]),
        })
    write(OUT / "libya_edges.csv", edge_rows)

    # Offices held
    position_rows = []
    for entity in occupancies:
        holder, post = endpoints(entity)
        office = kept.get(post) or support.get(post)
        if holder not in kept:
            continue
        position_rows.append({
            "occupancy_id": entity["id"],
            "person_id": holder,
            "person_name": kept[holder].get("caption", ""),
            "position_id": post,
            "position_name": office.get("caption", "") if office else "",
            "position_topics": ";".join(values(office, "topics")) if office else "",
            "is_foreign_posting": int(DIPLO in values(office, "topics")) if office else "",
            "subnational_area": first(office, "subnationalArea") if office else "",
            "start_date": first(entity, "startDate"),
            "end_date": first(entity, "endDate"),
            "status": first(entity, "status"),
            "datasets": ";".join(entity.get("datasets", [])[:8]),
        })
    write(OUT / "libya_positions.csv", position_rows)

    # Addresses
    address_rows = []
    for entity in list(kept.values()) + list(support.values()):
        if entity["schema"] != "Address":
            continue
        full = first(entity, "full")
        shabiya, token = locate(f"{full} {first(entity, 'city')} {first(entity, 'region')}",
                                places)
        address_rows.append({
            "address_id": entity["id"],
            "full": full,
            "city": first(entity, "city"),
            "region": first(entity, "region"),
            "country": ";".join(values(entity, "country")),
            "latitude": first(entity, "latitude"),
            "longitude": first(entity, "longitude"),
            "shabiya_ar": shabiya["shabiya_ar"] if shabiya else "",
            "shabiya_en": shabiya["shabiya_en"] if shabiya else "",
            "shabiya_pcode": shabiya["codab_pcode"] if shabiya else "",
            "matched_on": token,
        })
    write(OUT / "libya_addresses.csv", address_rows)

    # Designations
    sanction_rows = []
    for target, records in sorted(designations.items()):
        for entity in records:
            sanction_rows.append({
                "sanction_id": entity["id"],
                "entity_id": target,
                "entity_name": kept[target].get("caption", ""),
                "authority": first(entity, "authority"),
                "authority_id": first(entity, "authorityId"),
                "unsc_id": first(entity, "unscId"),
                "program": first(entity, "program"),
                "program_id": first(entity, "programId"),
                "listing_date": first(entity, "listingDate"),
                "start_date": first(entity, "startDate"),
                "end_date": first(entity, "endDate"),
                "status": first(entity, "status"),
                "reason": first(entity, "reason")[:400],
                "country": ";".join(values(entity, "country")),
            })
    write(OUT / "libya_sanctions.csv", sanction_rows)

    manifest = json.loads((RAW / "manifest.json").read_text())
    (OUT / "SOURCE.json").write_text(json.dumps({
        "source": manifest["source"],
        "licence": manifest["licence"],
        "export_run_time": manifest["export_run_time"],
        "ftm_model_version": manifest["ftm_model_version"],
        "retrieved": manifest["retrieved"],
        "bulk_files": manifest["files"],
        "selection": {
            "country_code": LIBYA,
            "country_properties": list(COUNTRY_PROPS),
            "routes": ["country_tagged", "libyan_position", "tie_to_libya"],
        },
        "outputs": {
            "libya_entities.csv": len(rows), "libya_edges.csv": len(edge_rows),
            "libya_positions.csv": len(position_rows),
            "libya_addresses.csv": len(address_rows),
            "libya_sanctions.csv": len(sanction_rows),
        },
        "edges_dropped_endpoint_outside_collections": dangling,
        "selection_notes": notes,
    }, ensure_ascii=False, indent=1) + "\n")

    report(rows, edge_rows, position_rows, address_rows, sanction_rows, dangling)


def write(path, rows):
    if not rows:
        print(f"{path.name:26s} no rows")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:26s} {len(rows):6d} rows")


def report(nodes, edges, positions, addresses, sanctions, dangling):
    print("\nnodes by route in:", dict(Counter(r["libya_link"] for r in nodes)))
    print("nodes by schema:  ", dict(Counter(r["schema"] for r in nodes).most_common(8)))
    print("persons:", sum(r["is_person"] for r in nodes),
          "| Libyan officials:", sum(r["is_libyan_official"] for r in nodes),
          "| PEPs:", sum(r["is_pep"] for r in nodes),
          "| sanctioned:", sum(r["is_sanctioned"] for r in nodes),
          "| relatives and associates:",
          sum(r["is_relative_or_associate"] for r in nodes))
    print("gov branch:       ",
          dict(Counter(r["gov_branch"] for r in nodes if r["gov_branch"]).most_common(6)))
    print("edges by type:    ", dict(Counter(r["edge_schema"] for r in edges)))
    print(f"{dangling} edges dropped: an endpoint is not in these two collections")
    placed = Counter(r["place_source"] for r in nodes if r["shabiya_en"])
    print(f"placed in a shabiya: {sum(placed.values())} of {len(nodes)} nodes",
          dict(placed))
    print("  by shabiya:",
          dict(Counter(r["shabiya_en"] for r in nodes if r["shabiya_en"]).most_common(8)))
    geo = sum(1 for r in addresses if r["shabiya_ar"])
    print(f"addresses: {len(addresses)} records, {geo} resolve to a shabiya")
    print(f"office spells: {len(positions)}, "
          f"{sum(1 for r in positions if r['is_foreign_posting'] == 1)} foreign postings")
    print(f"designations: {len(sanctions)} by "
          f"{len({r['authority'] for r in sanctions})} authorities")


if __name__ == "__main__":
    main()
