"""Shared export layout decisions for Word and PDF."""
import re
from itertools import zip_longest

from reportlab.pdfbase.pdfmetrics import stringWidth

from .structured import MATH, SCRIPT, body_style, equation_png, normalize_math


def option_columns(options, preference, width):
    choices = {"four": (4, 2, 1), "two": (2, 1), "one": (1,)}
    style = body_style()
    if preference == "one" or any("\n" in option for option in options):
        return 1
    widths = []
    for index, option in enumerate(options, 1):
        measured = stringWidth(f"({index}) ", style.fontName, style.fontSize)
        for part in MATH.split(normalize_math(option)):
            if MATH.fullmatch(part):
                measured += equation_png(part[2:-2])[1]
            else:
                measured += stringWidth(SCRIPT.sub(lambda m: re.sub(r"</?[^>]+>", "", m[0]), part),
                                        style.fontName, style.fontSize)
        widths.append(measured)
    return next(columns for columns in choices[preference]
                if columns == 1 or max(widths) <= width / columns - 16)


LIST_ONE = re.compile(r"List\s*[-–—]?\s*(?:I|1)\s*[:.]?", re.IGNORECASE)
LIST_TWO = re.compile(r"List\s*[-–—]?\s*(?:II|2)\s*[:.]?", re.IGNORECASE)
LIST_ITEM = re.compile(r"\s*([A-Z]+)[.):]\s+\S")
ROMAN_LABELS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")


def stacked_matching_table(lines, start):
    if not LIST_ONE.fullmatch(lines[start].strip()):
        return None
    end = start + 1
    columns = []
    for labels in ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", ROMAN_LABELS):
        items = []
        for label in labels:
            while end < len(lines) and not lines[end].strip():
                end += 1
            if end == len(lines):
                break
            match = LIST_ITEM.match(lines[end])
            if not match or match[1] != label:
                break
            items.append(lines[end].strip())
            end += 1
        columns.append(items)
        if len(columns) == 1:
            if end == len(lines) or not LIST_TWO.fullmatch(lines[end].strip()):
                return None
            end += 1
    if min(map(len, columns)) < 2:
        return None
    return [["List I", "List II"], *zip_longest(*columns, fillvalue="")], end


def content_rows(value):
    """Group pipe-delimited rows and legacy matching lists into tables."""
    lines = value.splitlines()
    index = 0
    while index < len(lines):
        matching = stacked_matching_table(lines, index)
        if matching:
            rows, index = matching
            yield rows
            continue
        cells = [cell.strip() for cell in lines[index].split("|")]
        end = index + 1
        if len(cells) > 1 and all(cells):
            while end < len(lines):
                next_cells = [cell.strip() for cell in lines[end].split("|")]
                if len(next_cells) != len(cells) or not all(next_cells):
                    break
                end += 1
        if end > index + 1:
            yield [[cell.strip() for cell in row.split("|")] for row in lines[index:end]]
        elif lines[index].strip():
            yield lines[index]
        index = end
