#!/usr/bin/env python3
"""
Population of Libya as the `Annuario Statistico Italiano` prints it, 1912 to
1943, and the movement of the settler population in 1937.

Source: the colonial chapter of the yearbooks, located by
`scripts/extract_istat_annuario_index.py`. **Transcribed by eye** from page
images, eleven pages in nine volumes, and committed as
`data/raw/istat/libya_annuario_population.csv` (one row per printed figure)
and `data/raw/istat/libya_annuario_population_movement.csv`.

## What the yearbooks add, and what they only repeat

The yearbooks print five kinds of population figure, and they are kept apart
by `reference`:

  census 1931 final        the 1936 volume, by commissariato: settlers and
                           Libyans by sex, and for Libyans dwelling type,
                           religion and "race"; with families and area by
                           colony. The census volume of 1931 as transcribed
                           here (tables I to III) has no religion, race or
                           dwelling type, so these are new.
  census 1931 provisional  the 1933 volume: settlers and Libyans by colony,
                           and Libyans by eight religions
  census 1936 provisional  the 1937 and 1938 volumes: 839,524 people by
                           province, settlers by sex, Libyans by dwelling
                           type and religion, labelled "dati provvisori"
  census 1936 final        the 1939, 1940 and 1943 volumes: Libyan residents
                           by dwelling type and sex, religion, race and
                           language, and civil status, and the Sahara Libico
                           by sottozona; all a reprint of census tables II,
                           XXII and XXX
  1911 and 1912            the Ottoman census of 3 July 1911 for
                           Tripolitania proper and the city of Tripoli, and
                           an early planimetric estimate of Libya's area, both
                           from the running text of the first two volumes

The movement file gives the settler population (national, foreign and
assimilated, without the garrison) present at the start and end of 1937 by
province, with births, deaths, immigrants and emigrants.

## Checks

  * every table's own arithmetic: dwelling types, religions, races,
    languages and civil states add to the whole; M + F = MF; provinces add
    to their total and the total plus the Sahara Libico to Libya; the
    commissariati add to their colony; settlers plus Libyans give the whole;
  * every figure printed in more than one volume agrees across them;
  * **census 1936 final**: every figure equals the census volume as already
    transcribed (tables II, XXII and XXX);
  * **census 1931 final**: every figure the 1931 table II transcription
    carries (present, settlers, Libyans, and their men) is equal;
  * the movement table: births minus deaths, immigrants minus emigrants,
    their sum, and start plus increase gives the end, for every province
    and the total.

The provisional figures are published as printed and compared with the final
ones in the report, not checked against them: they differ, which is why the
volume calls them provisional.

Outputs, under data/processed/istat/:
  libya_annuario_population.csv           one row per figure, printings
                                          merged
  libya_annuario_population_movement.csv  settler population movement, 1937
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"

KEY = ("reference", "population", "area", "group", "dimension", "category",
       "sex")
PROVINCES = ("Provincia di Tripoli", "Provincia di Misurata",
             "Provincia di Bengasi", "Provincia di Derna")
SOTTOZONE = ("Sottozona militare di Brach", "Sottozona militare di Gat",
             "Sottozona militare di Murzuch", "Sottozona militare di Hon",
             "Sottozona militare di el-Giof")
SUMMED = ("dimora", "religion", "race", "language", "civil_status")


def read(name):
    with (RAW / name).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k, v in r.items():
            if v.lstrip("-").isdigit() and k not in ("volume",):
                r[k] = int(v)
    return rows


def children(area, areas):
    """The areas a total is made of, as the tables print them."""
    if area == "Provincie italiane della Libia":
        return list(PROVINCES)
    if area == "LIBIA" and "Provincie italiane della Libia" in areas:
        return ["Provincie italiane della Libia",
                "Territorio Militare del Sud"]
    if area == "LIBIA":
        return list(PROVINCES) + ["Territorio Militare del Sud"]
    if area == "Territorio Militare del Sud":
        return list(SOTTOZONE)
    if area in ("Tripolitania", "Cirenaica"):
        return [a for a in areas if a.startswith(area + ": ")]
    return []


def audit(rows, bad):
    checked = 0
    page = defaultdict(dict)
    for r in rows:
        page[(r["volume"], r["pdf_page"], r["table"])][
            tuple(r[k] for k in KEY)] = r["value"]
    for where, cells in page.items():
        # parts add to wholes within a dimension
        groups = defaultdict(dict)
        for (ref, pop, area, grp, dim, cat, sex), v in cells.items():
            base = dim.split(";")[0]
            kind = dim.split(";")[-1] if ";" in dim else dim
            groups[(ref, pop, area, grp, base, kind, sex)][cat] = v
        for (ref, pop, area, grp, base, kind, sex), d in groups.items():
            if kind in SUMMED:
                total = None
                if kind == "dimora" and "all" in d:
                    total = d["all"]
                    parts = [v for c, v in d.items() if c != "all"]
                else:
                    parts = list(d.values())
                    if base.startswith("dimora="):
                        total = groups.get((ref, pop, area, grp, base, base,
                                            sex), {}).get("all")
                    else:
                        for probe in ((ref, pop, area, grp, "dimora", "dimora",
                                       sex), (ref, pop, area, grp, "total",
                                              "total", sex)):
                            if probe in groups and "all" in groups[probe]:
                                total = groups[probe]["all"]
                                break
                if total is not None and len(parts) > 1:
                    checked += 1
                    if sum(parts) != total:
                        bad.append(f"{where} {area} {grp} {dim_of(base, kind)}"
                                   f" {sex}: parts {sum(parts)} != {total}")
        # M + F = MF
        sexes = defaultdict(dict)
        for (ref, pop, area, grp, dim, cat, sex), v in cells.items():
            sexes[(ref, pop, area, grp, dim, cat)][sex] = v
        for k, d in sexes.items():
            if {"MF", "M", "F"} <= set(d):
                checked += 1
                if d["M"] + d["F"] != d["MF"]:
                    bad.append(f"{where} {k}: M + F != MF")
        # areas add to their totals
        areas = {k[2] for k in cells}
        for k, v in cells.items():
            kids = [a for a in children(k[2], areas) if a in areas]
            if len(kids) < 2:
                continue
            def cell(a):
                got = cells.get(k[:2] + (a,) + k[3:])
                if got is None and k[4].startswith("dimora=all"):
                    # el-Giof prints its one dwelling type and no total line
                    rest = k[4][len("dimora=all"):]
                    only = {d.split(";")[0] for (_, _, ar, _, d, _, _) in cells
                            if ar == a and d.startswith("dimora=")}
                    if len(only) == 1:
                        got = cells.get(k[:2] + (a, k[3], only.pop() + rest)
                                        + k[5:])
                return got
            if all(cell(a) is None for a in kids):
                continue
            vals = [cell(a) or 0 for a in kids]
            checked += 1
            if sum(vals) != v:
                bad.append(f"{where} {k}: areas {sum(vals)} != {v}")
        # settlers plus Libyans give the whole
        for k, v in cells.items():
            if k[3] != "all" or k[4] != "total":
                continue
            s = cells.get(k[:3] + ("settlers",) + k[4:])
            n = cells.get(k[:3] + ("national",) + k[4:])
            f = cells.get(k[:3] + ("foreign",) + k[4:])
            lib = cells.get(k[:3] + ("libyan",) + k[4:])
            if lib is None:
                continue
            settlers = s if s is not None else (
                n + f if None not in (n, f) else None)
            if settlers is not None:
                checked += 1
                if settlers + lib != v:
                    bad.append(f"{where} {k}: settlers + Libyans != whole")
    return checked


def dim_of(base, kind):
    return base if base == kind else f"{base};{kind}"


def printings_agree(rows, bad):
    seen = defaultdict(set)
    for r in rows:
        seen[tuple(r[k] for k in KEY)].add((r["volume"], r["value"]))
    repeated = 0
    for k, s in seen.items():
        if len({v for _, v in s}) > 1:
            bad.append(f"{k}: printings differ {sorted(s)}")
        if len(s) > 1:
            repeated += 1
    return seen, repeated


def census_1936(rows, bad):
    t22 = {(r["name"], r["dimora"]): r for r in read("libya_1936_table22.csv")}
    t30 = {r["area"]: r for r in read("libya_1936_table30.csv")
           if r["religion"] == "complesso" and r["age"] == "Totale"}
    t2 = {r["name"]: r for r in read("libya_1936_table2.csv")}
    dim = {"all": "Tot", "stabile": "st", "seminomade": "sn", "nomade": "n"}
    col = {("religion", "muslim"): "muslim", ("religion", "jewish"): "jewish",
           ("religion", "other"): "other_religion",
           ("race", "arab and arab-berber"): "arab", ("race", "berber"): "berber",
           ("race", "cologhli"): "cologhli", ("race", "negro"): "negro",
           ("race", "other"): "other_race", ("language", "arabic"): "lang_arabic",
           ("language", "berber"): "lang_berber",
           ("language", "other"): "lang_other",
           ("speaks_italian", "yes"): "italian"}
    civil = {"single": "celibi", "married": "coniugati", "widowed": "vedovi",
             "divorced": "divorziati", "unknown": "ignoto"}
    checked = 0
    for r in rows:
        if r["reference"] != "census 1936 final":
            continue
        area, v, sex = r["area"], r["value"], r["sex"]
        if area == "Provincie italiane della Libia":
            # the four provinces are each checked, and audit() adds them up
            if r["dimension"] != "total":
                continue
            exp = sum(t2[p]["resident_libyan_mf"] for p in PROVINCES)
        elif r["dimension"] == "area_km2":
            continue
        elif r["group"] == "libyan" and r["dimension"].startswith(
                ("dimora", "religion", "race", "language", "speaks")):
            d, cat = r["dimension"], r["category"]
            if d.startswith("dimora="):
                dimora = dim[d.split(";")[0].split("=")[1]]
                d = d.split(";")[1] if ";" in d else None
            elif d == "dimora":
                dimora, d, cat = dim[cat], None, "all"
            else:
                dimora = "Tot"
            row = t22.get((area, dimora))
            if row is None:
                exp = 0
            elif d is None and cat == "family heads":
                exp = row["heads"]
            elif d is None:
                exp = {"MF": row["mf"], "F": row["f"],
                       "M": row["mf"] - row["f"]}[sex]
            else:
                exp = row[col[(d, cat)]]
        elif r["dimension"] == "civil_status":
            t = t30["Libia" if area == "LIBIA" else area]
            exp = t[f"{civil[r['category']]}_{sex.lower()}"]
        elif r["dimension"] == "total":
            t = t2[area]
            grp = {"all": "total", "national": "national",
                   "foreign": "foreign", "libyan": "libyan"}[r["group"]]
            mf, f = t[f"resident_{grp}_mf"], t[f"resident_{grp}_f"]
            exp = {"MF": mf, "F": f, "M": mf - f}[sex]
        else:
            bad.append(f"census 1936 final: no rule for {r}")
            continue
        checked += 1
        if exp != v:
            bad.append(f"{r['volume']} p{r['pdf_page']} {area} {r['group']} "
                       f"{r['dimension']} {r['category']} {sex}: {v} != "
                       f"census {exp}")
    return checked


def census_1931(rows, bad):
    districts = {}
    with (OUT / "libya_1931_districts.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["level_name"] in ("commissariato", "colony"):
                name = r["colony"] if r["level_name"] == "colony" else \
                    f"{r['colony']}: {r['name']}"
                districts[name] = {k: int(v) for k, v in r.items()
                                   if k.endswith(("_mf", "_f"))}
    checked = 0
    for r in rows:
        if r["reference"] != "census 1931 final" or r["dimension"] != "total":
            continue
        d = districts.get(r["area"])
        if d is None:
            bad.append(f"1931: {r['area']} not in the table II transcription")
            continue
        pairs = {"all": ("present_mf", "present_f"),
                 "libyan": ("indigena_mf", "indigena_f"),
                 "foreign": ("straniera_mf", "straniera_f")}
        if r["group"] == "settlers":
            mf = d["regnicola_mf"] + d["straniera_mf"]
            f = d["regnicola_f"] + d["straniera_f"]
        else:
            mf, f = (d[c] for c in pairs[r["group"]])
        exp = {"MF": mf, "M": mf - f, "F": f}[r["sex"]]
        checked += 1
        if exp != r["value"]:
            bad.append(f"1931 {r['area']} {r['group']} {r['sex']}: "
                       f"{r['value']} != table II {exp}")
    return checked


def movement(bad):
    rows = read("libya_annuario_population_movement.csv")
    cols = ("present_start", "live_births", "deaths", "natural_increase",
            "immigrants", "emigrants", "net_migration", "net_increase",
            "present_end")
    for r in rows:
        if r["live_births"] - r["deaths"] != r["natural_increase"] or \
                r["immigrants"] - r["emigrants"] != r["net_migration"] or \
                r["natural_increase"] + r["net_migration"] != \
                r["net_increase"] or \
                r["present_start"] + r["net_increase"] != r["present_end"]:
            bad.append(f"movement {r['province']}: identities fail")
    total = next(r for r in rows if r["province"] == "Totale")
    for c in cols:
        if sum(r[c] for r in rows if r is not total) != total[c]:
            bad.append(f"movement {c}: provinces != total")
    return rows


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    rows = read("libya_annuario_population.csv")
    bad = []
    identities = audit(rows, bad)
    seen, repeated = printings_agree(rows, bad)
    c36 = census_1936(rows, bad)
    c31 = census_1931(rows, bad)
    mov = movement(bad)
    if bad:
        print(f"{len(bad)} checks failed:")
        for b in bad[:40]:
            print(f"  {b}")
        sys.exit(1)

    out = []
    first = {}
    for r in rows:
        k = tuple(r[c] for c in KEY)
        if k in first:
            continue
        first[k] = r
        vols = sorted({v for v, _ in seen[k]})
        out.append(dict(zip(KEY, k), value=r["value"],
                        table=r["table"], volumes=" ".join(vols),
                        pdf_page=r["pdf_page"]))
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "libya_annuario_population.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"  wrote libya_annuario_population.csv: {len(out):,} rows")
    with (OUT / "libya_annuario_population_movement.csv").open(
            "w", newline="", encoding="utf-8") as fh:
        fields = [k for k in mov[0] if k not in ("volume", "pdf_page")] + [
            "volume", "pdf_page"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(mov)
    print(f"  wrote libya_annuario_population_movement.csv: {len(mov)} rows")

    def get(ref, area, group, dim="total", cat="all", sex="MF", pop=None):
        for k, r in first.items():
            if (k[0], k[2], k[3], k[4], k[5], k[6]) == (ref, area, group, dim,
                                                        cat, sex) and (
                    pop is None or k[1] == pop):
                return r["value"]
    prov = get("census 1936 provisional", "LIBIA", "libyan", "dimora")
    final = get("census 1936 final", "LIBIA", "libyan", "dimora")
    p31 = get("census 1931 provisional", "Tripolitania", "libyan")
    f31 = get("census 1931 final", "Tripolitania", "libyan")
    print()
    print(f"  Libyans, 1936 census: provisional {prov:,}, final {final:,} "
          f"resident; 1931 Tripolitania provisional {p31:,}, final {f31:,}")
    tot = next(r for r in mov if r["province"] == "Totale")
    print(f"  settlers present in 1937: {tot['present_start']:,} to "
          f"{tot['present_end']:,}, {tot['net_migration']:,} of the "
          f"{tot['net_increase']:,} increase by migration")
    print(f"\n  [ok ] every printed identity holds: {identities} sums; "
          f"{repeated} figures printed more than once agree")
    print(f"  [ok ] {c36} figures equal the 1936 census volume and {c31} the "
          f"1931 table II transcription")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
