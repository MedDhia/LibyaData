#!/usr/bin/env python3
"""
Rebuild table cells from word coordinates in the census PDFs.

The census volumes cannot be read from a PDF text stream. Thousands are
separated by a space and the separator is inconsistent ("10 759" and "10046"
both occur), a printed row can straddle two vertical bands because figures and
Arabic sit on different baselines, and figures are centred in their columns
rather than aligned to an edge. Cells are therefore reconstructed from geometry.

Everything here works in printed order: right to left, matching how the tables
read. Text is returned exactly as extracted; convert it with
`arabic_text.to_logical` at the point of use.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    text: str
    x0: float
    x1: float

    @property
    def centre(self):
        return (self.x0 + self.x1) / 2

    def spans(self, x):
        return self.x0 - 1 <= x <= self.x1 + 1


def _bands(words, gap):
    bands, current = [], [words[0]]
    for previous, word in zip(words, words[1:]):
        if word["top"] - previous["top"] > gap:
            bands.append(current)
            current = [word]
        else:
            current.append(word)
    bands.append(current)
    return bands


def _overlap(left, right, slack=1.0):
    """True if any word in one band shares horizontal space with the other."""
    for a in left:
        for b in right:
            if a["x0"] - slack < b["x1"] and b["x0"] - slack < a["x1"]:
                return True
    return False


def page_rows(page, cell_gap=8.0, fine_gap=2.0, merge_cap=7.0):
    """Group a page's words into rows of Cells, ordered right to left.

    Splitting lines by a fixed vertical gap does not work across these volumes.
    Figures and Arabic sit on different baselines, so one printed row can span
    three points; but the dense cross-tabulations stack sub-rows only about four
    points apart, and merging those concatenates their figures into impossible
    values, while a threshold small enough to separate them tears the wide
    tables apart.

    So the page is first split finely, then adjacent lines are merged only when
    they cannot be separate rows: a row split across baselines has its words in
    different columns, whereas two real rows occupy the same columns and
    therefore overlap horizontally.

    Within a row, a horizontal gap wider than `cell_gap` starts a new cell,
    which keeps the space used as a thousands separator inside its own cell.
    """
    words = sorted(page.extract_words(), key=lambda w: w["top"])
    if not words:
        return []

    bands = _bands(words, fine_gap)
    merged = True
    while merged:
        merged = False
        out = []
        index = 0
        while index < len(bands):
            band = bands[index]
            if index + 1 < len(bands):
                following = bands[index + 1]
                distance = min(w["top"] for w in following) - max(w["top"] for w in band)
                if distance <= merge_cap and not _overlap(band, following):
                    out.append(band + following)
                    index += 2
                    merged = True
                    continue
            out.append(band)
            index += 1
        bands = out

    rows = []
    for band in bands:
        ordered = sorted(band, key=lambda w: -w["x0"])
        groups, current = [], [ordered[0]]
        for previous, word in zip(ordered, ordered[1:]):
            # Reading right to left, the gap is the previous word's left edge
            # minus this word's right edge.
            if previous["x0"] - word["x1"] > cell_gap:
                groups.append(current)
                current = [word]
            else:
                current.append(word)
        groups.append(current)
        rows.append([Cell(" ".join(w["text"] for w in reversed(g)),
                          min(w["x0"] for w in g), max(w["x1"] for w in g))
                     for g in groups])
    return rows


def assign_by_centre(cells, centres, tolerance):
    """Map cells onto columns by matching centres.

    Returns {column index: cell}, with columns the source left blank simply
    absent, or None if two cells compete for one column.
    """
    out = {}
    for cell in cells:
        distance, index = min((abs(cell.centre - c), i)
                              for i, c in enumerate(centres))
        if distance > tolerance:
            return None
        if index in out:
            return None
        out[index] = cell
    return out
