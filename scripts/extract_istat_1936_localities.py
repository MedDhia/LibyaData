#!/usr/bin/env python3
"""
Read the 1936 Italian census list of Libyan localities, and place each one.

Source: Istituto Centrale di Statistica del Regno d'Italia, `VIII censimento
generale della popolazione, 21 aprile 1936, Volume V: Libia, Isole italiane
dell'Egeo, Tientsin`, Rome 1939, Appendix II, `ELENCO ALFABETICO DELLE LOCALITÀ
DELLA LIBIA INDICATE NELLA TAV. XX CON L'INDICAZIONE DELLA CIRCOSCRIZIONE DI
APPARTENENZA AL 21 APRILE 1936-XIV`. Downloaded from ISTAT's digital library by
`scripts/download_istat_colonial.py`; the PDF is fetched here if it is absent.

This is a gazetteer of Libya as the colonial state recorded it: every locality
named in the census's table XX, with the circumscription it belonged to on 21
April 1936 and the page of table XX where its population is printed.

## Reading the page

Appendix II is eight pages of two column-pairs each, locality on the left of a
pair and circumscription on the right. The columns are recovered by the x
position of each text line and the rows by matching y positions, because the
text stream alone interleaves the pairs.

The census removes a generic word from the head of a name and prints it in
brackets at the end, so that the alphabet runs on the distinctive part. Its own
note lists them: the article `el-`, and `Àin` (spring), `Bir` (well), `Gasr`
(castle), `Gefàra` (plain), `Got` (depression), `Màrsa` (port), `Ras` (cape),
`Sània` (garden), `Sìdi` (marabout), `Uàdi` (valley) and `Zàvia` (lodge). The
bracket is moved back to the front, so `Abbàr (el-)` is read as `el-Abbàr` and
`Amza (Uàdi el-)` as `Uàdi el-Amza`. Both forms are kept.

## Placing a locality

Two steps, and only the first is certain.

**The circumscription.** There are some fifty of them, and the scan spells each
a dozen ways: `Residenza di Tarhùna` comes out as `za di tarhuna`, `i tarhuna`,
`tarhu na` and `tarliuna`. They are matched to a canonical seat by closest
string, which is safe because the list is short, closed and known in advance.

Each seat is then given its Arabic name in `SEATS` below, and the **shabiya
comes from this repository's own concordance**, through
`scripts/libya_places.py`, not from the table. So the assertion made here is a
transliteration, that Italian `Tarhùna` is Arabic ترهونة, and the geography is
the repository's. A seat whose Arabic name the concordance cannot place is left
unresolved and reported rather than guessed.

**The locality itself.** Matching a 1936 Italian transliteration to a 2006
Arabic census name is not a lookup. Both sides are reduced to a consonant
skeleton over classes that the two writing systems agree on, ت and ط both
becoming T, غ ق and ك all becoming K, Italian `gh` and hard `g` likewise, `sc`
becoming the sound ش writes. Vowels go, except where Italian writes the long
vowels that Arabic writes with و and ي.

A match is accepted only when the skeleton is at least four classes long, the
two places are in the same shabiya, and the name is unique in that shabiya on
both sides. The shabiya constraint is the same rule `scripts/match_osm_places.py`
uses, and for the same reason: the census has سوق الجمعة in Murqub while the
gazetteers put it in Tripoli, and الزهراء exists in both Jafara and Wadi al
Shatii.

Expect the locality match to be partial. Colonial transliteration is
inconsistent, the scan is poor, and the 1936 settlement pattern is not the 2006
one: the Italian state moved people, and the places it named include wells,
lodges and farms that no later census counts. The rate is reported rather than
improved by loosening the rule.

Outputs, under data/processed/istat/:
  libya_localities_1936.csv   one row per locality, with its shabiya
  libya_circoscrizioni_1936.csv  one row per circumscription, with its shabiya
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from difflib import get_close_matches
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_opensanctions_libya import ARABIC_ALIASES  # noqa: E402
from libya_places import gazetteer, resolve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "istat"
OUT = ROOT / "data" / "processed" / "istat"
PDF = RAW / ("Censimenti_popolazione_censpop1936_IST0005817vol5_"
             "LibiaIsoleitalianedellEgeoTientsin_IST0005817cp1936_"
             "LibiaIsoleitalianedellEgeoTientsin_OCRottimizzato.pdf")
SOURCE = ("https://ebiblio.istat.it/digibib/Censimenti%20popolazione/censpop1936/"
          "IST0005817vol5_LibiaIsoleitalianedellEgeoTientsin/"
          "IST0005817cp1936_LibiaIsoleitalianedellEgeoTientsin+OCRottimizzato.pdf")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# Appendix II, zero-indexed. Appendix I ends at 238 and Appendix III opens 247.
APPENDIX = range(239, 247)
HEADER_Y = 720
# Column headings and running heads that survive the header cut.
HEADINGS = {"pago", "localita", "circoscrizione", "politicoamministrativa",
            "diappartenenza", "segue", "nb", "pag"}
# A circumscription sits on its locality's baseline and between 40 and 230
# points to its right. Fixed column edges were tried first and lost a sixth of
# the rows: the scan is skewed differently on every page, so the columns are
# not where they are on the page before.
SAME_ROW = 5
OFFSET = (40, 230)

# The generics the census strips to the bracket, from its own note on page 239.
GENERICS = ("el-", "Àin", "Aiùn", "Bir", "Biàr", "Abiàr", "Gasr", "Gsur", "Gseir",
            "Gefàra", "Got", "Màrsa", "Ras", "Sània", "Suàni", "Suènia", "Sìdi",
            "Uàdi", "Uidiàn", "Udèi", "Udeiàt", "Zàvia")

# The circumscription seats, with the Arabic name each transliterates. The
# shabiya is not asserted here: the Arabic name is looked up in the concordance.
SEATS = {
    "tarhuna": "ترهونة", "garian": "غريان", "iefren": "يفرن", "giado": "جادو",
    "cirene": "شحات", "homs": "الخمس", "sabratha": "صبراتة", "nalut": "نالوت",
    "bengasi": "بنغازي", "el gusbat": "القصبات", "zuara": "زوارة",
    "mizda": "مزدة", "agedabia": "أجدابيا", "uadi el agial": "وادي الأجال",
    "gerdes gerrari": "قرضس الجرارى", "el giof": "الجوف",
    "beda littoria": "البيضاء", "traghen": "تراغن", "zanzur": "جنزور",
    "apollonia": "سوسة", "derna": "درنة", "brach": "براك", "sirte": "سرت",
    "tocra": "توكرة", "misurata": "مصراتة", "el azizia": "العزيزية",
    "hon": "هون", "sebha": "سبها", "zliten": "زليتن", "tobruch": "طبرق",
    "gat": "غات", "edri": "إدري", "castel benito": "بن غشير",
    "porto bardia": "البردية", "berghin": "برقن", "sorman": "صرمان",
    "gadames": "غدامس", "murzuch": "مرزق", "uadi etba": "وادي عتبة",
    "el agheila": "العقيلة", "soluch": "سلوق", "el gatrun": "القطرون",
    "barce": "المرج", "giovanni berta": "القبة", "umm el araneb": "أم الأرانب",
    "en nofilia": "النوفلية", "sugh el giumaa": "سوق الجمعة", "zella": "زلة",
    "tolmeta": "طلميثة", "suani ben adem": "سواني بن آدم", "tagiura": "تاجوراء",
    "tripoli": "طرابلس", "el abiar": "الأبيار", "cussabat": "القصبات",
    "misda": "مزدة", "zavia": "الزاوية", "el marg": "المرج",
    "beni ulid": "بني وليد", "gasr ben gascir": "بن غشير",
}

# Seats the concordance cannot place under their own name, given the province
# they sit in. This is a geographic assertion rather than a transliteration, so
# a locality placed this way is marked `asserted` and can be dropped. Four more
# come from `scripts/extract_opensanctions_libya.ARABIC_ALIASES`, which already
# asserts أجدابيا, صبراتة, زليتن and تراغن, and is imported rather than repeated.
SEAT_SHABIYA = {
    "apollonia": "الجبل الأخضر", "castel benito": "طرابلس",
    "cussabat": "المرقب", "el gusbat": "المرقب", "hon": "الجفرة",
    "mizda": "الجبل الغربي", "misda": "الجبل الغربي",
    "porto bardia": "البطنان", "suani ben adem": "الجفارة",
    "tolmeta": "المرج", "uadi el agial": "وادي الحياة",
    "umm el araneb": "مرزق", "zella": "الجفرة",
    "gasr ben gascir": "طرابلس",
}

# Italian colonial orthography to the sound classes Arabic and Latin agree on.
# Order matters: the digraphs are tried first.
ITALIAN = (
    ("sc", "X"), ("gh", "K"), ("ch", "K"), ("gi", "G"), ("ge", "G"),
    ("qu", "KW"), ("b", "B"), ("c", "K"), ("d", "D"), ("f", "F"), ("g", "K"),
    ("h", "H"), ("j", "G"), ("k", "K"), ("l", "L"), ("m", "M"), ("n", "N"),
    ("p", "B"), ("q", "K"), ("r", "R"), ("s", "S"), ("t", "T"), ("v", "W"),
    ("w", "W"), ("x", "X"), ("z", "Z"), ("u", "W"), ("i", "Y"),
    ("a", ""), ("e", ""), ("o", ""), ("y", "Y"),
)
ARABIC = {
    "ب": "B", "ت": "T", "ث": "S", "ج": "G", "ح": "H", "خ": "H", "د": "D",
    "ذ": "D", "ر": "R", "ز": "Z", "س": "S", "ش": "X", "ص": "S", "ض": "D",
    "ط": "T", "ظ": "D", "ع": "", "غ": "K", "ف": "F", "ق": "K", "ك": "K",
    "ل": "L", "م": "M", "ن": "N", "ه": "H", "و": "W", "ي": "Y", "ى": "Y",
    "ء": "", "أ": "", "إ": "", "آ": "", "ا": "", "ة": "H", "ئ": "", "ؤ": "",
}
MIN_SKELETON = 4


def latin_fold(text):
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def skeleton_latin(name):
    """Sound classes of an Italian transliteration."""
    text = re.sub(r"\s+", "", latin_fold(name))
    out, i = [], 0
    while i < len(text):
        for source, target in ITALIAN:
            if text.startswith(source, i):
                out.append(target)
                i += len(source)
                break
        else:
            i += 1
    return collapse("".join(out))


def skeleton_arabic(name):
    """The same classes, from the Arabic."""
    text = re.sub(r"[ً-ْ\s]", "", str(name))
    return collapse("".join(ARABIC.get(c, "") for c in text))


def collapse(skeleton):
    """No class twice in a row, and no trailing H.

    The two systems disagree about doubling, and about the end of a word: the
    census writes Sabràtha and Tarhùna for صبراتة and ترهونة, so the ة is an H
    on one side and part of the vowel on the other.
    """
    return re.sub(r"H$", "", re.sub(r"(.)\1+", r"\1", skeleton))


def unarticled(skeleton):
    """The skeleton without its leading article, if it has one."""
    return skeleton[1:] if skeleton.startswith("L") else skeleton


def voweless(skeleton):
    """The skeleton with W and Y dropped.

    Italian writes a long vowel where Arabic writes none and the reverse:
    Misurata for مصراتة, Hon for هون. Dropping the two semivowels lets those
    meet, at the cost of a shorter and less distinctive key, which is why a
    match on it is recorded under its own rule.
    """
    return re.sub(r"[WY]", "", skeleton)


def fetch_pdf():
    if PDF.exists():
        return
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"fetching {SOURCE.rsplit('/', 1)[-1]} (18 MB)")
    request = urllib.request.Request(SOURCE, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=600) as response:
        PDF.write_bytes(response.read())


def lines_of(page):
    from pdfminer.layout import LTTextContainer, LTTextLine
    out = []
    for element in page:
        if not isinstance(element, LTTextContainer):
            continue
        for line in element:
            if not isinstance(line, LTTextLine):
                continue
            text = " ".join(line.get_text().split())
            if text:
                out.append({"x": line.x0, "y": (line.y0 + line.y1) / 2,
                            "text": text})
    return out


TYPE_WORD = re.compile(r"d[il]stretto|res[a-z]{0,4}nza|mud[a-z]{0,5}[ao]|"
                       r"circondario|commissariato|territorio")


def is_circumscription(text):
    """Which of the two columns a line belongs to, read off the line itself.

    A circumscription names its kind or opens with the table XX page number; a
    locality does neither. Reading the content rather than the position is what
    survives the skew.
    """
    flat = re.sub(r"\s+", "", latin_fold(text))
    return bool(TYPE_WORD.search(flat)) or bool(re.match(r"^\W*\d{2}\b", text))


def read_appendix():
    """One (locality, circumscription) pair per printed row."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams

    rows = []
    for number in APPENDIX:
        page = next(extract_pages(PDF, page_numbers=[number],
                                  laparams=LAParams(line_margin=0.25,
                                                    char_margin=1.5)))
        lines = [ln for ln in lines_of(page) if ln["y"] < HEADER_Y]
        names = [ln for ln in lines if not is_circumscription(ln["text"])]
        seats = [ln for ln in lines if is_circumscription(ln["text"])]
        for name in sorted(names, key=lambda ln: -ln["y"]):
            beside = [s for s in seats
                      if abs(s["y"] - name["y"]) <= SAME_ROW
                      and OFFSET[0] < (s["x"] - name["x"]) < OFFSET[1]]
            best = min(beside, key=lambda s: (abs(s["y"] - name["y"]),
                                              s["x"] - name["x"]), default=None)
            rows.append((number, name["text"], best["text"] if best else ""))
    return rows


def unbracket(name):
    """Put the generic back where the name is read: `Abbàr (el-)` is el-Abbàr."""
    found = re.match(r"^(.*?)\s*[(\[]([^)\]]{1,24})[)\]]\s*\.?$", name.strip())
    if not found:
        return re.sub(r"\s+", " ", name.strip(" .,·'")).strip()
    stem, bracket = found.group(1).strip(), found.group(2).strip()
    generic = latin_fold(bracket).strip()
    if any(generic.startswith(latin_fold(word).strip()[:4] or "\0")
           for word in GENERICS) or generic in ("el", "ez", "es", "en", "er"):
        return re.sub(r"\s+", " ", f"{bracket} {stem}").strip()
    return re.sub(r"\s+", " ", f"{stem} ({bracket})").strip()


# The kind, written every way the scan writes it, including run together with
# the "di" that follows it: "Mudiriadi Brach", "residenza eli tarhuna".
KIND_RUN = re.compile(r"d\s?[il]\s?stretto|r\s?es[a-z ]{0,6}nza|mud[a-z ]{0,6}[ao]|"
                      r"circondario|commissariato|territorio")


def seat_of(text, canon):
    """The circumscription seat, matched to the canonical list."""
    flat = re.sub(r"\s+", " ", latin_fold(text)).strip()
    flat = re.sub(r"\b\d+\b", " ", flat)
    kind = KIND_RUN.search(flat)
    tail = flat[kind.end():] if kind else flat
    # Then whatever follows the last "di", however the scan spelled it: the
    # kind itself often comes out as something KIND_RUN cannot see, "la di
    # Tràghen" for "Mudiria di Tràghen".
    parts = re.split(r"\b(?:di|dl|d1|eli|d|u|j|ii|i)\b", tail)
    tail = parts[-1] if len(parts) > 1 else tail
    tail = re.sub(r"^\s*(?:di|dl|d1|eli|el i)\s*", " ", tail)
    tail = re.sub(r"\s+", " ", tail).strip()
    if len(tail) < 3:
        return "", 0.0
    close = get_close_matches(tail, canon, n=1, cutoff=0.72)
    return (close[0], 1.0) if close else (tail, 0.0)


def kind_of(text):
    flat = re.sub(r"\s+", "", latin_fold(text))
    for pattern, label in ((r"d[il]stretto", "distretto"),
                           (r"res[a-z]{0,4}nza", "residenza"),
                           (r"mud[a-z]{0,4}[ao]", "mudiria"),
                           (r"circondario", "circondario"),
                           (r"commissariato", "commissariato"),
                           (r"territorio", "territorio")):
        if re.search(pattern, flat):
            return label
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    fetch_pdf()

    places, shabiya_keys, scrambled = gazetteer()

    # Every seat's shabiya comes from the concordance, through its Arabic name.
    # Where the concordance does not hold the name, the province is asserted,
    # and the row says which of the two happened.
    seat_place, routes = {}, Counter()
    for seat, arabic in SEATS.items():
        found = resolve(arabic, places, shabiya_keys, scrambled)
        route = "concordance"
        if not found and arabic in ARABIC_ALIASES:
            found = resolve(ARABIC_ALIASES[arabic], places, shabiya_keys, scrambled)
            route = "asserted"
        if not found and seat in SEAT_SHABIYA:
            found = resolve(SEAT_SHABIYA[seat], places, shabiya_keys, scrambled)
            route = "asserted"
        if found:
            found = found[:3] + (route if route == "asserted" else found[3],)
        routes[route if found else "unplaced"] += 1
        seat_place[seat] = (arabic, found)
    print(f"{len(SEATS)} circumscription seats: {dict(routes)}")
    for seat, (arabic, found) in sorted(seat_place.items()):
        if not found:
            print(f"  unplaced: {seat:18s} {arabic}")

    rows = read_appendix()
    print(f"\n{len(rows)} lines read from appendix II")

    canon = list(SEATS)
    localities, unseated = [], 0
    for page, name, circumscription in rows:
        if len(latin_fold(name).strip()) < 3 or name.isupper():
            continue
        # The page carries the census's own glossary of the generic words and
        # the note explaining it; those lines are prose, not places.
        if "=" in circumscription or "=" in name or len(name) > 40:
            continue
        if re.sub(r"[^a-z]", "", latin_fold(name)) in HEADINGS:
            continue
        seat, matched = seat_of(circumscription, canon)
        if not matched:
            unseated += 1
            seat = ""
        arabic, found = seat_place.get(seat, ("", None))
        table = re.search(r"\b(\d{2})\b", circumscription)
        localities.append({
            "locality_it": unbracket(name),
            "locality_printed": name,
            "skeleton": skeleton_latin(unbracket(name)),
            "circoscrizione_it": seat,
            "circoscrizione_kind": kind_of(circumscription),
            "circoscrizione_ar": arabic,
            "shabiya_ar": found[0] if found else "",
            "shabiya_en": found[1] if found else "",
            "shabiya_pcode": found[2] if found else "",
            "shabiya_matched_level": found[3] if found else "",
            "tav_xx_page": table.group(1) if table else "",
            "appendix_page": page + 1,
            "circoscrizione_printed": circumscription,
        })
    print(f"{len(localities)} localities, {unseated} with no readable "
          f"circumscription")

    match_to_concordance(localities, places, shabiya_keys, scrambled)

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "libya_localities_1936.csv", localities)
    seats = [{
        "circoscrizione_it": seat,
        "circoscrizione_ar": arabic,
        "shabiya_ar": found[0] if found else "",
        "shabiya_en": found[1] if found else "",
        "shabiya_pcode": found[2] if found else "",
        "matched_level": found[3] if found else "unresolved",
        "localities": sum(1 for row in localities
                          if row["circoscrizione_it"] == seat),
    } for seat, (arabic, found) in sorted(seat_place.items())]
    write(OUT / "libya_circoscrizioni_1936.csv", seats)
    report(localities, seats)


def match_to_concordance(localities, places, shabiya_keys, scrambled):
    """Join a 1936 locality to a 2006 mahalla, on the skeleton and the shabiya."""
    path = ROOT / "data" / "processed" / "concordance_mahalla.csv"
    with path.open() as fh:
        mahallas = list(csv.DictReader(fh))

    census = defaultdict(lambda: defaultdict(set))
    unarticled_census = defaultdict(lambda: defaultdict(set))
    loose_census = defaultdict(lambda: defaultdict(set))
    for row in mahallas:
        key = skeleton_arabic(row["mahalla_ar"])
        if len(key) < MIN_SKELETON:
            continue
        census[row["shabiya_en"]][key].add(row["mahalla_id"])
        unarticled_census[row["shabiya_en"]][unarticled(key)].add(row["mahalla_id"])
        loose_census[row["shabiya_en"]][voweless(key)].add(row["mahalla_id"])
    mahalla_by_id = {row["mahalla_id"]: row for row in mahallas}

    # A 1936 name that repeats inside its own shabiya cannot be matched either.
    mine = defaultdict(Counter)
    for row in localities:
        if row["shabiya_en"] and len(row["skeleton"]) >= MIN_SKELETON:
            mine[row["shabiya_en"]][row["skeleton"]] += 1

    for row in localities:
        row["mahalla_id"] = row["mahalla_ar"] = row["match_rule"] = ""
        key, shabiya = row["skeleton"], row["shabiya_en"]
        if not shabiya or len(key) < MIN_SKELETON:
            row["match_rule"] = "skeleton too short" if shabiya else "no shabiya"
            continue
        if mine[shabiya][key] > 1:
            row["match_rule"] = "name repeats in 1936 shabiya"
            continue
        # Three keys, strictest first: the skeleton, the skeleton without its
        # article, and the skeleton without its semivowels.
        for rule, index, wanted in (
                ("skeleton and shabiya", census, key),
                ("article dropped", unarticled_census, unarticled(key)),
                ("semivowels dropped", loose_census, voweless(key))):
            if len(wanted) < MIN_SKELETON:
                continue
            hits = index.get(shabiya, {}).get(wanted, set())
            if len(hits) == 1:
                mahalla = mahalla_by_id[next(iter(hits))]
                row["mahalla_id"] = mahalla["mahalla_id"]
                row["mahalla_ar"] = mahalla["mahalla_ar"]
                row["match_rule"] = rule
                break
            if len(hits) > 1:
                row["match_rule"] = "several mahallas of that sound in the shabiya"
                break
        else:
            row["match_rule"] = "no mahalla of that sound in the shabiya"

    # One 1936 locality to one mahalla. Where two claim the same mahalla, one of
    # them is wrong and there is nothing in the names to say which, so both are
    # given up: el-Gsèba and el-Gùsba both sound like القصبة in Jabal al Gharbi.
    claimed = Counter(row["mahalla_id"] for row in localities if row["mahalla_id"])
    for row in localities:
        if row["mahalla_id"] and claimed[row["mahalla_id"]] > 1:
            row["mahalla_id"] = row["mahalla_ar"] = ""
            row["match_rule"] = "two 1936 localities claim the same mahalla"


def write(path, rows):
    if not rows:
        print(f"{path.name:32s} no rows")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:32s} {len(rows):5d} rows")


def report(localities, seats):
    placed = [row for row in localities if row["shabiya_en"]]
    print(f"\n{len(placed)} of {len(localities)} localities carry a shabiya")
    print("  by shabiya:", dict(Counter(row["shabiya_en"]
                                        for row in placed).most_common(10)))
    print("  by kind:   ", dict(Counter(row["circoscrizione_kind"] or "(none)"
                                        for row in localities).most_common()))
    joined = [row for row in localities if row["mahalla_id"]]
    print(f"\n{len(joined)} localities join a 2006 mahalla on sound and shabiya")
    print("  why the rest do not:",
          dict(Counter(row["match_rule"] for row in localities
                       if not row["mahalla_id"]).most_common()))
    for row in joined[:12]:
        print(f"   {row['locality_it'][:26]:26s} {row['shabiya_en']:16s} "
              f"{row['mahalla_ar']}")
    print("\nnext: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
