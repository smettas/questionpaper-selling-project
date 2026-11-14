"""Typeset structured question text, vector math and diagram assets."""
import re
from base64 import b64decode
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from matplotlib import get_data_path, rc_context
from matplotlib.mathtext import math_to_image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, Table, Spacer
from svglib.svglib import svg2rlg

MATH = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\])", re.S)
SCRIPT = re.compile(r"(<(?:sub|sup)>[^<>]+</(?:sub|sup)>)")


@lru_cache(maxsize=256)
def equation_svg(expression):
    output = BytesIO()
    with rc_context({"svg.fonttype": "path"}):
        math_to_image(f"${expression}$", output, format="svg")
    return output.getvalue()


def validate_content(content):
    for value in (content["stem"], *content["options"], content["hint"]):
        if any("\n" in block for block in MATH.findall(value)):
            raise ValueError("Keep each math expression on one line.")
        remainder = MATH.sub("", value)
        if "\\" in remainder:
            raise ValueError("Use balanced math delimiters and supported math commands.")
        for block in MATH.findall(value):
            equation_svg(block[2:-2])


@lru_cache(maxsize=1)
def body_style():
    font = Path(get_data_path()) / "fonts" / "ttf" / "DejaVuSerif.ttf"
    pdfmetrics.registerFont(TTFont("PaperSerif", str(font)))
    return ParagraphStyle("StructuredBody", fontName="PaperSerif", fontSize=10, leading=15,
                          spaceAfter=4)


def text_blocks(text, width, prefix=""):
    blocks = []
    for line in text.splitlines():
        buffer = prefix
        prefix = ""
        parts = MATH.split(line)
        for index, part in enumerate(parts):
            if not part:
                continue
            if not MATH.fullmatch(part):
                buffer += "".join(chunk if re.fullmatch(r"<sub>[^<>]+</sub>|<sup>[^<>]+</sup>", chunk)
                                  else escape(chunk) for chunk in SCRIPT.split(part))
                continue
            if buffer.strip():
                blocks.append(Paragraph(buffer, body_style()))
                buffer = ""
            drawing = svg2rlg(BytesIO(equation_svg(part[2:-2])))
            suffix = re.match(r"^\s*((?:mol|grams?|g|kg|L|mL|u|molecules?|atoms?)\b[.,;:]?|[.,;:])", parts[index + 1])
            remainder = suffix[1] if suffix else ""
            if suffix:
                parts[index + 1] = parts[index + 1][suffix.end():].lstrip()
            trailing_width = 45 if remainder else 0
            scale = min(1.15, (width - trailing_width) / drawing.width)
            drawing.scale(scale, scale)
            drawing.width *= scale
            drawing.height *= scale
            drawing.hAlign = "LEFT"
            if remainder:
                blocks.append(Table([[drawing, Paragraph(escape(remainder), body_style())]],
                                    colWidths=[drawing.width + 4, trailing_width], hAlign="LEFT",
                                    style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            else:
                blocks.append(drawing)
        if buffer.strip():
            blocks.append(Paragraph(buffer, body_style()))
    return blocks


def question_blocks(content, width, *, answer_key=False, prefix="", option_layout="one"):
    from .layout import content_rows, option_columns

    placement = "hint" if answer_key else "question"
    blocks = []
    for part in content_rows(content["hint" if answer_key else "stem"]):
        if isinstance(part, str):
            blocks.extend(text_blocks(part, width, prefix))
        else:
            cell_width = width / len(part[0])
            blocks.append(Table([[text_blocks(cell, cell_width - 12) for cell in row] for row in part],
                                colWidths=[cell_width] * len(part[0]), repeatRows=1, hAlign="LEFT",
                                style=[("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#9aa8ba")),
                                       ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f8")),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            blocks.append(Spacer(1, 6))
        prefix = ""
    for diagram in content["diagrams"]:
        if diagram["placement"] != placement:
            continue
        picture = Image(BytesIO(b64decode(diagram["png"])))
        scale = min(1, width / picture.imageWidth, 240 / picture.imageHeight)
        picture.drawWidth = picture.imageWidth * scale
        picture.drawHeight = picture.imageHeight * scale
        picture.hAlign = "LEFT"
        blocks.append(picture)
    if not answer_key:
        options = content["options"]
        columns = option_columns(options, option_layout, width)
        cells = [text_blocks(option, width / columns - 12, f"({number}) ")
                 for number, option in enumerate(options, 1)]
        if columns == 1:
            for cell in cells:
                blocks.extend(cell)
        else:
            blocks.append(Table([cells[i:i + columns] for i in range(0, 4, columns)],
                                colWidths=[width / columns] * columns, hAlign="LEFT",
                                style=[("VALIGN", (0, 0), (-1, -1), "TOP"),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                       ("TOPPADDING", (0, 0), (-1, -1), 0),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return blocks
