from io import BytesIO
from xml.sax.saxutils import escape

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image as PDFImage
from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, Flowable, Indenter, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


from .structured import body_style, question_blocks
from .watermark import watermark_image


def artwork_image(field, max_width):
    with field.open("rb") as asset, Image.open(asset) as source:
        bitmap = BytesIO()
        source.convert("RGB").save(bitmap, "PNG")
    picture = PDFImage(bitmap)
    scale = min(.52, max_width / picture.imageWidth, 680 / picture.imageHeight)
    picture.drawWidth = picture.imageWidth * scale
    picture.drawHeight = picture.imageHeight * scale
    picture.hAlign = "LEFT"
    return picture


class QuestionNumber(Flowable):
    """Draw the number in the margin on the first text baseline."""
    _ZEROSIZE = True
    keepWithNext = True

    def __init__(self, number, gutter):
        super().__init__()
        self.number = number
        self.gutter = gutter

    def draw(self):
        self.canv.setFont(body_style().fontName, body_style().fontSize)
        self.canv.drawString(-self.gutter, -body_style().fontSize, f"{self.number}.")


def build_pdf(details, sections, *, answer_key=False, preview=False, mode=None):
    output = BytesIO()
    two = details.get("page_columns") == "two"
    watermark = details.get("watermark") if not (preview or answer_key or mode == "answer") else ""
    document = (BaseDocTemplate if two or watermark else SimpleDocTemplate)(
        output, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40,
        title=details["title"] or ("Answer Key" if answer_key else "Question Paper"),
    )
    navy = colors.black
    title = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=15, leading=19, alignment=TA_CENTER)
    subtitle = ParagraphStyle("Subtitle", parent=title, fontSize=12, leading=15)
    label = ParagraphStyle("Label", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=navy)
    right_label = ParagraphStyle("RightLabel", parent=label, alignment=TA_RIGHT)
    subject_label = ParagraphStyle("Subject", parent=label, alignment=TA_CENTER)
    gutter = 32
    flow = []
    width = document.width - 12
    branding = []
    if details["institution"]:
        branding.append(Paragraph(escape(details["institution"]), title))
    subtitle_parts = [escape(details["title"])] if details["title"] else []
    if details["date"]:
        subtitle_parts.append(f"({details['date']:%d-%m-%Y})")
    if subtitle_parts:
        branding.append(Paragraph("  ".join(subtitle_parts), subtitle))
    if details["logo"]:
        logo = PDFImage(BytesIO(details["logo"]))
        scale = min(44 / logo.imageHeight, 76 / logo.imageWidth)
        logo.drawWidth = logo.imageWidth * scale
        logo.drawHeight = logo.imageHeight * scale
        branding = [Table([[logo, branding or "", ""]], colWidths=[85, width - 170, 85],
                          style=[("VALIGN", (0, 0), (-1, -1), "MIDDLE")])]
    flow.extend(branding)
    if details["duration"] or details["marks"]:
        duration = f"Duration: {details['duration']} min" if details["duration"] else ""
        marks = f"Max. Marks: {details['marks']}" if details["marks"] else ""
        flow.append(Table([[Paragraph(duration, label), Paragraph(marks, right_label)]],
                          colWidths=[width / 2] * 2))
    def double_rule():
        return Table([[""]], colWidths=[header_width], rowHeights=[4], style=[
            ("LINEABOVE", (0, 0), (-1, -1), .8, colors.black),
            ("LINEBELOW", (0, 0), (-1, -1), .8, colors.black),
        ])

    header_width = width
    standalone_answer = answer_key or mode == "answer"
    if standalone_answer:
        flow.append(Paragraph("Answer Key", subtitle))
    if flow:
        flow.extend([double_rule(), Spacer(1, 12)])
    header_height = 0
    if two and flow:
        header_height = sum(item.wrap(width, document.height)[1] for item in flow) + 24
        flow.append(FrameBreak)
    if two:
        width = (document.width - 18) / 2 - 12

    answer_header = []
    answer_header_height = 0
    if mode == "combined":
        if subtitle_parts:
            answer_header.append(Paragraph("  ".join(subtitle_parts), subtitle))
        answer_header.extend([Paragraph("Answer Key", subtitle), double_rule(), Spacer(1, 12)])
        answer_header_height = sum(item.wrap(header_width, document.height)[1] for item in answer_header) + 24

    for is_answer in ([False, True] if mode == "combined" else [standalone_answer]):
        if is_answer and mode == "combined":
            if two or watermark:
                flow.append(NextPageTemplate("AnswerStart"))
            flow.extend([PageBreak(), *answer_header])
            if two:
                flow.append(FrameBreak)
        answer_key = is_answer
        number = details["start_number"] - 1
        for subject, questions in sections:
            heading = Paragraph(subject.upper(), subject_label)
            if answer_key and any(question.hint or question.structured for question in questions):
                for index, question in enumerate(questions):
                    number += 1
                    entry = [Paragraph(f"({question.correct_option})", label)]
                    if question.structured:
                        entry.extend(question_blocks(question.structured, width if preview else width - gutter, answer_key=True))
                    elif question.hint:
                        entry.append(artwork_image(question.hint, width if preview else width - gutter))
                    if not preview:
                        entry = [Indenter(left=gutter), QuestionNumber(number, gutter), *entry, Indenter(left=-gutter)]
                    flow.append(KeepTogether(([heading] if index == 0 else []) + entry + [Spacer(1, 9)]))
                continue
            if answer_key:
                answers = []
                for question in questions:
                    number += 1
                    answers.append(f"{number}.  ({question.correct_option})")
                rows = [answers[i:i + 5] for i in range(0, len(answers), 5)]
                rows[-1] += [""] * (5 - len(rows[-1]))
                table = Table(rows, colWidths=[width / 5] * 5, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f0f4fa"), colors.white]),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                heading.keepWithNext = True
                flow.extend([heading, table, Spacer(1, 16)])
                continue
            for index, question in enumerate(questions):
                number += 1
                content_width = width if preview else width - gutter
                if question.structured:
                    entry = question_blocks(question.structured, content_width,
                                            option_layout=details.get("option_layout") or "one")
                else:
                    entry = [artwork_image(question.artwork, content_width)]
                if mode == "paired":
                    entry.append(Paragraph(f"Answer: ({question.correct_option})", label))
                    if question.structured:
                        entry.extend(question_blocks(question.structured, content_width, answer_key=True))
                    elif question.hint:
                        entry.append(artwork_image(question.hint, content_width))
                if not preview:
                    entry = [Indenter(left=gutter), QuestionNumber(number, gutter), *entry, Indenter(left=-gutter)]
                flow.append(KeepTogether(([heading] if index == 0 else []) + entry + [Spacer(1, 8)]))

    def footer(canvas, doc):
        canvas.setFillColor(navy)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0] - 40, 23, f"Page {doc.page}")

    mark = None
    if watermark:
        payload, mark_width, mark_height = watermark_image(watermark)
        mark = ImageReader(BytesIO(payload))

    def question_mark(canvas, doc):
        if mark is not None:
            canvas.drawImage(mark, (A4[0] - mark_width) / 2, (A4[1] - mark_height) / 2,
                             width=mark_width, height=mark_height, mask="auto")

    if two:
        column_width = (document.width - 18) / 2

        def columns(height):
            return [Frame(document.leftMargin + offset, document.bottomMargin, column_width, height)
                    for offset in (0, column_width + 18)]

        def opening_frames(height):
            frames = columns(document.height - height)
            if height:
                frames.insert(0, Frame(document.leftMargin, document.bottomMargin + document.height - height,
                                       document.width, height, topPadding=0, bottomPadding=0))
            return frames

        templates = [
            PageTemplate("First", opening_frames(header_height), onPage=footer, onPageEnd=question_mark,
                         autoNextPageTemplate="Body"),
            PageTemplate("Body", columns(document.height), onPage=footer, onPageEnd=question_mark),
        ]
        if answer_header:
            templates.append(PageTemplate("AnswerStart", opening_frames(answer_header_height),
                                          onPage=footer, autoNextPageTemplate="AnswerBody"))
            templates.append(PageTemplate("AnswerBody", columns(document.height), onPage=footer))
        document.addPageTemplates(templates)
        document.build(flow)
    elif watermark:
        def page_frame():
            return Frame(document.leftMargin, document.bottomMargin, document.width, document.height)

        document.addPageTemplates([
            PageTemplate("Questions", page_frame(), onPage=footer, onPageEnd=question_mark),
            PageTemplate("AnswerStart", page_frame(), onPage=footer),
        ])
        document.build(flow)
    else:
        document.build(flow, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
