"""Typeset structured question text, inline math and diagram assets."""
import re
from base64 import b64decode
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from matplotlib import get_data_path, rc_context
from matplotlib.figure import Figure
from matplotlib.mathtext import MathTextParser
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, Table, Spacer
from reportlab.platypus.paraparser import ParaParser
from PIL import Image as PILImage

MATH = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\])", re.S)
SCRIPT = re.compile(r"(<(?:sub|sup)>[^<>]+</(?:sub|sup)>)")
MATH_PATH_PARSER = MathTextParser("path")
NUMERIC_SQUARE_ROOT = re.compile(r"√\(([0-9.]+)²\s*([+−-])\s*([0-9.]+)²\)")


def normalize_math(value):
    """Typeset known plain-text formulas from existing chapter banks."""
    def typeset_root(match):
        left, operator, right = match.groups()
        return rf"\(\sqrt{{{left}^2 {operator.replace('−', '-')} {right}^2}}\)"

    return "".join(
        part if MATH.fullmatch(part) else NUMERIC_SQUARE_ROOT.sub(
            typeset_root,
            part.replace("√(K<sub>b</sub>/C)", r"\(\sqrt{\frac{K_b}{C}}\)")
                .replace("√(n(n+2))", r"\(\sqrt{n(n+2)}\)"),
        )
        for part in MATH.split(value)
    )
QUESTION_LABEL = re.compile(
    r"^\s*(?:(?:Assertion|Reason)(?:\s*\([AR]\))?\s*[:–—-]"
    r"|Statement\s*[-–—]?\s*(?:[IVX]+|\d+|[A-Z])\s*[:.)–—-]"
    r"|(?:List|Match)\s*[-–—]?\s*(?:[IVX]+|\d+)(?=\W|$)\s*:?)",
    re.IGNORECASE,
)


def split_question_label(value):
    match = QUESTION_LABEL.match(value)
    return (match[0].rstrip(), value[len(match[0].rstrip()):]) if match else ("", value)


def render_equation(expression, format, dpi=None):
    output = BytesIO()
    with rc_context({"svg.fonttype": "path", "savefig.transparent": True,
                     "mathtext.fontset": "dejavuserif"}):
        math = f"${expression}$"
        width, height, depth, _, _ = MATH_PATH_PARSER.parse(math, dpi=72)
        # MathText's nominal box can end before the ink of a radical bar.
        padding = 1
        canvas_width = width + 2 * padding
        canvas_height = height + 2 * padding
        figure = Figure(figsize=(canvas_width / 72, canvas_height / 72))
        figure.text(padding / canvas_width, (depth + padding) / canvas_height, math)
        figure.savefig(output, format=format, dpi=dpi)
    return output.getvalue()


@lru_cache(maxsize=256)
def equation_svg(expression):
    return render_equation(expression, "svg")


@lru_cache(maxsize=256)
def equation_png(expression):
    dpi = 288
    payload = render_equation(expression, "png", dpi=dpi)
    with PILImage.open(BytesIO(payload)) as image:
        width, height = image.size
    return payload, width * 72 / dpi, height * 72 / dpi


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
    pdfmetrics.registerFont(TTFont("PaperSerif-Bold", str(font.with_name("DejaVuSerif-Bold.ttf"))))
    pdfmetrics.registerFontFamily("PaperSerif", normal="PaperSerif", bold="PaperSerif-Bold")
    return ParagraphStyle("StructuredBody", fontName="PaperSerif", fontSize=10, leading=15,
                          spaceAfter=4, autoLeading="max")


class EquationParagraphParser(ParaParser):
    """Resolve equation images directly from memory during paragraph parsing."""

    def __init__(self, images):
        super().__init__()
        self.images = images

    def start_img(self, attributes):
        super().start_img(attributes)
        fragment = self._stack[-1]
        fragment.src = BytesIO(self.images[int(fragment.src)])


def text_blocks(text, width, prefix="", *, bold_labels=False):
    blocks = []
    for line in normalize_math(text).splitlines():
        buffer = prefix
        images = []
        prefix = ""
        if bold_labels:
            label, line = split_question_label(line)
            if label:
                buffer += f"<b>{escape(label)}</b>"
        for part in MATH.split(line):
            if MATH.fullmatch(part):
                image, natural_width, height = equation_png(part[2:-2])
                scale = min(1, width / natural_width)
                buffer += (f'<img src="{len(images)}" width="{natural_width * scale:.2f}" '
                           f'height="{height * scale:.2f}" valign="middle"/>')
                images.append(image)
            else:
                buffer += "".join(
                    chunk if SCRIPT.fullmatch(chunk) else escape(chunk)
                    for chunk in SCRIPT.split(part)
                )
        if buffer.strip():
            style = body_style()
            if images:
                _, fragments, _ = EquationParagraphParser(images).parse(buffer, style)
                blocks.append(Paragraph(buffer, style, frags=fragments))
            else:
                blocks.append(Paragraph(buffer, style))
    return blocks


def question_blocks(content, width, *, answer_key=False, prefix="", option_layout="one"):
    from .layout import content_rows, option_columns

    placement = "hint" if answer_key else "question"
    blocks = []
    for part in content_rows(content["hint" if answer_key else "stem"]):
        if isinstance(part, str):
            blocks.extend(text_blocks(part, width, prefix, bold_labels=not answer_key))
        else:
            cell_width = width / len(part[0])
            blocks.append(Table([[text_blocks(cell, cell_width - 12, bold_labels=not answer_key)
                                  for cell in row] for row in part],
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
