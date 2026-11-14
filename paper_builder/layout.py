"""Shared export layout decisions for Word and PDF."""
import re

from reportlab.pdfbase.pdfmetrics import stringWidth

from .structured import MATH, body_style


def option_columns(options, preference, width):
    choices = {"four": (4, 2, 1), "two": (2, 1), "one": (1,)}
    style = body_style()
    for columns in choices[preference]:
        if columns == 1:
            return 1
        if all(not MATH.search(value) and "\n" not in value
               and stringWidth(re.sub(r"</?(?:sub|sup)>", "", f"({index}) {value}"),
                               style.fontName, style.fontSize) < width / columns - 16
               for index, value in enumerate(options, 1)):
            return columns


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
