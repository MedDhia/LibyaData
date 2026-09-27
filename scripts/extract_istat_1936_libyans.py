#!/usr/bin/env python3
"""
Tables XXI and XXII of the 1936 census: the Libyan population itself.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione III, Popolazione libica, Tavole XXI and XXII, printed pages 80 to 91.

**Transcribed by eye**, like the other 1931 and 1936 tables, and validated
before anything is published. The two transcriptions are committed as
`data/raw/istat/libya_1936_table21.csv` and `libya_1936_table22.csv` and are
the source.

## What they count, which is the other 86 per cent of Libya

Tables I to IV of the same volume count the whole population and then the
settlers. These two count the `popolazione libica` on its own: 732,973 present
in April 1936 and 750,851 resident. They are the only tables in the volume that
break that population down by what it was rather than where it was.

Both tables run the same 83 circumscriptions plus Libya, and both go a level
deeper than table II: below the five sottozone militari of the Territorio
Militare del Sud they name the thirteen mudirie of the Fezzan, so Brach, Sebha,
Gat, Murzuch, Traghen, Hon and Zella each get a line of their own.

Every row is split by **dimora**, which here is a way of life and not a
dwelling: `stabile` (settled), `seminomade` and `nomade`. That split is the
reason to have these tables. Of the 732,973 present, 110,830 were counted
seminomadic or nomadic, and they are not spread evenly: the Circondario di
el-Azizia was 99% seminomadic and the Distretto di Mizda 79% nomadic, while the
Circondario di Tripoli, the Residenza di Bengasi and the Residenza di Homs were
settled to a person. Among the circondari the range runs from Agedabia at 45%
and Tobruch at 33% down to Homs, Zliten and Bengasi at nothing. A map of
nomadism in Libya on the eve of the colonisation programme is in these columns.

## Religion, race and language, in the volume's own categories

The categories are the census's, not ours, and the race column in particular is
a colonial instrument: it sorts people into `araba e arabo-berbera`, `berbera`,
`cologhla` (the descendants of Ottoman garrison troops), `negra`, `razze varie
dell'Africa Orientale` and `altre`. They are published as printed because that
is what the source says, and the column names keep the Italian so nobody
mistakes them for a modern classification.

What they show is real all the same. The Ibadi Berber west is visible in one
line: the Circondario di Nalut counted 8,457 Ibadis of 22,989 Muslims and
10,231 Berbers of 23,030 people, against 29,223 Ibadis in the whole Provincia
di Tripoli. The 20,938 Jews of the Provincia di Tripoli and the 17,196 in the
Circondario di Tripoli alone are the Tripoli community before the racial laws.
The 5,578 cologhli of the province and the 24,167 of Misurata are an Ottoman
inheritance that no later census recorded.

Table XXI adds age (under 15) and sex; table XXII adds the number of family
heads, which with the population gives a mean household size.

## Six checks, and the sixth crosses to another table

  rites       Malechita + altri riti + Ibadismo = the Muslim population
  religion    Muslim + Israelitica + Copta + altre = the population
  race        the six race columns sum to the population
  language    the language columns sum to the population
  dimora      stabile + seminomade + nomade = the Tot. line, in every column
  hierarchy   every parent equals the sum of the rows under it, and the four
              provinces plus the Territorio Militare del Sud sum to Libya
  table II    the population here equals table II's `libica`, present for
              table XXI and resident for table XXII, for men and women and for
              women alone

The last binds two transcriptions made from six different pages: 276 figures
agree. Table XXI also carries M + F = MF and the same for the under-15s, which
table XXII does not print.

Outputs, under data/processed/istat/:
  libya_1936_libyans_present.csv    229 rows, table XXI
  libya_1936_libyans_resident.csv   229 rows, table XXII
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_istat_1936_circumscriptions import (  # noqa: E402
    COLONY, key_of, place, resolve)
from libya_places import gazetteer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
CIRCUMSCRIPTIONS = RAW / "libya_1936_table2.csv"

RELIGION = ("muslim", "jewish", "copt", "other_religion")
RITES = ("malechita", "other_rites", "ibadi")
RACE = ("arab", "berber", "cologhli", "negro", "ao_races", "other_race")
LANGUAGE = ("lang_arabic", "lang_berber", "lang_ao", "lang_other")

PRESENT = (["mf", "mf_u15", "m", "m_u15", "f", "f_u15"] + ["muslim"]
           + list(RITES) + ["jewish", "copt", "other_religion"] + list(RACE)
           + list(LANGUAGE) + ["italian"])
# Table XXII drops the age and sex detail, adds family heads, and folds the
# A.O. columns into `altre` for both race and language.
RESIDENT = (["mf", "heads", "f", "muslim"] + list(RITES)
            + ["jewish", "other_religion"]
            + ["arab", "berber", "cologhli", "negro", "other_race"]
            + ["lang_arabic", "lang_berber", "lang_other", "italian"])

# The thirteen mudirie of the Fezzan and the two distretti under Mizda, which
# table II stops short of and the concordance therefore never saw. The
# gazetteer resolves most of these itself once it is handed the Arabic name;
# the rest are asserted to the shabiya of the circumscription above them and
# labelled as such, so they can be dropped.
DEEPER = {
    "Mudiria di Edri": "إدري", "Mudiria di Berghin": "برقن",
    "Mudiria di Brach": "براك", "Mudiria di Sebha": "سبها",
    "Mudiria di Gat": "غات", "Mudiria di Uadi el-Agial": "وادي الحياة",
    "Mudiria di Murzuch": "مرزق", "Mudiria di Uadi Etba": "وادي عتبة",
    "Mudiria di el-Gatrun": "القطرون",
}
DEEPER_ASSERTED = {
    "Mudiria di Traghen": "مرزق", "Mudiria di Umm el-Araneb": "مرزق",
    "Mudiria di Hon": "الجفرة", "Mudiria di Zella": "الجفرة",
    "Distretto di Mizda": "الجبل الغربي",
    "Distretto di el-Gheria esc-Scerghia": "الجبل الغربي",
}


def read(name, numbers):
    rows = []
    for row in csv.DictReader((RAW / name).open()):
        for column in numbers:
            row[column] = int(row[column])
        rows.append(row)
    return rows


def audit(rows, numbers, table):
    """The identities the table prints, in every line of it."""
    trouble = []

    for row in rows:
        who = f"{table} {row['order']} {row['name']} {row['dimora']}"
        rites = sum(row[c] for c in RITES)
        if rites != row["muslim"]:
            trouble.append(f"{who}: the rites sum to {rites:,}, the Muslim "
                           f"population is {row['muslim']:,}")
        for block, columns in (("religions", [c for c in RELIGION
                                              if c in numbers]),
                               ("races", [c for c in RACE if c in numbers]),
                               ("languages", [c for c in LANGUAGE
                                              if c in numbers])):
            got = sum(row[c] for c in columns)
            if got != row["mf"]:
                trouble.append(f"{who}: the {block} sum to {got:,}, the "
                               f"population is {row['mf']:,}")
        for column in ("f", "heads", "italian", "mf_u15"):
            if column in numbers and row[column] > row["mf"]:
                trouble.append(f"{who}: {column} exceeds the population")
        if "m" in numbers:
            if row["m"] + row["f"] != row["mf"]:
                trouble.append(f"{who}: M and F do not add to MF")
            if row["m_u15"] + row["f_u15"] != row["mf_u15"]:
                trouble.append(f"{who}: the under-15s do not add up")

    lines = defaultdict(dict)
    for row in rows:
        lines[row["name"]][row["dimora"]] = row
    for name, kinds in lines.items():
        if "Tot" not in kinds:
            if len(kinds) != 1:
                trouble.append(f"{table} {name}: {len(kinds)} lines and no "
                               f"Tot. line")
            continue
        parts = [kinds[d] for d in ("st", "sn", "n") if d in kinds]
        for column in numbers:
            got = sum(p[column] for p in parts)
            if got != kinds["Tot"][column]:
                trouble.append(f"{table} {name} {column}: the dimora lines sum "
                               f"to {got:,}, the Tot. line says "
                               f"{kinds['Tot'][column]:,}")

    totals = {name: kinds.get("Tot") or next(iter(kinds.values()))
              for name, kinds in lines.items()}
    children = defaultdict(list)
    for name, row in totals.items():
        if row["parent"]:
            children[row["parent"]].append(row)
    for parent, kids in children.items():
        above = totals.get(parent)
        if not above:
            trouble.append(f"{table}: no row named {parent}")
            continue
        for column in numbers:
            got = sum(k[column] for k in kids)
            if got != above[column]:
                trouble.append(f"{table} {parent} {column}: its {len(kids)} "
                               f"children sum to {got:,}, the row says "
                               f"{above[column]:,}")
    return trouble


def against_table_two(present, resident):
    """This is table II's `libica`, present in XXI and resident in XXII."""
    if not CIRCUMSCRIPTIONS.exists():
        return ["libya_1936_table2.csv is missing"], 0
    two = {r["name"]: r for r in csv.DictReader(CIRCUMSCRIPTIONS.open())}
    trouble, checked = [], 0
    for table, rows, when in (("XXI", present, "present"),
                              ("XXII", resident, "resident")):
        for row in one_line(rows):
            twin = two.get(row["name"])
            if not twin:
                continue
            for column in ("mf", "f"):
                want = int(twin[f"{when}_libyan_{column}"])
                if want != row[column]:
                    trouble.append(f"{table} {row['name']} {column}: table II "
                                   f"has {want:,} Libyans {when}, this table "
                                   f"has {row[column]:,}")
                else:
                    checked += 1
    return trouble, checked


def one_line(rows):
    """The Tot. line of each circumscription, or its only line."""
    seen, out = set(), []
    for row in rows:
        if row["name"] in seen:
            continue
        kinds = [r for r in rows if r["name"] == row["name"]]
        pick = next((r for r in kinds if r["dimora"] == "Tot"), kinds[0])
        seen.add(row["name"])
        out.append(pick)
    return out


def locate(rows, places, shabiya_keys, scrambled):
    province = {}
    for row in rows:
        if row["level"] in ("provincia", "territorio"):
            province[row["name"]] = row["name"]
        elif row["parent"]:
            province[row["name"]] = province.get(row["parent"], "")
        row["province"] = province.get(row["name"], "")
    place(rows, places, shabiya_keys, scrambled,
          lambda r: COLONY.get(r["province"] or r["name"], "Tripolitania"))
    for row in rows:
        if row["shabiya_route"] != "unplaced":
            continue
        arabic = DEEPER.get(row["name"])
        if arabic:
            found = resolve(arabic, places, shabiya_keys, scrambled)
            if found:
                row.update(place_ar=arabic, shabiya_ar=found[0],
                           shabiya_en=found[1], shabiya_pcode=found[2],
                           shabiya_route="concordance")
                continue
        arabic = DEEPER_ASSERTED.get(row["name"])
        if arabic:
            found = resolve(arabic, places, shabiya_keys, scrambled)
            if found:
                row.update(place_ar=arabic, shabiya_ar=found[0],
                           shabiya_en=found[1], shabiya_pcode=found[2],
                           shabiya_route="asserted")


def write(rows, numbers, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fields = (["province", "level", "name", "parent", "dimora", "place_ar",
               "shabiya_ar", "shabiya_en", "shabiya_pcode", "shabiya_route"]
              + numbers + ["order", "place_key"])
    path = OUT / name
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:36s} {len(rows):5d} rows")
    return path


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    places, shabiya_keys, scrambled = gazetteer()

    present = read("libya_1936_table21.csv", PRESENT)
    resident = read("libya_1936_table22.csv", RESIDENT)

    trouble = (audit(present, PRESENT, "XXI")
               + audit(resident, RESIDENT, "XXII"))
    more, checked = against_table_two(present, resident)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    for rows in (present, resident):
        heads = one_line(rows)
        locate(heads, places, shabiya_keys, scrambled)
        carried = {r["name"]: r for r in heads}
        for row in rows:
            for column in ("province", "place_ar", "shabiya_ar", "shabiya_en",
                           "shabiya_pcode", "shabiya_route", "place_key"):
                row[column] = carried[row["name"]][column]

    write(present, PRESENT, "libya_1936_libyans_present.csv")
    write(resident, RESIDENT, "libya_1936_libyans_resident.csv")
    report(present, resident, checked)


def report(present, resident, checked):
    total = next(r for r in present if r["level"] == "colony"
                 and r["dimora"] == "Tot")
    moving = total["mf"] - next(r for r in present if r["level"] == "colony"
                                and r["dimora"] == "st")["mf"]
    living = next(r for r in resident if r["level"] == "colony"
                  and r["dimora"] == "Tot")
    print()
    print(f"Libya 1936, the Libyan population: {total['mf']:,} present and "
          f"{living['mf']:,} resident, of whom {moving:,} "
          f"({moving / total['mf']:.0%}) were counted seminomadic or nomadic")
    print(f"  religion: {total['muslim']:,} Muslim "
          f"({total['ibadi']:,} of them Ibadi), {total['jewish']:,} Jewish, "
          f"{total['copt']:,} Copt")
    print(f"  race as the census recorded it: {total['arab']:,} arab or "
          f"arabo-berbera, {total['berber']:,} berbera, "
          f"{total['cologhli']:,} cologhla, {total['negro']:,} negra")
    print(f"  language: {total['lang_berber']:,} spoke Berber and "
          f"{total['italian']:,} spoke Italian")
    heads = one_line(present)
    shifting = sorted((r for r in heads if r["level"] == "circondario"),
                      key=lambda r: -moved(present, r["name"]) / r["mf"])
    print("  least settled, by circondario: " + ", ".join(
        f"{r['name'].replace('Circondario di ', '')} "
        f"{moved(present, r['name']) / r['mf']:.0%}" for r in shifting[:4]))
    print("\n  [ok ] rites, religion, race, language, dimora and hierarchy "
          "checks pass in both tables")
    print(f"  [ok ] {checked} figures agree with table II: this is its "
          f"Libyan population, present and resident")
    print(f"{len(heads)} circumscriptions "
          f"{dict(Counter(r['shabiya_route'] for r in heads))}")
    print("\nnext: python3 scripts/validate.py")


def moved(rows, name):
    lines = {r["dimora"]: r for r in rows if r["name"] == name}
    whole = lines.get("Tot") or next(iter(lines.values()))
    settled = lines.get("st", {"mf": 0})["mf"] if "Tot" in lines else whole["mf"]
    return whole["mf"] - settled


if __name__ == "__main__":
    main()
