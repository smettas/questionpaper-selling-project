"""Editable Word export for structured bank questions."""
import re
from base64 import b64decode
from io import BytesIO
from xml.etree import ElementTree as ET

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from latex2mathml.converter import convert
from PIL import Image

from .layout import content_rows, option_columns
from .structured import MATH, SCRIPT


def append_math(paragraph, expression):
    def node(name, children=()):
        element = OxmlElement(f"m:{name}")
        element.extend(children)
        return element

    def translate(element):
        tag = element.tag.split("}")[-1]
        children = [item for child in element for item in translate(child)]
        if tag in ("mi", "mn", "mo", "mtext"):
            token = node("t")
            token.text = element.text or ""
            token.set(qn("xml:space"), "preserve")
            return [node("r", [token])]
        if tag in ("math", "mrow", "mstyle"):
            return children
        if tag == "mspace":
            token = node("t")
            token.text = " "
            token.set(qn("xml:space"), "preserve")
            return [node("r", [token])]
        structures = {"mfrac": ("f", ("num", "den")), "msup": ("sSup", ("e", "sup")),
                      "msub": ("sSub", ("e", "sub")), "msubsup": ("sSubSup", ("e", "sub", "sup"))}
        if tag in structures:
            name, slots = structures[tag]
            return [node(name, [node(slot, translate(child)) for slot, child in zip(slots, element)])]
        if tag in ("msqrt", "mroot"):
            rad = node("rad")
            if tag == "msqrt":
                hidden = node("degHide")
                hidden.set(qn("m:val"), "1")
                rad.append(node("radPr", [hidden]))
            rad.extend([node("deg", translate(element[1]) if tag == "mroot" else []),
                        node("e", translate(element[0]) if tag == "mroot" else children)])
            return [rad]
        raise ValueError(f"Word export does not support equation element {tag}.")

    paragraph._p.append(node("oMath", translate(ET.fromstring(convert(expression)))))


def write_text(paragraph, value):
    for part in MATH.split(value):
        if MATH.fullmatch(part):
            append_math(paragraph, part[2:-2])
            continue
        for chunk in SCRIPT.split(part):
            match = re.fullmatch(r"<(sub|sup)>([^<>]+)</\1>", chunk)
            run = paragraph.add_run(match[2] if match else chunk)
            if match:
                run.font.subscript = match[1] == "sub"
                run.font.superscript = match[1] == "sup"


def add_picture(paragraph, payload, width):
    with Image.open(BytesIO(payload)) as source:
        size = min(width, 240 * source.width / source.height)
        png = BytesIO()
        source.convert("RGBA").save(png, "PNG")
    paragraph.add_run().add_picture(png, width=Pt(size))


def build_word(details, sections, mode):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Pt(595.28), Pt(841.89)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Pt(40)
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "DejaVu Serif", Pt(10)
    style.paragraph_format.space_after = Pt(4)
    width = (515 - 18) / 2 if details.get("page_columns") == "two" else 515
    if details["logo"]:
        add_picture(doc.add_paragraph(), details["logo"], 76)
    for value in [details["institution"], "  ".join(filter(None, [
            details["title"], f"({details['date']:%d-%m-%Y})" if details["date"] else ""])),
            "    ".join(filter(None, [
                f"Duration: {details['duration']} min" if details["duration"] else "",
                f"Max. Marks: {details['marks']}" if details["marks"] else ""]))]:
        if value:
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run(value).bold = True
    if details.get("page_columns") == "two":
        from docx.enum.section import WD_SECTION_START
        section = doc.add_section(WD_SECTION_START.CONTINUOUS)
        cols = section._sectPr.find(qn("w:cols"))
        cols.set(qn("w:num"), "2")
        cols.set(qn("w:space"), "360")

    def make_table(rows, columns):
        table = doc.add_table(rows=rows, cols=columns)
        table.autofit = False
        for column in table.columns:
            column.width = Pt(width / columns)
        return table

    def size_row(row):
        for cell in row.cells:
            cell.width = Pt(width / len(row.cells))
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))

    def content(question, answer, number):
        data = question.structured
        prefix = f"{number}. ({question.correct_option}) " if answer else f"{number}. "
        if not data:
            paragraph = doc.add_paragraph(prefix)
            field = question.hint if answer else question.artwork
            if field:
                paragraph.paragraph_format.keep_with_next = True
                with field.open("rb") as asset:
                    add_picture(doc.add_paragraph(), asset.read(), width - 10)
            return
        start = len(doc.paragraphs)
        for part in content_rows(data["hint" if answer else "stem"]):
            if isinstance(part, str):
                paragraph = doc.add_paragraph()
                write_text(paragraph, prefix + part)
            else:
                if prefix:
                    doc.add_paragraph(prefix)
                table = make_table(0, len(part[0]))
                table.style = "Table Grid"
                for row in part:
                    table_row = table.add_row()
                    size_row(table_row)
                    cells = table_row.cells
                    for cell, value in zip(cells, row):
                        write_text(cell.paragraphs[0], value)
            prefix = ""
        for asset in data["diagrams"]:
            if asset["placement"] == ("hint" if answer else "question"):
                add_picture(doc.add_paragraph(), b64decode(asset["png"]), width - 10)
        if not answer:
            columns = option_columns(data["options"], details.get("option_layout") or "one", width - 12)
            options = [f"({i}) {value}" for i, value in enumerate(data["options"], 1)]
            if columns == 1:
                for value in options:
                    write_text(doc.add_paragraph(), value)
            else:
                table = make_table(4 // columns, columns)
                for row in table.rows:
                    size_row(row)
                for cell, value in zip((cell for row in table.rows for cell in row.cells), options):
                    write_text(cell.paragraphs[0], value)
                doc.add_paragraph()
        for paragraph in doc.paragraphs[start:-1]:
            paragraph.paragraph_format.keep_with_next = True
        if len(doc.paragraphs) > start:
            doc.paragraphs[-1].paragraph_format.space_after = Pt(9)

    for answer in ([False, True] if mode == "combined" else [mode == "answer"]):
        if answer:
            if mode == "combined":
                doc.add_page_break()
            doc.add_heading("Answer Key", level=1)
        number = details["start_number"]
        for subject, questions in sections:
            doc.add_heading(subject.upper(), level=2)
            for question in questions:
                content(question, answer, number)
                if mode == "paired":
                    content(question, True, number)
                number += 1
    output = BytesIO()
    doc.save(output)
    return output.getvalue()
