"""Editable Word export for structured bank questions."""
import re
from base64 import b64decode
from io import BytesIO
from xml.etree import ElementTree as ET

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from latex2mathml.converter import convert
from PIL import Image

from .layout import content_rows, option_columns
from .structured import MATH, SCRIPT, normalize_math, split_question_label
from .watermark import watermark_image


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
        if tag == "mover" and len(element) == 2 and element[1].text in ("^", "→", "¯"):
            accent = node("chr")
            accent.set(qn("m:val"), {"^": "\u0302", "→": "\u20d7", "¯": "\u0304"}[element[1].text])
            return [node("acc", [node("accPr", [accent]), node("e", translate(element[0]))])]
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


def write_text(paragraph, value, *, bold_labels=False):
    if bold_labels:
        label, value = split_question_label(value)
        if label:
            paragraph.add_run(label).bold = True
    for part in MATH.split(normalize_math(value)):
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


def add_watermark(section, text):
    payload, width, height = watermark_image(text)
    run = section.header.paragraphs[0].add_run()
    inline = run.add_picture(BytesIO(payload), width=Pt(width), height=Pt(height))._inline
    anchor = OxmlElement("wp:anchor")
    for name, value in {
        "distT": "0", "distB": "0", "distL": "0", "distR": "0", "simplePos": "0",
        "relativeHeight": "1", "behindDoc": "0", "locked": "0", "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        anchor.set(name, value)
    position = OxmlElement("wp:simplePos")
    position.set("x", "0")
    position.set("y", "0")
    anchor.append(position)
    for axis in ("H", "V"):
        position = OxmlElement(f"wp:position{axis}")
        position.set("relativeFrom", "page")
        alignment = OxmlElement("wp:align")
        alignment.text = "center"
        position.append(alignment)
        anchor.append(position)
    anchor.append(inline.extent)
    anchor.append(OxmlElement("wp:wrapNone"))
    for child in list(inline):
        anchor.append(child)
    inline.getparent().replace(inline, anchor)


def build_word(details, sections, mode):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Pt(595.28), Pt(841.89)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Pt(40)
    watermark = details.get("watermark") if mode != "answer" else ""
    if watermark:
        add_watermark(sec, watermark)
    style = doc.styles["Normal"]
    style.font.name, style.font.size = "DejaVu Serif", Pt(10)
    style.paragraph_format.space_after = Pt(4)
    width = (515 - 18) / 2 if details.get("page_columns") == "two" else 515
    if details["logo"]:
        add_picture(doc.add_paragraph(), details["logo"], 76)
    title_and_date = "  ".join(filter(None, [
        details["title"], f"({details['date']:%d-%m-%Y})" if details["date"] else "",
    ]))
    metadata = "    ".join(filter(None, [
        f"Duration: {details['duration']} min" if details["duration"] else "",
        f"Max. Marks: {details['marks']}" if details["marks"] else "",
    ]))
    two = details.get("page_columns") == "two"

    def header(*values, answer=False):
        paragraphs = []
        for value in filter(None, values):
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run(value).bold = True
            paragraphs.append(paragraph)
        if answer:
            heading = doc.add_heading("Answer Key", level=1)
            heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraphs.append(heading)
        if paragraphs:
            borders = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            for key, value in (("val", "double"), ("sz", "6"), ("space", "4")):
                bottom.set(qn(f"w:{key}"), value)
            borders.append(bottom)
            paragraphs[-1]._p.get_or_add_pPr().insert_element_before(borders, "w:spacing", "w:jc")
            paragraphs[-1].paragraph_format.space_after = Pt(12)

    def column_section(start, count):
        section = doc.add_section(start)
        cols = section._sectPr.find(qn("w:cols"))
        cols.set(qn("w:num"), str(count))
        cols.set(qn("w:space"), "360")
        return section

    header(details["institution"], title_and_date, metadata, answer=mode == "answer")
    # OJAS_COVERED_CHAPTERS_WORD
    from test_patterns.exporting import word_coverage
    word_coverage(doc, details)
    if two:
        column_section(WD_SECTION_START.CONTINUOUS, 2)

    gutter = 32
    width -= gutter

    def body_paragraph(number=None):
        paragraph = doc.add_paragraph()
        fmt = paragraph.paragraph_format
        fmt.left_indent = Pt(gutter)
        if number is not None:
            fmt.first_line_indent = Pt(-gutter)
            fmt.tab_stops.add_tab_stop(Pt(gutter))
            paragraph.add_run(f"{number}.\t")
        return paragraph

    def make_table(rows, columns):
        table = doc.add_table(rows=rows, cols=columns)
        table.autofit = False
        indent = OxmlElement("w:tblInd")
        indent.set(qn("w:w"), str(gutter * 20))
        indent.set(qn("w:type"), "dxa")
        table._tbl.tblPr.insert_element_before(indent, "w:tblLayout", "w:tblLook")
        for column in table.columns:
            column.width = Pt(width / columns)
        return table

    def size_row(row):
        for cell in row.cells:
            cell.width = Pt(width / len(row.cells))
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))

    def content(question, answer, number):
        data = question.structured
        prefix = f"({question.correct_option}) " if answer else ""
        if not data:
            paragraph = body_paragraph(number)
            paragraph.add_run(prefix)
            field = question.hint if answer else question.artwork
            if field:
                paragraph.paragraph_format.keep_with_next = True
                with field.open("rb") as asset:
                    add_picture(body_paragraph(), asset.read(), width - 10)
            return
        start = len(doc.paragraphs)
        for index, part in enumerate(content_rows(data["hint" if answer else "stem"])):
            if isinstance(part, str):
                paragraph = body_paragraph(number if index == 0 else None)
                write_text(paragraph, prefix + part, bold_labels=not answer)
            else:
                if index == 0:
                    body_paragraph(number).add_run(prefix)
                table = make_table(0, len(part[0]))
                table.style = "Table Grid"
                for row in part:
                    table_row = table.add_row()
                    size_row(table_row)
                    cells = table_row.cells
                    for cell, value in zip(cells, row):
                        write_text(cell.paragraphs[0], value, bold_labels=not answer)
            prefix = ""
        for asset in data["diagrams"]:
            if asset["placement"] == ("hint" if answer else "question"):
                add_picture(body_paragraph(), b64decode(asset["png"]), width - 10)
        if not answer:
            columns = option_columns(data["options"], details.get("option_layout") or "one", width - 12)
            options = [f"({i}) {value}" for i, value in enumerate(data["options"], 1)]
            if columns == 1:
                for value in options:
                    write_text(body_paragraph(), value)
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
        if answer and mode == "combined":
            if two or watermark:
                section = column_section(WD_SECTION_START.NEW_PAGE, 1)
                if watermark:
                    section.header.is_linked_to_previous = False
            else:
                doc.add_page_break()
            header(title_and_date, answer=True)
            if two:
                column_section(WD_SECTION_START.CONTINUOUS, 2)
        number = details["start_number"]
        for section_index, (subject, questions) in enumerate(sections):
            if details.get("section_starts"):
                number = details["section_starts"][section_index] - 0
            heading = doc.add_heading(subject.upper(), level=2)
            heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for question in questions:
                content(question, answer, number)
                if mode == "paired":
                    content(question, True, number)
                number += 1
    output = BytesIO()
    doc.save(output)
    return output.getvalue()
