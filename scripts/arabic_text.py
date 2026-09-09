#!/usr/bin/env python3
"""
Convert Arabic text extracted from the 2006 census PDFs into logical order.

The census volumes are typeset in Arabic presentation forms (the U+FB50–U+FEFF
shaped-glyph blocks) laid out in visual order, so a naive text extraction
returns each line back to front with the letters in their contextual shapes.

The order of operations matters. A lam-alef ligature is a single glyph standing
for two letters, so it must be reversed *before* it is expanded: expanding first
and reversing afterwards silently swaps the two letters, turning الجلاء into
الجالء. Every place name containing lam-alef would be corrupted, and the result
still looks like plausible Arabic, so the error would not be visible on
inspection.

Numbers and Latin words are laid out left to right inside the right-to-left
line, so their runs are reversed back after the line is flipped.
"""

import re
import unicodedata

# Runs that were already left-to-right in the source and must be flipped back.
LTR_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,\-/()%&'\"]*[A-Za-z0-9]|[A-Za-z0-9]")

TATWEEL = "ـ"
DIACRITICS = re.compile(r"[ً-ْٰـ]")

# Arabic-Indic digits, which appear in a few volumes.
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def to_logical(text):
    """Return visually-ordered presentation-form Arabic as logical-order text."""
    if not text:
        return ""
    # Reverse first, so a ligature glyph lands in its logical position before
    # normalisation splits it into its constituent letters.
    text = text[::-1]
    text = unicodedata.normalize("NFKC", text)
    return LTR_RUN.sub(lambda m: m.group(0)[::-1], text)


def normalise_name(name):
    """Tidy an Arabic place name for use as a key: no tatweel, single spaces."""
    name = name.translate(ARABIC_DIGITS)
    name = DIACRITICS.sub("", name.replace(TATWEEL, ""))
    name = re.sub(r"[‏‎‪-‮]", "", name)
    name = name.replace("(", "(").replace(")", ")")
    return " ".join(name.split()).strip(" .:-")


def is_arabic(text):
    return any("؀" <= ch <= "ۿ" for ch in text)
