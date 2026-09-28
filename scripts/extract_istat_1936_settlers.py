#!/usr/bin/env python3
"""
Tables V to XII of the 1936 census: the settler population's families,
institutions, ages and nationalities.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione II, Popolazione nazionale, straniera e assimilata, printed pages 7 to
15.

**Transcribed by eye** and validated before anything is published. The
transcriptions are committed as `data/raw/istat/libya_1936_table{5,6,7,8,
9_10,11,12}.csv` and are the source.

## What they hold

  V     resident families and their members by the social condition of the
        head (padroni, artigiani, liberi professionisti, dirigenti,
        impiegati, operai, personale di servizio, altre, with di cui lines for
        agriculture and the armed forces), per province and for Tripoli
  VI    the same families by number of members, for Libya and Tripoli; and
        the families headed by a woman
  VII   the same families by number of co-resident children under 6, 15, 21
        and of any age, by condition of the head
  VIII  convivenze: hotels, hospitals, schools, religious communities,
        prisons, ships and other quarters, by province, with the number of
        institutions, their members by sex, and the subset of institutions of
        fifteen members or fewer
  IX    the settler population present by single year of age, sex and civil
        status, for Libya and Tripoli, with the census's special age groups
  X     the same for the resident population
  XI    foreigners present by country, sex and whether they lived there
  XII   foreigners with a habitual dwelling by age, civil status and activity,
        for the main nationalities

`settler` is shorthand for the volume's `popolazione nazionale, straniera e
assimilata`: Italians, other foreigners and the small assimilated group.

## Checks, and five crossings to other tables

  V     the eight conditions add to the total; di cui lines never exceed their
        condition; provinces add to Libya
  VI    sizes add to families; the sum of size times families is the members,
        exactly; VI's totals equal V's for Libya and for Tripoli
  VII   the children in families with k children are k times those families;
        the four age limits nest; conditions add to the total
  VIII  provinces add to Libya; F <= MF; the small institutions are a subset;
        the ten kinds add to the whole
  IX, X M + F = MF; the five civil states add to the total; single ages add
        to the Complesso; the special age groups equal the sum of their ages;
        IX's totals are table IV's present population and X's its resident
        population, for Libya and for the municipio di Tripoli
  XI    countries add to continents and continents plus the stateless to the
        whole; the whole equals table II's `straniera` for Libya and Tripoli
  XII   ages, civil states and activities each add to the whole, for every
        column; the whole equals XI's foreigners with a habitual dwelling, and
        the French, British and Greek columns equal XI's lines for them

Outputs, under data/processed/istat/:
  libya_1936_settler_families.csv       V and VI, long
  libya_1936_settler_children.csv       VII, long
  libya_1936_settler_institutions.csv   VIII, long
  libya_1936_settler_age.csv            IX and X, long
  libya_1936_foreigners.csv             XI and XII, long
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"

MAIN = ("padroni", "artigiani", "liberi_professionisti", "dirigenti",
        "impiegati", "operai", "personale_servizio", "altre")
SUBS = {"padroni": ("padroni_piccoli", "padroni_agricoltura"),
        "artigiani": ("artigiani_coloni_parziari",
                      "artigiani_agricoltura_altri"),
        "dirigenti": ("dirigenti_agricoltura", "dirigenti_forze_armate"),
        "impiegati": ("impiegati_agricoltura", "impiegati_forze_armate",
                      "impiegati_culto"),
        "operai": ("operai_agricoltura", "operai_forze_armate")}
CONDITIONS = ["totale"] + [c for m in MAIN for c in (m,) + SUBS.get(m, ())]
PROVINCES = ("Provincia di Tripoli", "Provincia di Misurata",
             "Provincia di Bengasi", "Provincia di Derna",
             "Territorio Militare del Sud")
STATES = ("tot", "celibi", "coniugati", "vedovi", "divorziati", "ignoto")
AGECOLS = [f"{s}_{x}" for s in STATES for x in ("mf", "m", "f")]
LIMITS = ("u6", "u15", "u21", "any")
KS = [str(k) for k in range(1, 9)] + ["9plus"]
AREAS8 = ("libia", "mun_tripoli", "tripoli", "misurata", "bengasi", "derna",
          "territorio")


def read(name):
    rows = []
    for row in csv.DictReader((RAW / name).open()):
        for key, value in row.items():
            if value.lstrip("-").isdigit() and key not in (
                    "members", "age", "table"):
                row[key] = int(value)
        rows.append(row)
    return rows


def audit_5_6(v, vi):
    trouble = []
    for r in v + vi:
        who = f"{r.get('measure', 'VI')} {r['area']} {r.get('members', '')}"
        if sum(r[c] for c in MAIN) != r["totale"]:
            trouble.append(f"{who}: conditions do not add to the total")
        for main, subs in SUBS.items():
            if any(r[s] > r[main] for s in subs):
                trouble.append(f"{who}: a di cui line exceeds {main}")
    by5 = {(r["measure"], r["area"]): r for r in v}
    for measure in ("families", "members"):
        for c in CONDITIONS:
            got = sum(by5[(measure, p)][c] for p in PROVINCES)
            if got != by5[(measure, "Libia")][c]:
                trouble.append(f"V {measure} {c}: provinces {got:,}")
    six = defaultdict(dict)
    for r in vi:
        six[r["area"]][r["members"]] = r
    names = {"Libia": "Libia",
             "di cui municipio di Tripoli": "di cui municipio di Tripoli"}
    for area, lines in six.items():
        sizes = [k for k in lines if k.isdigit()]
        for c in CONDITIONS:
            if sum(lines[k][c] for k in sizes) != lines["famiglie"][c]:
                trouble.append(f"VI {area} {c}: sizes do not add")
            if (sum(int(k) * lines[k][c] for k in sizes)
                    != lines["membri"][c]):
                trouble.append(f"VI {area} {c}: size times families is not "
                               f"the members")
            if lines["famiglie"][c] != by5[("families", names[area])][c]:
                trouble.append(f"VI {area} {c}: families differ from V")
            if lines["membri"][c] != by5[("members", names[area])][c]:
                trouble.append(f"VI {area} {c}: members differ from V")
    return trouble


def audit_7(rows):
    trouble = []
    by = {(r["measure"], r["condition_of_head"]): r for r in rows}
    main = ("padroni", "artigiani", "liberi professionisti", "dirigenti",
            "impiegati", "operai", "personale di servizio", "altre")
    for (measure, cond), r in by.items():
        for a in LIMITS:
            if sum(r[f"{a}_{k}"] for k in KS) != r[f"{a}_total"]:
                trouble.append(f"VII {measure} {cond} {a}: sizes")
        if measure == "families":
            totals = [r[f"{a}_total"] for a in LIMITS]
            if totals != sorted(totals):
                trouble.append(f"VII {cond}: age limits not nested")
            kids = by[("children", cond)]
            for a in LIMITS:
                for k in KS[:-1]:
                    if kids[f"{a}_{k}"] != int(k) * r[f"{a}_{k}"]:
                        trouble.append(f"VII {cond} {a} k={k}")
    for measure in ("families", "children"):
        for a in LIMITS:
            for k in KS + ["total"]:
                got = sum(by[(measure, m)][f"{a}_{k}"] for m in main)
                if got != by[(measure, "totale")][f"{a}_{k}"]:
                    trouble.append(f"VII {measure} {a}_{k}: conditions")
    return trouble


def audit_8(rows):
    trouble = []
    by = {(r["kind"], r["role"], r["scope"]): r for r in rows}
    for (kind, role, scope), r in by.items():
        for x in ("n", "mf", "f"):
            got = sum(r[f"{a}_{x}"] for a in AREAS8[2:])
            if got != r[f"libia_{x}"]:
                trouble.append(f"VIII {kind} {role} {scope} {x}: provinces")
        for a in AREAS8:
            if r[f"{a}_f"] > r[f"{a}_mf"]:
                trouble.append(f"VIII {kind} {role} {scope} {a}: F > MF")
        if scope == "small":
            big = by[(kind, role, "all")]
            if any(r[k] > big[k] for k in big if k.endswith(("_n", "_mf",
                                                              "_f"))):
                trouble.append(f"VIII {kind} {role}: small exceeds all")
    kinds = {k for k, _, _ in by} - {"complesso"}
    for scope in ("all", "small"):
        for col in [f"{a}_{x}" for a in AREAS8 for x in ("n", "mf", "f")]:
            got = sum(by[(k, "componenti", scope)][col] for k in kinds)
            if got != by[("complesso", "componenti", scope)][col]:
                trouble.append(f"VIII {scope} {col}: kinds do not add")
    return trouble


def age_start(label):
    return int(label.replace("+", "").split("-")[0])


GROUPS = {"fino a 5": (0, 5), "fino a 9": (0, 9), "6-13": (6, 13),
          "fino a 14": (0, 14), "15-64": (15, 64), "65+": (65, 200),
          "14-17": (14, 17), "18-20": (18, 20), "21+": (21, 200)}


def audit_9_10(rows):
    trouble = []
    blocks = defaultdict(dict)
    for r in rows:
        blocks[(r["table"], r["area"])][r["age"]] = r
        who = f"{r['table']} {r['area']} {r['age']}"
        for s in STATES:
            if r[f"{s}_m"] + r[f"{s}_f"] != r[f"{s}_mf"]:
                trouble.append(f"{who} {s}: M + F")
        for x in ("mf", "m", "f"):
            if sum(r[f"{s}_{x}"] for s in STATES[1:]) != r[f"tot_{x}"]:
                trouble.append(f"{who} {x}: civil states")
    for key, lines in blocks.items():
        ages = [a for a in lines if a not in ("Totale",)
                and not a.startswith("gruppo")]
        for col in AGECOLS:
            if sum(lines[a][col] for a in ages) != lines["Totale"][col]:
                trouble.append(f"{key} {col}: ages do not add")
        for g, (lo, hi) in GROUPS.items():
            line = lines.get(f"gruppo {g}")
            if not line:
                continue
            inside = [a for a in ages if a != "ignota"
                      and lo <= age_start(a) <= hi]
            for col in AGECOLS:
                if sum(lines[a][col] for a in inside) != line[col]:
                    trouble.append(f"{key} group {g} {col}")
    return trouble, blocks


def crossings(blocks, xi):
    trouble, checked = [], 0
    four = {r["name"]: r for r in csv.DictReader(
        (RAW / "libya_1936_table4.csv").open())}
    two = {r["name"]: r for r in csv.DictReader(
        (RAW / "libya_1936_table2.csv").open())}
    names = {"Libia": "LIBIA",
             "di cui municipio di Tripoli": "Circondario di Tripoli"}
    for (table, area), lines in blocks.items():
        when = "present" if table == "9" else "resident"
        twin = four[names[area]]
        for x in ("mf", "f"):
            if lines["Totale"][f"tot_{x}"] != int(twin[f"{when}_{x}"]):
                trouble.append(f"table {table} {area} {x}: differs from IV")
            else:
                checked += 1
    whole = next(r for r in xi if r["continent"] == "Complesso")
    for area, col in (("LIBIA", "present_libia"),
                      ("Circondario di Tripoli", "present_tripoli")):
        for x in ("mf", "f"):
            if whole[f"{col}_{x}"] != int(two[area][f"present_foreign_{x}"]):
                trouble.append(f"XI {area} {x}: differs from table II")
            else:
                checked += 1
    return trouble, checked


def audit_11_12(xi, xii):
    trouble = []
    cols11 = [k for k in xi[0] if k.startswith(("present", "habitual"))]
    groups = defaultdict(list)
    for r in xi:
        groups[r["continent"]].append(r)
    for continent, lines in groups.items():
        total = [r for r in lines if r["state"] == "Totale"]
        if total:
            for c in cols11:
                if sum(r[c] for r in lines if r["state"] != "Totale") \
                        != total[0][c]:
                    trouble.append(f"XI {continent} {c}")
    whole = groups["Complesso"][0]
    for c in cols11:
        got = sum(groups[k][-1][c] for k in ("Europa", "Asia", "Africa",
                                             "America"))
        got += groups["Apolidi"][0][c]
        if got != whole[c]:
            trouble.append(f"XI {c}: continents do not add to the whole")
    cols12 = [k for k in xii[0] if k.endswith(("_mf", "_m", "_f"))]
    total = next(r for r in xii if r["block"] == "totale")
    for block in ("eta", "stato", "attivita"):
        for c in cols12:
            got = sum(r[c] for r in xii if r["block"] == block
                      and r["line"] != "di cui botteghe artigiane")
            if got != total[c]:
                trouble.append(f"XII {block} {c}: lines do not add")
    for r in xii:
        for place in ("libia", "tripoli"):
            if r[f"{place}_m"] + r[f"{place}_f"] != r[f"{place}_mf"]:
                trouble.append(f"XII {r['line']} {place}: M + F")
    pairs = (("libia", "habitual_libia"), ("tripoli", "habitual_tripoli"))
    for mine, theirs in pairs:
        for x in ("mf", "f"):
            if total[f"{mine}_{x}"] != whole[f"{theirs}_{x}"]:
                trouble.append(f"XII {mine} {x}: differs from XI")
    by11 = {r["state"]: r for r in xi}
    for col, state in (("francia", "Francia"),
                       ("gran_bretagna", "Gran Bretagna e Irlanda del Nord"),
                       ("grecia", "Grecia")):
        for x in ("mf", "f"):
            if total[f"{col}_{x}"] != by11[state][f"habitual_libia_{x}"]:
                trouble.append(f"XII {col} {x}: differs from XI")
    return trouble


def write(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name:40s} {len(rows):5d} rows")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    v, vi = read("libya_1936_table5.csv"), read("libya_1936_table6.csv")
    vii, viii = read("libya_1936_table7.csv"), read("libya_1936_table8.csv")
    ages = read("libya_1936_table9_10.csv")
    xi, xii = read("libya_1936_table11.csv"), read("libya_1936_table12.csv")

    trouble = audit_5_6(v, vi) + audit_7(vii) + audit_8(viii)
    more, blocks = audit_9_10(ages)
    trouble += more + audit_11_12(xi, xii)
    more, checked = crossings(blocks, xi)
    trouble += more
    if trouble:
        print(f"{len(trouble)} checks fail; nothing is published:")
        for line in trouble[:12]:
            print("   " + line)
        sys.exit(1)

    families = []
    for r in v:
        for c in CONDITIONS:
            families.append({"table": "V", "measure": r["measure"],
                             "area": r["area"], "members_in_family": "all",
                             "condition_of_head": c, "value": r[c]})
    for r in vi:
        measure = {"famiglie": "families", "membri": "members",
                   "capo femmina": "families headed by a woman"}.get(
                       r["members"], "families")
        size = r["members"] if r["members"].isdigit() else "all"
        for c in CONDITIONS:
            families.append({"table": "VI", "measure": measure,
                             "area": r["area"], "members_in_family": size,
                             "condition_of_head": c, "value": r[c]})
    children = []
    labels = {"u6": "under 6", "u15": "under 15", "u21": "under 21",
              "any": "any age"}
    for r in vii:
        for a in LIMITS:
            for k in KS + ["total"]:
                children.append({"measure": r["measure"],
                                 "condition_of_head": r["condition_of_head"],
                                 "children_age": labels[a],
                                 "number_of_children": k.replace("9plus",
                                                                 "9+"),
                                 "value": r[f"{a}_{k}"]})
    institutions = []
    area8 = {"libia": "Libia", "mun_tripoli": "di cui municipio di Tripoli",
             "tripoli": "Provincia di Tripoli",
             "misurata": "Provincia di Misurata",
             "bengasi": "Provincia di Bengasi",
             "derna": "Provincia di Derna",
             "territorio": "Territorio Militare del Sud"}
    for r in viii:
        for a in AREAS8:
            institutions.append({
                "kind": r["kind"], "role": r["role"],
                "scope": "15 members or fewer" if r["scope"] == "small"
                else "all", "area": area8[a],
                "institutions": r[f"{a}_n"], "persons_mf": r[f"{a}_mf"],
                "persons_f": r[f"{a}_f"]})
    agerows = []
    for r in ages:
        for s in STATES:
            for x in ("mf", "m", "f"):
                agerows.append({
                    "population": "present" if r["table"] == "9"
                    else "resident", "area": r["area"], "age": r["age"],
                    "civil_status": "all" if s == "tot" else s,
                    "sex": x.upper(), "persons": r[f"{s}_{x}"]})
    foreigners = []
    for r in xi:
        for col in [k for k in r if k.startswith(("present", "habitual"))]:
            dwelling, place, sex = col.split("_")
            foreigners.append({
                "table": "XI", "continent": r["continent"],
                "state": r["state"], "breakdown": "",
                "line": "", "dwelling": "all present" if dwelling ==
                "present" else "habitual", "area": "Libia" if place ==
                "libia" else "di cui municipio di Tripoli",
                "sex": sex.upper(), "persons": r[col]})
    for r in xii:
        for col in [k for k in r if k.endswith(("_mf", "_m", "_f"))]:
            who, sex = col.rsplit("_", 1)
            foreigners.append({
                "table": "XII", "continent": "",
                "state": {"libia": "all", "tripoli": "all"}.get(who, who),
                "breakdown": r["block"], "line": r["line"],
                "dwelling": "habitual",
                "area": "di cui municipio di Tripoli" if who == "tripoli"
                else "Libia", "sex": sex.upper(), "persons": r[col]})
    write("libya_1936_settler_families.csv", families)
    write("libya_1936_settler_children.csv", children)
    write("libya_1936_settler_institutions.csv", institutions)
    write("libya_1936_settler_age.csv", agerows)
    write("libya_1936_foreigners.csv", foreigners)

    libya = blocks[("9", "Libia")]
    young = sum(libya[str(a)]["tot_m"] for a in range(20, 25))
    print()
    print(f"  settlers present aged 20 to 24: {young:,} men against "
          f"{sum(libya[str(a)]['tot_f'] for a in range(20, 25)):,} women; "
          f"{libya['22']['tot_m']:,} men aged 22 alone")
    print(f"  foreigners: {xi[-1]['present_libia_mf']:,} present, "
          f"{next(r for r in xi if r['state'].startswith('Gran'))['present_libia_mf']:,}"
          f" of them British subjects")
    print("\n  [ok ] every printed identity holds in all eight tables")
    print(f"  [ok ] {checked} figures agree with tables II and IV")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
