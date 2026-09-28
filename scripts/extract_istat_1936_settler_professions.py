#!/usr/bin/env python3
"""
Tables XIII to XIX of the 1936 census: the settler population's economic
activity, professional position and individual profession.

Source: Istituto Centrale di Statistica, `VIII Censimento generale della
popolazione 1936, Volume V, Libia, Isole italiane dell'Egeo, Tientsin`,
Sezione II, Popolazione nazionale, straniera e assimilata, printed pages 16
to 54.

**Transcribed by eye** and validated before anything is published. The
transcriptions are committed as `data/raw/istat/libya_1936_table{13..19}.csv`
and are the source.

## What they hold

  XIII  the population present with a habitual dwelling, all ages, by
        circumscription and by the nine categories of economic activity,
        with the artisans among those at work and the inactive
  XIV   those aged 10 and over by category, class and main subclass of
        activity and by professional position, for Libya and the municipi
        of Tripoli and Bengasi, with the familiari coadiuvanti
  XV    the same people by category and position with their civil status,
        and the families they head: members, dependants (improduttivi),
        dependants under 15 and domestic servants; for Libya and by province
  XVI   the same people by individual profession (numbered 1 to 260 in the
        volume, number 129 skipped by the printer) and position
  XVII  the padroni (owners employing others) by class of activity, with
        their coadiuvanti, and the non-professional conditions
  XVIII the same people by position, sex and age group
  XIX   the same people by category, class, dependence (independent or
        employed), position, qualification and individual profession

`settler` is shorthand for the volume's `popolazione nazionale, straniera e
assimilata`.

## Checks, and crossings to other tables

  XIII  the nine categories add to the working total, which with the
        inactive is the
        whole; artisans never exceed those at work; every circumscription with
        parts equals their sum and the provinces add to Libya; the whole
        equals table IV's habitual population in all 69 rows
  XIV   M + F = MF in the three areas; positions add to the block total;
        classes add to their category; the categories equal XIII's Libya
        line, with agriculture and hunting-fishing merged and liberal arts and
        worship merged, as XIII prints them
  XV    M + F = MF; the unmarried and the married never exceed the workers;
        dependants never exceed members; positions add to the block total;
        the five provinces add to Libya in every cell; categories equal XIV
  XVI   positions add to each profession; professions add to the
        agricultural and non-agricultural totals; the two add to the whole;
        position totals equal XIV's `In complesso, per posizione`
  XVII  classes add to categories and categories to the padroni; the padroni
        equal XVI's and the non-professional conditions equal XIV's
  XVIII age groups add to each sex; agricultural plus non-agricultural
        positions give the whole; positions equal XIV and XVI
  XIX   every node of the tree equals the sum of its children, coadiuvanti
        included; categories equal XIV; positions equal XVIII; the padroni
        of each class, and their coadiuvanti, equal XVII

## Source misprints

XIX prints three figures that break its own sums. Each is corrected below
only where two independent sums agree on the value, and each is kept as
printed in the raw file:

  class 9 (Industrie poligrafiche), padroni, coadiuvanti F printed 1:
      M + F = MF (8 = 6 + 2) and XVII's class 9 both give 2
  class 15 (Industrie del vestiario), padroni, coadiuvanti MF printed as a
      dash: M + F (2 + 4) and XVII's class 15 both give 6
  class 24 (Comunicazioni), impiegati amministrativi, `Addetti agli uffici`
      printed as dashes: the professions beneath it and its parent line
      (197 178 19, with the sales line at zero) both give 197 178 19

Outputs, under data/processed/istat/:
  libya_1936_settler_activity.csv            XIII, long
  libya_1936_settler_activity_position.csv   XIV, long
  libya_1936_settler_activity_families.csv   XV, long
  libya_1936_settler_professions.csv         XVI, long
  libya_1936_settler_padroni.csv             XVII, long
  libya_1936_settler_position_age.csv        XVIII, long
  libya_1936_settler_activity_class.csv      XIX, long
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"

CATS13 = ("agriculture_hunting_fishing", "industry",
          "transport_communications", "commerce", "credit_insurance",
          "liberal_arts_worship", "public_administration",
          "private_administration", "domestic_service")
ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI")
# XIV's category numerals mapped to XIII's merged columns
CAT_TO_13 = {"I": 0, "II": 0, "III": 1, "IV": 2, "V": 3, "VI": 4, "VII": 5,
             "X": 5, "VIII": 6, "IX": 7, "XI": 8}
AGES = ("10_14", "15_17", "18_20", "21_24", "25_34", "35_44", "45_54",
        "55_64", "65_plus", "unknown")
SEX = ("mf", "m", "f")

# (seq in libya_1936_table19.csv, field) -> (printed, corrected)
MISPRINTS = {
    (196, "coadiuvanti"): ((8, 6, 1), (8, 6, 2)),
    (364, "coadiuvanti"): ((0, 2, 4), (6, 2, 4)),
    (586, "persons"): ((0, 0, 0), (197, 178, 19)),
}


def read(name):
    with open(RAW / name, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k, v in r.items():
            if v is not None and v.isdigit() and k not in (
                    "code", "convention_number", "number", "class"):
                r[k] = int(v)
    return rows


def triple(r, prefix=""):
    return tuple(r[f"{prefix}{s}"] for s in SEX)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def total(rows):
    out = (0, 0, 0)
    for t in rows:
        out = add(out, t)
    return out


def audit_13(xiii, iv, bad):
    for r in xiii:
        n = r["name"]
        if sum(r[c] for c in CATS13) != r["active_total"]:
            bad.append(f"XIII {n}: categories != working total")
        if r["active_total"] + r["inactive"] != r["habitual_mf"]:
            bad.append(f"XIII {n}: working + inactive != whole")
        if r["active_artisans"] > r["active_total"]:
            bad.append(f"XIII {n}: artisans exceed the working total")
    cols = ("habitual_mf",) + CATS13 + ("active_total", "active_artisans",
                                        "inactive")
    kids = defaultdict(list)
    for r in xiii:
        if r["parent"]:
            kids[r["parent"]].append(r)
    libya = next(r for r in xiii if r["level"] == "colony")
    kids[libya["name"]] = [r for r in xiii if r["level"] == "provincia"]
    for r in xiii:
        for c in cols:
            if kids[r["name"]] and sum(k[c] for k in kids[r["name"]]) != r[c]:
                bad.append(f"XIII {r['name']} {c}: parts do not add up")
    ivby = {r["name"]: r for r in iv}
    for r in xiii:
        if ivby[r["name"]]["habitual_mf"] != r["habitual_mf"]:
            bad.append(f"XIII {r['name']}: whole != table IV habitual")
    return libya, len(xiii)


def blocks_14(xiv):
    blocks = []
    for r in xiv:
        if not blocks or blocks[-1]["block"] != r["block"] \
                or blocks[-1]["level"] != r["level"]:
            blocks.append({"level": r["level"], "block": r["block"],
                           "lines": [], "T": None, "c": None})
        b = blocks[-1]
        v = tuple(r[f"{a}_{s}"] for a in ("libia", "tripoli", "bengasi")
                  for s in SEX)
        if r["line"] == "Totale":
            b["T"] = v
        elif r["line"].startswith("di cui"):
            b["c"] = v
        else:
            b["lines"].append((r["line"], v))
    return blocks


def audit_14(xiv, libya13, bad):
    blocks = blocks_14(xiv)
    for b in blocks:
        for name, v in b["lines"] + [("T", b["T"])] + (
                [("c", b["c"])] if b["c"] else []):
            for g in (0, 3, 6):
                if v[g + 1] + v[g + 2] != v[g]:
                    bad.append(f"XIV {b['block']} {name}: M + F != MF")
        if b["lines"]:
            s = tuple(sum(v[c] for _, v in b["lines"]) for c in range(9))
            if s != b["T"]:
                bad.append(f"XIV {b['block']}: positions != total")
    cat, classes = None, []

    def close():
        if cat and classes:
            s = tuple(sum(x["T"][c] for x in classes) for c in range(9))
            if s != cat["T"]:
                bad.append(f"XIV {cat['block']}: classes != category")
    for b in blocks:
        if b["level"] == "category":
            close()
            cat, classes = b, []
        elif b["level"] == "class":
            classes.append(b)
    close()
    cats = {b["block"].split(".")[0]: b for b in blocks
            if b["level"] == "category"}
    merged = [0] * 9
    for k, i in CAT_TO_13.items():
        merged[i] += cats[k]["T"][0]
    for i, c in enumerate(CATS13):
        if merged[i] != libya13[c]:
            bad.append(f"XIV {c}: {merged[i]} != XIII {libya13[c]}")
    return blocks, cats, 9


def audit_15(xv, cats14, bad):
    cols = [k for k in xv[0] if k not in ("seq", "level", "area", "block",
                                          "line")]
    blocks = defaultdict(list)
    for r in xv:
        blocks[(r["area"], r["block"])].append(r)
    for key, rows in blocks.items():
        lines = [r for r in rows if r["line"] != "Totale"]
        tot = next(r for r in rows if r["line"] == "Totale")
        for r in rows:
            w = f"XV {key} {r['line']}"
            if r["addetti_m"] + r["addetti_f"] != r["addetti_mf"]:
                bad.append(f"{w}: M + F != MF")
            if r["celibi_nubili_mf"] + r["coniugati_vedovi_mf"] > \
                    r["addetti_mf"]:
                bad.append(f"{w}: civil states exceed workers")
            if r["improduttivi_mf"] > r["membri_mf"] or \
                    r["improduttivi_under15_mf"] > r["improduttivi_mf"]:
                bad.append(f"{w}: dependants exceed members")
        for c in cols:
            if sum(r[c] for r in lines) != tot[c]:
                bad.append(f"XV {key} {c}: lines != total")
    areas = [a for a, b in blocks if b == "Totale generale" and a != "Libia"]
    libia = blocks[("Libia", "Totale generale")]
    for i, r in enumerate(libia):
        for c in cols:
            s = sum(blocks[(a, "Totale generale")][i][c] for a in areas)
            if s != r[c]:
                bad.append(f"XV {r['line']} {c}: provinces != Libya")
    checked = 0
    for r in libia:
        k = r["line"]
        if k in cats14:
            checked += 1
            want = cats14[k]["T"][:3]
            if k == "XII":
                # XV folds the 201 without an indicated activity into XII
                want = add(want, cats14["Senza indicazione di attivita "
                                        "professionale"]["T"][:3])
            if (r["addetti_mf"], r["addetti_m"], r["addetti_f"]) != want:
                bad.append(f"XV category {k} != XIV")
    for (area, block), rows in blocks.items():
        k = block.split(".")[0]
        if area == "Libia" and k in cats14:
            tot = next(r for r in rows if r["line"] == "Totale")
            if (tot["addetti_mf"], tot["addetti_m"], tot["addetti_f"]) != \
                    cats14[k]["T"][:3]:
                bad.append(f"XV block {block} != XIV")
            checked += 1
    return len(areas), checked


def audit_16(xvi, pos14, bad):
    prof = {}
    positions = defaultdict(list)
    for r in xvi:
        if r["kind"] == "profession":
            if r["position"]:
                positions[r["number"]].append(triple(r))
            else:
                prof[r["number"]] = r
    for n, r in prof.items():
        if positions[n] and total(positions[n]) != triple(r):
            bad.append(f"XVI {n}: positions != profession")
        if r["m"] + r["f"] != r["mf"]:
            bad.append(f"XVI {n}: M + F != MF")
    tot = {(r["scope"], r["position"], r["measure"]): triple(r)
           for r in xvi if r["kind"] == "total"}
    padroni = next(triple(r) for r in xvi if r["kind"] == "padroni"
                   and r["measure"] == "persons")
    agri = total(triple(r) for r in prof.values() if r["scope"] == "agri")
    nonagri = total(triple(r) for r in prof.values()
                    if r["scope"] == "nonagri")
    if agri != tot[("agri", "", "persons")]:
        bad.append("XVI agricultural professions != total")
    if add(nonagri, padroni) != tot[("nonagri", "", "persons")]:
        bad.append("XVI non-agricultural professions != total")
    if add(tot[("agri", "", "persons")], tot[("nonagri", "", "persons")]) \
            != tot[("all", "", "persons")]:
        bad.append("XVI agri + non-agri != whole")
    bypos = defaultdict(list)
    for r in xvi:
        if r["kind"] == "profession" and r["position"] \
                and r["scope"] == "nonagri":
            bypos[r["position"]].append(triple(r))
    bypos["A"].append(padroni)
    for p in "ABCDEFGHI":
        if total(bypos[p]) != tot[("nonagri", p, "persons")]:
            bad.append(f"XVI non-agri position {p}: professions != total")
        a = tot.get(("agri", p, "persons"), (0, 0, 0))
        if add(a, tot[("nonagri", p, "persons")]) != \
                tot[("all", p, "persons")]:
            bad.append(f"XVI position {p}: agri + non-agri != whole")
        if tot[("all", p, "persons")] != pos14[p]:
            bad.append(f"XVI position {p} != XIV")
    if tot[("all", "", "coadiuvanti")] != pos14["c"]:
        bad.append("XVI coadiuvanti != XIV")
    numbers = sorted(int(k) for k in prof)
    gaps = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    if gaps != [129]:
        bad.append(f"XVI profession numbers: gaps {gaps}")
    return prof, tot, padroni, 18


def audit_17(xvii, xvi_padroni, pos14, nonprof14, bad):
    for r in xvii:
        for pre in ("padroni_", "coadiuvanti_"):
            if r[pre + "m"] + r[pre + "f"] != r[pre + "mf"]:
                bad.append(f"XVII {r['label']}: M + F != MF")
    # classes 25 to 28 are wholesale and 29 to 39 retail trade; classes 40
    # to 44 sit directly under the commerce category
    kids = defaultdict(list)
    section = category = None
    subs = {}
    for r in xvii:
        if r["level"] == "section":
            section = r
        elif r["level"] == "category":
            category = r
            kids[id(section)].append(r)
        elif r["level"] == "subcategory":
            subs["ingrosso" if "ingrosso" in r["label"] else "minuto"] = r
            kids[id(category)].append(r)
        elif r["level"] == "class":
            c = int(r["class"])
            if section["label"].startswith("B)"):
                kids[id(section)].append(r)
            elif 25 <= c <= 28:
                kids[id(subs["ingrosso"])].append(r)
            elif 29 <= c <= 39:
                kids[id(subs["minuto"])].append(r)
            else:
                kids[id(category)].append(r)
    for r in xvii:
        if kids[id(r)]:
            for pre in ("padroni_", "coadiuvanti_"):
                if total(triple(k, pre) for k in kids[id(r)]) != \
                        triple(r, pre):
                    bad.append(f"XVII {r['label']}: parts != {pre[:-1]}")
    sec = {r["label"][0]: r for r in xvii if r["level"] == "section"}
    if triple(sec["A"], "padroni_") != xvi_padroni:
        bad.append("XVII padroni != XVI")
    if triple(sec["B"], "padroni_") != nonprof14:
        bad.append("XVII non-professional != XIV")
    if triple(sec["C"], "padroni_") != pos14["unspec"]:
        bad.append("XVII unspecified != XIV")
    return {r["class"]: r for r in xvii if r["level"] == "class"}, 3


def audit_18(xviii, pos14, xvi_tot, bad):
    by = {(r["group"], r["position"]): r for r in xviii}
    for r in xviii:
        w = f"XVIII {r['group']} {r['position']}"
        if r["m"] + r["f"] != r["mf"]:
            bad.append(f"{w}: M + F != MF")
        for s in ("m", "f"):
            if sum(r[f"{a}_{s}"] for a in AGES) != r[s]:
                bad.append(f"{w}: ages != {s}")
        if r["coadiuvanti_m"] + r["coadiuvanti_f"] != r["coadiuvanti_mf"]:
            bad.append(f"{w}: coadiuvanti M + F != MF")
    cols = [k for k in xviii[0] if k not in ("seq", "group", "position")]
    for g in ("Professioni agricole", "Professioni non agricole",
              "In complesso"):
        rows = [r for r in xviii if r["group"] == g]
        tot = next(r for r in rows if r["position"] == "Totale")
        for c in cols:
            if sum(r[c] for r in rows if r is not tot) != tot[c]:
                bad.append(f"XVIII {g} {c}: positions != total")
    checked = 0
    for r in xviii:
        if r["group"] != "In complesso" or r["position"] == "Totale":
            continue
        p = r["position"][0] if r["position"][1] == ")" else None
        parts = [by[(g, r["position"])] for g in
                 ("Professioni agricole", "Professioni non agricole")
                 if (g, r["position"]) in by]
        if p:
            for c in cols:
                if sum(x[c] for x in parts) != r[c]:
                    bad.append(f"XVIII {r['position']} {c}: agri + "
                               f"non-agri != whole")
            if triple(r) != pos14[p] or triple(r) != xvi_tot[("all", p,
                                                              "persons")]:
                bad.append(f"XVIII {r['position']} != XIV or XVI")
            checked += 2
    nonprof = next(r for r in xviii if r["group"] == "Condizioni non "
                   "professionali")
    unspec = next(r for r in xviii if r["group"] == "Senza indicazione")
    for g, key in ((nonprof, "nonprof"), (unspec, "unspec")):
        if triple(g) != pos14[key]:
            bad.append(f"XVIII {g['group']} != XIV")
        checked += 1
    grand = by[("In complesso", "Totale")]
    if triple(grand) != pos14["T"]:
        bad.append("XVIII whole != XIV")
    return by, checked + 1


LV19 = {"category": 0, "class": 1, "dependence": 2, "position": 3,
        "group": 4, "subgroup": 5, "profession": 6}


def tree_19(xix):
    nodes = []
    stack = []
    lastx = None
    for r in xix:
        n = dict(r, kids=[], parent=None,
                 persons=triple(r),
                 coad=None if r["coadiuvanti_mf"] == "" else
                 triple(r, "coadiuvanti_"), notes=[])
        for field in ("persons", "coadiuvanti"):
            key = (r["seq"], field)
            if key in MISPRINTS:
                printed, fixed = MISPRINTS[key]
                have = n["persons"] if field == "persons" else n["coad"]
                if have != printed:
                    raise SystemExit(f"XIX seq {r['seq']}: expected printed "
                                     f"{printed}, raw has {have}")
                if field == "persons":
                    n["persons"] = fixed
                else:
                    n["coad"] = fixed
                n["notes"].append(f"{field} printed {printed}, corrected "
                                  f"to {fixed}")
        if r["level"] == "di_cui":
            n["parent"] = stack[-1]
            lastx = n
        elif r["level"] == "di_cui_detail":
            n["parent"] = lastx
            lastx["kids"].append(n)
        else:
            while stack and LV19[stack[-1]["level"]] >= LV19[r["level"]]:
                stack.pop()
            if stack:
                n["parent"] = stack[-1]
                stack[-1]["kids"].append(n)
            stack.append(n)
        nodes.append(n)
    return nodes


def audit_19(nodes, cats14, by18, x17, bad):
    for n in nodes:
        w = f"XIX {n['seq']} {n['label']}"
        v = n["persons"]
        if v[1] + v[2] != v[0]:
            bad.append(f"{w}: M + F != MF")
        if n["coad"] and n["coad"][1] + n["coad"][2] != n["coad"][0]:
            bad.append(f"{w}: coadiuvanti M + F != MF")
        if n["kids"]:
            if total(k["persons"] for k in n["kids"]) != v:
                bad.append(f"{w}: parts != whole")
            if n["coad"] and total(k["coad"] or (0, 0, 0)
                                   for k in n["kids"]) != n["coad"]:
                bad.append(f"{w}: coadiuvanti parts != whole")
    checked = 0
    cats = [n for n in nodes if n["level"] == "category"]
    for n in cats:
        if n["code"] in cats14:
            checked += 1
            if n["persons"] != cats14[n["code"]]["T"][:3]:
                bad.append(f"XIX category {n['code']} != XIV")
    pos = defaultdict(list)
    coad = defaultdict(list)
    for n in nodes:
        if n["level"] == "position":
            pos[n["code"]].append(n["persons"])
            if n["coad"]:
                coad[n["code"]].append(n["coad"])
    for p in "ABCDEFGHI":
        checked += 1
        if total(pos[p]) != triple(by18[("In complesso", POS18[p])]):
            bad.append(f"XIX position {p} != XVIII")
    for p in "ABC":
        checked += 1
        if total(coad[p]) != triple(by18[("In complesso", POS18[p])],
                                    "coadiuvanti_"):
            bad.append(f"XIX coadiuvanti {p} != XVIII")
    for n in nodes:
        if n["level"] != "class":
            continue
        pa = [p for d in n["kids"] for p in d["kids"] if p["code"] == "A"]
        c = n["code"]
        if c in x17 and int(c) < 69:
            checked += 2
            if total(p["persons"] for p in pa) != triple(x17[c], "padroni_"):
                bad.append(f"XIX class {c} padroni != XVII")
            if total(p["coad"] or (0, 0, 0) for p in pa) != \
                    triple(x17[c], "coadiuvanti_"):
                bad.append(f"XIX class {c} padroni coadiuvanti != XVII")
        elif c in x17:
            checked += 1
            if n["persons"] != triple(x17[c], "padroni_"):
                bad.append(f"XIX class {c} != XVII")
        elif pa and c != "1":
            bad.append(f"XIX class {c}: padroni missing from XVII")
    return checked


POS18 = {"A": "A) Padroni", "B": "B) Artigiani con dipendenti",
         "C": "C) Artigiani senza dipendenti",
         "D": "D) Liberi professionisti", "E": "E) Dirigenti",
         "F": "F) Impiegati", "G": "G) Personale di servizio e di fatica",
         "H": "H) Operai", "I": "I) Lavoranti a domicilio"}


def write(name, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {name}: {len(rows):,} rows")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    iv = read("libya_1936_table4.csv")
    xiii = read("libya_1936_table13.csv")
    xiv = read("libya_1936_table14.csv")
    xv = read("libya_1936_table15.csv")
    xvi = read("libya_1936_table16.csv")
    xvii = read("libya_1936_table17.csv")
    xviii = read("libya_1936_table18.csv")
    xix = read("libya_1936_table19.csv")

    bad = []
    checked = 0
    libya13, n = audit_13(xiii, iv, bad)
    checked += n
    blocks, cats14, n = audit_14(xiv, libya13, bad)
    checked += n
    group = next(b for b in blocks if b["block"].startswith("In complesso"))
    pos14 = {}
    for name, v in group["lines"]:
        if name[1] == ")":
            pos14[name[0]] = v[:3]
        elif name.startswith("Condizioni"):
            pos14["nonprof"] = v[:3]
        elif name.startswith("Senza"):
            pos14["unspec"] = v[:3]
    pos14["T"] = group["T"][:3]
    pos14["c"] = group["c"][:3]
    _, n = audit_15(xv, cats14, bad)
    checked += n
    prof, tot16, padroni16, n = audit_16(xvi, pos14, bad)
    checked += n
    x17, n = audit_17(xvii, padroni16, pos14, pos14["nonprof"], bad)
    checked += n
    by18, n = audit_18(xviii, pos14, tot16, bad)
    checked += n
    nodes = tree_19(xix)
    checked += audit_19(nodes, cats14, by18, x17, bad)
    if bad:
        print(f"{len(bad)} checks failed:")
        for b in bad[:40]:
            print(f"  {b}")
        sys.exit(1)

    rows13 = []
    for r in xiii:
        for c in ("habitual_mf",) + CATS13 + ("active_total",
                                              "active_artisans", "inactive"):
            rows13.append({"order": r["order"], "level": r["level"],
                           "parent": r["parent"], "name": r["name"],
                           "measure": c, "persons": r[c]})
    rows14 = []
    for r in xiv:
        for a, area in (("libia", "Libia"), ("tripoli", "municipio di "
                        "Tripoli"), ("bengasi", "municipio di Bengasi")):
            for s in SEX:
                rows14.append({
                    "seq": r["seq"], "level": r["level"],
                    "activity": r["block"], "position": r["line"],
                    "area": area, "sex": s.upper(),
                    "persons": r[f"{a}_{s}"]})
    rows15 = []
    measures = [k for k in xv[0] if k not in ("seq", "level", "area",
                                              "block", "line")]
    for r in xv:
        for m in measures:
            what, s = m.rsplit("_", 1)
            rows15.append({
                "seq": r["seq"], "area": r["area"],
                "category": r["block"], "line": r["line"], "measure": what,
                "sex": s.upper(), "value": r[m]})
    rows16 = []
    for r in xvi:
        for s in SEX:
            rows16.append({
                "seq": r["seq"], "kind": r["kind"], "scope": r["scope"],
                "section": r["section"], "number": r["number"],
                "code": r["code"], "profession": r["profession"],
                "position": r["position"], "measure": r["measure"],
                "sex": s.upper(), "persons": r[s]})
    rows17 = []
    for r in xvii:
        for pre in ("padroni", "coadiuvanti"):
            for s in SEX:
                rows17.append({
                    "seq": r["seq"], "level": r["level"],
                    "class": r["class"], "label": r["label"],
                    "measure": pre, "sex": s.upper(),
                    "persons": r[f"{pre}_{s}"]})
    rows18 = []
    for r in xviii:
        for s in SEX:
            rows18.append({"group": r["group"], "position": r["position"],
                           "age": "all", "measure": "persons",
                           "sex": s.upper(), "persons": r[s]})
            rows18.append({"group": r["group"], "position": r["position"],
                           "age": "all", "measure": "coadiuvanti",
                           "sex": s.upper(),
                           "persons": r[f"coadiuvanti_{s}"]})
        for a in AGES:
            for s in ("m", "f"):
                rows18.append({"group": r["group"],
                               "position": r["position"],
                               "age": a.replace("_", "-").replace(
                                   "-plus", "+"),
                               "measure": "persons", "sex": s.upper(),
                               "persons": r[f"{a}_{s}"]})
    rows19 = []
    for n in nodes:
        path = []
        p = n["parent"]
        while p:
            path.append(p)
            p = p["parent"]
        cat = next((x for x in path if x["level"] == "category"), None)
        cls = next((x for x in path if x["level"] == "class"), None)
        for field, vals in (("persons", n["persons"]),
                            ("coadiuvanti", n["coad"])):
            if vals is None:
                continue
            for s, v in zip(SEX, vals):
                rows19.append({
                    "seq": n["seq"], "level": n["level"],
                    "category": cat["code"] if cat else (
                        n["code"] if n["level"] == "category" else ""),
                    "class": cls["code"] if cls else (
                        n["code"] if n["level"] == "class" else ""),
                    "code": n["code"],
                    "convention_number": n["convention_number"],
                    "label": n["label"], "measure": field,
                    "sex": s.upper(), "persons": v,
                    "note": "; ".join(n["notes"])})
    write("libya_1936_settler_activity.csv", rows13)
    write("libya_1936_settler_activity_position.csv", rows14)
    write("libya_1936_settler_activity_families.csv", rows15)
    write("libya_1936_settler_professions.csv", rows16)
    write("libya_1936_settler_padroni.csv", rows17)
    write("libya_1936_settler_position_age.csv", rows18)
    write("libya_1936_settler_activity_class.csv", rows19)

    print()
    print(f"  settlers at work: {libya13['active_total']:,} of "
          f"{libya13['habitual_mf']:,} with a habitual dwelling; "
          f"{libya13['public_administration']:,} in public "
          f"administration")
    soldiers = next(n for n in nodes if n["level"] == "class"
                    and n["code"] == "61")
    print(f"  defence of the country: {soldiers['persons'][0]:,}; "
          f"domestic servants: {prof['257']['mf']:,}, "
          f"{prof['257']['f']:,} of them women")
    print(f"  {len(prof)} professions, {len(nodes)} lines in XIX, "
          f"{len(MISPRINTS)} source misprints corrected")
    print("\n  [ok ] every printed identity holds in all seven tables")
    print(f"  [ok ] {checked} crossings agree between XIII to XIX and "
          f"table IV")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
