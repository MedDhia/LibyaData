#!/usr/bin/env python3
"""
Read the Official Gazette and pull out who was appointed to what.

Input is the House of Representatives' gazette, mirrored by
`scripts/download_gazette.py`: 50 issues, January 2023 to August 2026, 45 of
them with a usable text layer and 5 page scans that are skipped and counted.

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
from collections import Counter
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arabic_text import normalise_name, to_logical  # noqa: E402

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
HIJRI = re.compile(r"(\d{1,2})\s*/\s*([^/\d]{2,14}?)\s*/\s*(\d{4})\s*هـ")
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

ORDINALS = {"الأول": 1, "األول": 1, "الثاني": 2, "الثالث": 3, "الرابع": 4,
            "الخامس": 5, "اخلامس": 5, "السادس": 6, "السابع": 7, "الثامن": 8,
            "التاسع": 9, "العاشر": 10, "الحادي": 11, "الثاني عشر": 12,
            "الثالث عشر": 13, "الرابع عشر": 14, "الخامس عشر": 15,
            "السادس عشر": 16, "السابع عشر": 17, "الثامن عشر": 18,
            "الأولى": 1, "األوىل": 1, "الثانية": 2, "الثالثة": 3, "الرابعة": 4}


def fold(text):
    """Fold the spelling drift and the fonts' letter transpositions.

    The same fold `build_concordance.join_key` uses, minus the article strip:
    alef and ya variants, ta marbuta, spacing, and lam-alef written the wrong
    way round. It turns تعيني into تعيين and جملس into مجلس-adjacent forms.
    """
    text = normalise_name(str(text))
    text = re.sub(r"[إأآا]", "ا", text)
    text = re.sub(r"[ىي]", "ي", text)
    text = text.replace("ة", "ه")
    text = re.sub(r"\s+", "", text)
    return text.replace("لا", "ال")


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


def dates_in(block, issue_year=0):
    """The Gregorian and Hijri dates the decision is signed with.

    Only the tail of the block is read. A decision's preamble cites the laws it
    rests on, some of them from the 1960s, and the first Gregorian date in the
    block is as likely to be one of those as the signature.
    """
    gregorian = hijri = ""
    for line in block["lines"][-SIGNATURE_TAIL:]:
        if "املوافق" in line or "الموافق" in line or "بتاريخ" in line or "صدر" in line:
            stamp = GREGORIAN.search(line)
            if stamp and not gregorian and len(stamp.group(1)) == 4:
                year = int(stamp.group(1))
                if not issue_year or issue_year - 4 <= year <= issue_year + 1:
                    gregorian = (f"{stamp.group(1)}-{int(stamp.group(2)):02d}"
                                 f"-{int(stamp.group(3)):02d}")
            moon = HIJRI.search(line)
            if moon and not hijri:
                hijri = f"{moon.group(3)}-{moon.group(2).strip()}-{moon.group(1)}"
    return gregorian, hijri


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()

    manifest_path = RAW / "manifest.json"
    if not manifest_path.exists():
        sys.exit(f"missing {manifest_path}. Run scripts/download_gazette.py first.")
    manifest = json.loads(manifest_path.read_text())
    authority = manifest["publishing_authority"]

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
            gregorian, hijri = dates_in(block, published_year)
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
    print("next: python3 scripts/validate.py")


if __name__ == "__main__":
    main()
