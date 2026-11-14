"""Typeset structured question text, vector math and diagram assets."""
import re
from base64 import b64decode
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from matplotlib import get_data_path, rc_context
from matplotlib.mathtext import math_to_image
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph
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
        for part in MATH.split(line):
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
            scale = min(1.15, width / drawing.width)
            drawing.scale(scale, scale)
            drawing.width *= scale
            drawing.height *= scale
            drawing.hAlign = "LEFT"
            blocks.append(drawing)
        if buffer.strip():
            blocks.append(Paragraph(buffer, body_style()))
    return blocks


def question_blocks(content, width, *, answer_key=False, prefix=""):
    placement = "hint" if answer_key else "question"
    blocks = text_blocks(content["hint" if answer_key else "stem"], width, prefix)
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
        for number, option in enumerate(content["options"], 1):
            blocks.extend(text_blocks(option, width, f"({number}) "))
    return blocks
