"""Shared export layout decisions for Word and PDF."""
import re

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


def content_rows(value):
    """Group contiguous pipe-delimited lines with a common column count."""
    lines = value.splitlines()
    index = 0
    while index < len(lines):
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
