#!/usr/bin/env python3
"""
Read the Official Gazette and pull out who was appointed to what.

Input is the House of Representatives' gazette, mirrored by
`scripts/download_gazette.py`: 50 issues, February 2023 to August 2026, 46 of
them with a usable text layer and 4 page scans that are skipped and counted.

## The publishing authority is a variable

This is the House of Representatives' own gazette, begun in January 2023. It
records decisions of the House, its Presidency Board and its Speaker, plus
Supreme Constitutional Court judgments, Council of Ministers decisions of the
House-appointed government, and public notices. It does **not** record the
Tripoli government's appointments. Every row therefore carries
`publishing_authority`, and an analysis that treats this as a national record of
Libyan appointments will be measuring one side of a split state.

## Reading order

Each page's text layer comes out bottom line first, so lines are reversed per
page before anything else. Get that wrong and every decision appears to end
before it begins.

## Finding a decision

A decision opens on a title line, `قرار <authority> رقم (73) لسنة 2024م`, and is
followed by a subject line beginning `بشأن` or `في شأن`. Either can be missing:
some issues print the title as an image and only the subject survives, so a
subject with no open title opens a decision of its own with the number left
empty. The block runs to the next title, and inside it the parser takes the
citation preamble, the articles, the signature and the two dates the gazette
prints, Hijri and Gregorian.

## Appointments

An appointment is a decision whose subject carries one of nine acts: تعيين,
تكليف, تسمية, ندب, ترقية, إعفاء, إنهاء, تجديد or تشكيل. The embedded fonts
transpose letters, printing تعيني for تعيين and جملس for مجلس, so matching is on
a folded key rather than the literal string, the same fold the concordance uses.

Named people are taken from the honorific: `السيد /` and `السيدة /`, alone or in
a numbered list. A name is written to `person_name` only when the span after the
honorific ends cleanly at a role word or a bracket; the whole line is kept in
`person_line` either way, so every extracted name can be checked against what
the page says, and a decision that names nobody still produces a row.

Two repairs happen first. The fonts split single letters off their word, writing
منصو ر for منصور, so a lone letter is rejoined to its neighbour; two-letter
fragments are left alone because بن and أبو are real, which means a few names
keep an internal split, and `person_key` exists for that: the name folded and
stripped of spaces, so إسماع يل and إسماعيل join to each other. Academic and
military titles are stripped, so د سلطنة مسعود and سلطنة مسعود are one person. A
span carrying an unmapped glyph is discarded rather than half-read.

## Geography

Two geographies, and conflating them would be an error. Where a decision was
signed is not where its office has authority.

`issued_at` is the city in the signature block, "صدر في مدينة بنغازي". It is
resolved against the concordance and written to `issued_at_shabiya_*`, with
`issued_at_matched_level` recording the layer that answered. The whole block is
read for the signature rather than its tail: a decision that runs into a budget
annex carries its signature in the middle and a page footer at the end, which
cost 10 of the 68, one of them the only other Tripoli signature in the series.

`issued_at_status` says why a decision carries no place, because an empty column
is not one thing. The gazette prints its own table of contents as decision
titles and those entries have no body to sign, which is 8 of them; 33 have a
body that goes unsigned in print.

## Dates

The signature prints both calendars on adjacent lines, "بتاريخ: 23/رجب/1447ه"
then "املوافق: 12/يناير/2026م", so the month is a word and not a number. Reading
only numeric dates left 21 of 109 decisions dated and none with a Hijri date at
all. Month names are matched on their anagram, because the fonts that print طبرق
as طربق print فبراير as فرباير, and the 16 spellings of the 12 months collide
only where two spellings are the same month.

Both calendars are collected with the line they sit on and the closest pair
wins, which keeps a decision's own date from being paired with one cited
elsewhere in the same window. `signed_hijri` is `YYYY-MM-DD` in the Hijri
calendar, not a month name.

56 of the 60 decisions carrying both dates agree to within three days, which is
the tolerance between the tabular Islamic calendar and the Umm al-Qura one the
gazette follows. The four that do not are printed that way: 4 Ramadan 1444 is 26
March 2023, and the gazette prints it against 2 March.

`office_shabiya_*` is the territory the office covers, read from the subject.
Almost nothing lands there, and that is the finding rather than a failure: these
are national offices. Of the 109 decisions, the subjects name no Libyan place at
all. A place is accepted only when it is one of the 22 shabiyat, or when a
place-signalling word (بلدية, مدينة, منطقة, محلة, شعبية) stands immediately
before it. Without that rule المحكمة العليا matches العليا, a mahalla in Jabal
al Gharbi, and six national court decisions acquire a false province.

`office_scope` codes what kind of office it is: `bilateral` for the
parliamentary friendship committees, which are territorial only in naming
another country; `subnational` where a Libyan place resolves; `national`
otherwise.

Outputs, all under data/processed/gazette/:
  gazette_issues.csv        one row per issue
  gazette_decisions.csv     one row per decision, appointments flagged
  gazette_appointments.csv  one row per appointment and named person
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import normalise_name, to_logical  # noqa: E402
from libya_places import (PLACE_MARKERS, anagram, fold, gazetteer,  # noqa: E402
                          locate)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "gazette"
OUT = ROOT / "data" / "processed" / "gazette"

# "قرار رئيس مجلس النواب رقم (73) لسنة 2024م", and the same with the definite
# article, "القانون رقم ( 29) لسنة 2023م", brackets sometimes padded.
TITLE = re.compile(r"^(?:ال)?(قانون|قرار|أمر)\s*(.{0,60}?)\s*رقم\s*\(?\s*(\d{1,4})\s*\)?"
                   r"\s*لسنة\s*(\d{4})")
# A decision's articles start here. Past this point a line opening with بشأن is
# part of the text, not a new decision's subject.
BODY_START = re.compile(r"^(?:صدر\s+(?:القرار|القانون|الأمر)|صدر القانون|المادة|املادة|"
                        r"مادة\s*\()")
SUBJECT_MAX = 140
# Lines from the end of a block in which the signature and its dates sit.
SIGNATURE_TAIL = 14
SUBJECT = re.compile(r"^(?:بشأن|في شأن|فى شأن|يف شأن)\s+(.{3,200})")
GREGORIAN = re.compile(r"(\d{4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})")
# The signature block writes the month as a word, not a number:
# "بتاريخ: 23/رجب/1447ه. املوافق: 12/يناير/2026م". Both calendars use the same
# shape, so one pattern reads both and the month name says which is which.
NAMED_DATE = re.compile(r"(\d{1,2})\s*/\s*([^/\d]{2,20}?)\s*/\s*(\d{4})")
GREGORIAN_MONTHS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
                    "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")
# Spelling variants that are the same month, kept so the anagram index holds both.
GREGORIAN_ALSO = {"إبريل": 4, "يونية": 6, "يولية": 7, "اغسطس": 8}
HIJRI_MONTHS = ("محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى",
                "جمادى الآخرة", "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة",
                "ذو الحجة")
HIJRI_ALSO = {"ربيع الثاني": 4, "جمادى الثانية": 6, "ذي القعدة": 11, "ذي الحجة": 12}


DATE_MARKERS = ("املوافق", "الموافق", "بتاريخ", "صدر")


def month_index(names, extra):
    """Month name to number, keyed on the anagram.

    The same fonts that print طبرق as طربق print فبراير as فرباير, so the month
    is matched on its letters sorted rather than in order. The 16 spellings of
    the 12 months collide only where two spellings are the same month.
    """
    index = {anagram(name): number for number, name in enumerate(names, 1)}
    index.update({anagram(name): number for name, number in extra.items()})
    return index
HONORIFIC = re.compile(r"الس(?:يد|يدة|ادة)\s*/\s*(.{3,70})")
ISSUE_HEAD = re.compile(r"العدد\s+(\S+(?:\s+عشر)?)\s+.{0,3}السنة\s+(\S+)")

# The acts that make a decision an appointment, keyed on the folded form so the
# fonts' letter transpositions do not matter.
ACTS = {
    "تعيين": "appointment", "تكليف": "assignment", "تسمية": "naming",
    "ندب": "secondment", "ترقية": "promotion", "اعفاء": "removal",
    "انهاء": "termination", "تجديد": "renewal", "تشكيل": "committee_formation",
}
# Words at which a personal name ends and a role begins.
ROLE_WORDS = ("رئيس", "رئيسا", "عضو", "عضوا", "وكيل", "مستشار", "نائب", "محافظ",
              "مدير", "امين", "وزير", "عميد", "قائد", "سفير", "مندوب", "المحامي")

# "صدر في مدينة بنغازي" at the foot of a decision.
ISSUED_AT = re.compile(r"^صدر\s+(?:يف|في|فى)\s+(?:ب?مدينة\s+)?(.{2,30}?)\s*[.،:]?\s*$")
# Foreign adjectives in the parliamentary friendship committees.
BILATERAL = ("المغربية", "اإليطالية", "الإيطالية", "الربيطانية", "البريطانية",
             "الرتكية", "التركية", "املرصية", "المصرية", "الفرنسية", "األملانية",
             "الألمانية", "الروسية", "الصينية", "التونسية", "اجلزائرية",
             "الجزائرية", "اإلسبانية", "الإسبانية", "اإلماراتية", "الإماراتية")

ORDINALS = {"الأول": 1, "األول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4,
            "الخامس": 5, "اخلامس": 5, "السادس": 6, "السابع": 7, "الثامن": 8,
            "التاسع": 9, "العاشر": 10, "الحادي": 11, "الثاني عشر": 12,
            "الثالث عشر": 13, "الرابع عشر": 14, "الخامس عشر": 15,
            "السادس عشر": 16, "السابع عشر": 17, "الثامن عشر": 18,
            "الأولى": 1, "األوىل": 1, "الثانية": 2, "الثالثة": 3, "الرابعة": 4}


def act_of(subject):
    """Which appointment act a subject line performs, if any."""
    folded = fold(subject)
    for word, label in ACTS.items():
        if fold(word) in folded:
            return word, label
    return "", ""


def lines_of(path):
    """(page number, line) in reading order. Pages come out bottom line first."""
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = to_logical(page.extract_text() or "")
            if not text.strip():
                continue
            for line in reversed(text.split("\n")):
                line = re.sub(r"ـ+", "", line).strip()
                if line:
                    out.append((page.page_number, line))
    return out


def issue_header(lines):
    """Issue number, year of publication and the printed Gregorian date."""
    number = year = ""
    date = ""
    for _, line in lines[:40]:
        found = ISSUE_HEAD.search(line)
        if found and not number:
            number = str(ORDINALS.get(found.group(1).strip(), ""))
            year = str(ORDINALS.get(found.group(2).strip(), ""))
        if not date:
            stamp = GREGORIAN.search(line)
            if stamp and len(stamp.group(1)) == 4:
                date = f"{stamp.group(1)}-{int(stamp.group(2)):02d}-{int(stamp.group(3)):02d}"
    return number, year, date


# Honorifics and academic titles that precede a name rather than being part of
# it. Stripped so that "د سلطنة مسعود" and "سلطنة مسعود" are one person.
TITLES = ("د", "د.", "أ", "أ.", "أ.د", "م", "الدكتور", "الدكتورة", "الأستاذ",
          "األستاذ", "المهندس", "املهندس", "اللواء", "العميد", "المستشار",
          "املستشار")
# A name is rejected outright when it carries a glyph the font failed to map.
BROKEN = re.compile(r"\(cid|\d")


def repair_spacing(text):
    """Rejoin letters the PDF's kerning split off from their word.

    The gazette's fonts emit "منصو ر" for منصور and "محمد ا لحاج" for محمد
    الحاج: a single letter separated from the word it belongs to. No Arabic name
    particle is one letter, so a lone letter is always a fragment. An alef joins
    forward, because it starts the definite article; anything else joins back to
    the word it was cut from. Two-letter fragments are left alone, because بن
    and أبو are real.
    """
    words, out, carry = text.split(), [], ""
    for word in words:
        if carry:
            word, carry = carry + word, ""
        if len(word) == 1:
            if word in "اأإ":
                carry = word
            elif out:
                out[-1] += word
            else:
                carry = word
            continue
        out.append(word)
    if carry:
        out.append(carry)
    return " ".join(out)


def person_from(line):
    """A personal name from an honorific, or '' when the span does not close."""
    found = HONORIFIC.search(line)
    if not found:
        return ""
    span = found.group(1).strip(" .:،,-")
    if BROKEN.search(span):
        return ""
    # Titles come off before the spacing repair, or a lone "د" would be glued to
    # the first name.
    words = span.split()
    while words and words[0].strip(".") in TITLES:
        words = words[1:]
    words = [w.strip("()،,.:/\"") for w in repair_spacing(" ".join(words)).split()]
    words = [w for w in words if w]

    # The fonts split role words too, printing "عض وا" for عضوا and "رئي سا" for
    # رئيسا, so the cut is looked for in the space-free concatenation and mapped
    # back to a token boundary. Cutting on whole tokens alone leaves the role
    # stuck to the name.
    joined, offsets, position = "", [], 0
    for word in words:
        offsets.append(position)
        joined += word
        position += len(word)
    folded = fold(joined)
    cut = len(words)
    earliest = len(joined) + 1
    for role in ROLE_WORDS:
        at = folded.find(fold(role))
        if 0 <= at < earliest:
            earliest = at
    if earliest <= len(joined):
        for index, start in enumerate(offsets):
            if start >= earliest:
                cut = index
                break
        else:
            cut = len(words)
        # A role word starting inside the first token means no name at all.
        if earliest < offsets[min(1, len(offsets) - 1)]:
            return ""
    name = words[:cut][:5]
    if len(name) < 2:
        return ""
    return normalise_name(" ".join(name))


def split_decisions(lines):
    """Group the lines of one issue into decision blocks.

    A subject line is only a subject before the articles begin. Libyan statutory
    prose is full of `بشأن` inside an article, citing another law, and taking
    those for new decisions is what turns one law into five.
    """
    blocks, current, in_body = [], None, False
    for page, line in lines:
        title = TITLE.match(line)
        if title:
            if current:
                blocks.append(current)
            current = {"page": page, "kind": title.group(1),
                       "authority": title.group(2).strip(" .:،,-"),
                       "number": title.group(3), "year": title.group(4),
                       "subject": "", "lines": []}
            in_body = False
            continue
        if BODY_START.match(line):
            in_body = True
        subject = SUBJECT.match(line) if not in_body else None
        if subject and len(line) <= SUBJECT_MAX:
            if current is None or current["subject"]:
                if current:
                    blocks.append(current)
                current = {"page": page, "kind": "", "authority": "",
                           "number": "", "year": "", "subject": "", "lines": []}
            current["subject"] = subject.group(1).strip(" .:،,-")
            continue
        if current is not None:
            current["lines"].append(line)
    if current:
        blocks.append(current)
    return [b for b in blocks if b["subject"] or b["number"]]


GREGORIAN_INDEX = month_index(GREGORIAN_MONTHS, GREGORIAN_ALSO)
HIJRI_INDEX = month_index(HIJRI_MONTHS, HIJRI_ALSO)


def signature_status(block, city, where):
    """Why a decision carries no signature place, where it carries none.

    An empty column is not one thing. The gazette prints its own table of
    contents as decision titles, and those entries have no body to sign; a
    decision whose body is here may still go unsigned in print; and a signature
    that is printed can still name a place the gazetteer does not hold.
    """
    if where:
        return "signed"
    if city:
        return "place not in the gazetteer"
    if len([line for line in block["lines"] if line.strip()]) < 3:
        return "no body text: a table-of-contents entry"
    return "no signature line printed"


def signature(block):
    """Where the decision was signed: the line index and the city it names.

    The whole block is read, not its tail. A decision that runs into a budget
    annex or a salary table carries its signature in the middle and a page
    footer at the end: reading the last 14 lines alone loses 12 of them, one of
    them the only Tripoli signature in the series.

    The **first** match is taken, not the last, because the other failure is a
    block that swallowed the decision printed after it, and that decision's
    signature is not this one's. On the 73 blocks where the old tail rule fired,
    the first match in the whole block is the same line, so nothing that was
    already read changes.
    """
    for index, line in enumerate(block["lines"]):
        found = ISSUED_AT.match(line)
        if found:
            return index, normalise_name(found.group(1))
    return None, ""


def dates_in(block, issue_year=0, signed_at=None):
    """The Gregorian and Hijri dates the decision is signed with.

    Never the whole block: a decision's preamble cites the laws it rests on,
    some of them from the 1960s, and the first Gregorian date in the block is as
    likely to be one of those as the signature. Where the signature line has
    been found, the window around it is read, because that is where the date is
    printed; otherwise the tail, which is where it is when the block ends
    cleanly. The window is tried first and the tail second, so this can only
    find a date the tail rule would have missed, never lose one.
    """
    window = []
    if signed_at is not None:
        window = block["lines"][max(0, signed_at - 3):signed_at + 8]
    for lines in (window, block["lines"][-SIGNATURE_TAIL:]):
        gregorian, hijri = scan_dates(lines, issue_year)
        if gregorian or hijri:
            return gregorian, hijri
    return "", ""


def scan_dates(lines, issue_year):
    """The Gregorian and Hijri dates a decision is signed with.

    The signature prints them on two adjacent lines, "بتاريخ" then "املوافق",
    so both are collected with the line they sit on and the closest pair wins.
    Taking the first of each independently pairs a decision's own date with a
    date cited elsewhere in the same window, which put four of them a lunar
    month apart from each other.
    """
    gregorians, hijris = [], []
    for index, line in enumerate(lines):
        if not any(mark in line for mark in DATE_MARKERS):
            continue
        stamp = GREGORIAN.search(line)
        if stamp and len(stamp.group(1)) == 4 and in_window(stamp.group(1),
                                                            issue_year):
            gregorians.append((index, f"{stamp.group(1)}-{int(stamp.group(2)):02d}"
                                      f"-{int(stamp.group(3)):02d}"))
        for day, name, year in NAMED_DATE.findall(line):
            code = anagram(name)
            month = GREGORIAN_INDEX.get(code)
            if month:
                if in_window(year, issue_year):
                    gregorians.append((index, f"{year}-{month:02d}-{int(day):02d}"))
                continue
            month = HIJRI_INDEX.get(code)
            # The Hijri year runs about 579 behind the Gregorian one in this
            # period, so the same window applies once it is converted.
            if month and in_window(int(year) + 579, issue_year):
                hijris.append((index, f"{year}-{month:02d}-{int(day):02d}"))
    if gregorians and hijris:
        near = min(((abs(i - j), g, h) for i, g in gregorians for j, h in hijris),
                   key=lambda pair: pair[0])
        return near[1], near[2]
    return (gregorians[0][1] if gregorians else "",
            hijris[0][1] if hijris else "")


def in_window(year, issue_year):
    """Is this year close enough to the issue's to be the signature's own?

    A decision's preamble cites the laws it rests on, some of them from the
    1960s. The window runs four years back, because the series reprints older
    decisions, and one year forward for an issue published late.
    """
    return not issue_year or issue_year - 4 <= int(year) <= issue_year + 1


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    manifest_path = RAW / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"missing {manifest_path}. Run scripts/download_gazette.py first.")
    manifest = json.loads(manifest_path.read_text())
    authority = manifest["publishing_authority"]

    places, shabiya_keys, scrambled = gazetteer()
    print(f"gazetteer: {len(places)} Arabic keys, article variants included, "
          f"{len(shabiya_keys)} of them naming a shabiya")

    issues, decisions, appointments = [], [], []
    seen, scans = {}, 0
    for entry in manifest["issues"]:
        path = RAW / entry["file"]
        if not path.exists():
            continue
        try:
            lines = lines_of(path)
        except Exception as exc:                              # noqa: BLE001
            print(f"  {entry['file']}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        # A page scan yields a cover page and nothing else.
        if len(lines) < 30:
            scans += 1
            issues.append({
                "issue_id": entry["id"], "title": entry["title"],
                "issue_number": "", "issue_year": "", "issue_date": "",
                "published": entry["date"][:10], "pages_with_text": 0,
                "decisions": 0, "appointments": 0, "read_by": "scan_no_text_layer",
                "publishing_authority": authority, "source_sha256": entry["sha256"],
            })
            continue

        number, year, date = issue_header(lines)
        blocks = split_decisions(lines)
        found = 0
        for block in blocks:
            act, act_en = act_of(block["subject"])
            published_year = int((date or entry["date"][:10])[:4])
            signed_at, city = signature(block)
            gregorian, hijri = dates_in(block, published_year, signed_at)
            where, city_token = locate(city, places, shabiya_keys, scrambled,
                                       require_marker=False)
            office, office_token = locate(block["subject"], places, shabiya_keys,
                                          scrambled)
            # Foreign adjectives are matched on the anagram too, because the
            # fonts scramble المغربية into املغربية.
            subject_words = {anagram(w) for w in block["subject"].split()}
            scope = ("bilateral"
                     if subject_words & {anagram(w) for w in BILATERAL}
                     else "subnational" if office else "national")
            record = {
                "issue_id": entry["id"], "issue_number": number, "issue_year": year,
                "issue_date": date or entry["date"][:10],
                "page": block["page"],
                "decision_kind": block["kind"],
                "issuing_body": block["authority"],
                "decision_number": block["number"],
                "decision_year": block["year"],
                "subject": block["subject"],
                "act_ar": act, "act_en": act_en,
                "is_appointment": int(bool(act)),
                "signed_gregorian": gregorian, "signed_hijri": hijri,
                "issued_at": city,
                "issued_at_shabiya_ar": where[0] if where else "",
                "issued_at_shabiya_en": where[1] if where else "",
                "issued_at_shabiya_pcode": where[2] if where else "",
                "issued_at_matched_level": where[3] if where else "",
                "issued_at_status": signature_status(block, city, where),
                "office_scope": scope,
                "office_shabiya_ar": office[0] if office else "",
                "office_shabiya_en": office[1] if office else "",
                "office_shabiya_pcode": office[2] if office else "",
                "office_place_matched_on": office_token,
                "publishing_authority": authority,
                "source_document": entry["title"],
                "source_sha256": entry["sha256"],
            }
            key = (record["decision_kind"], record["decision_number"],
                   record["decision_year"], fold(record["subject"])[:60])
            if key in seen:
                # The gazette reprints: the same law or decision appears in more
                # than one issue, sometimes as a corrected re-upload. Keep the
                # first printing and count the rest rather than double-counting.
                seen[key]["printed_in_issues"] += 1
                continue
            record["printed_in_issues"] = 1
            seen[key] = record
            decisions.append(record)
            if not act:
                continue
            found += 1
            named = [(line, person_from(line)) for line in block["lines"]
                     if HONORIFIC.search(line)]
            named = [(line, name) for line, name in named if name] or [("", "")]
            for line, name in named:
                appointments.append({**record, "person_name": name,
                                     "person_key": fold(name),
                                     "person_line": line[:200]})

        issues.append({
            "issue_id": entry["id"], "title": entry["title"],
            "issue_number": number, "issue_year": year,
            "issue_date": date or entry["date"][:10],
            "published": entry["date"][:10],
            "pages_with_text": len({p for p, _ in lines}),
            "decisions": len(blocks), "appointments": found,
            "read_by": "text", "publishing_authority": authority,
            "source_sha256": entry["sha256"],
        })

    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / "gazette_issues.csv", issues)
    write(OUT / "gazette_decisions.csv", decisions)
    write(OUT / "gazette_appointments.csv", appointments)
    report(issues, decisions, appointments, scans)


def write(path, rows):
    if not rows:
        print(f"{path.name:30s} no rows")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path.name:30s} {len(rows):5d} rows")


def report(issues, decisions, appointments, scans):
    read = [i for i in issues if i["read_by"] == "text"]
    print(f"\n{len(read)} issues read, {scans} page scans with no text layer")
    if read:
        print(f"  {read[0]['issue_date']} to {read[-1]['issue_date']}")
    print("decision kinds: ",
          dict(Counter(d["decision_kind"] or "(title not printed)"
                       for d in decisions).most_common(6)))
    print("appointment acts:",
          dict(Counter(d["act_en"] for d in decisions if d["act_en"]).most_common(10)))
    named = sum(1 for a in appointments if a["person_name"])
    print(f"appointments: {sum(d['is_appointment'] for d in decisions)} decisions, "
          f"{len(appointments)} rows, {named} carrying a personal name")
    reprinted = sum(1 for d in decisions if d["printed_in_issues"] > 1)
    print(f"{reprinted} decisions printed in more than one issue, kept once")
    bodies = Counter(d["issuing_body"] for d in decisions if d["issuing_body"])
    print("issuing bodies: ", dict(bodies.most_common(6)))
    print("issued at:      ",
          dict(Counter(d["issued_at"] for d in decisions if d["issued_at"])
               .most_common(6)))
    placed = sum(1 for d in decisions if d["issued_at_shabiya_en"])
    print(f"{placed} of {len(decisions)} decisions place their signature in a shabiya",
          dict(Counter(d["issued_at_shabiya_en"] for d in decisions
                       if d["issued_at_shabiya_en"])))
    print("  matched on:   ",
          dict(Counter(d["issued_at_matched_level"] for d in decisions
                       if d["issued_at_matched_level"])))
    print("  unsigned, by why:",
          dict(Counter(d["issued_at_status"] for d in decisions
                       if d["issued_at_status"] != "signed").most_common()))
    dated = sum(1 for d in decisions if d["signed_gregorian"])
    print(f"{dated} of {len(decisions)} decisions carry a signature date")
    print("office scope:   ", dict(Counter(d["office_scope"] for d in decisions)))
    territorial = [d for d in decisions if d["office_shabiya_en"]]
    print(f"{len(territorial)} decisions name a Libyan place in the office itself",
          dict(Counter(d["office_shabiya_en"] for d in territorial)))
    print("next: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
