from io import BytesIO
from xml.sax.saxutils import escape

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image as PDFImage
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


from .structured import question_blocks


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


def build_pdf(details, sections, *, answer_key=False, preview=False):
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40,
        title=details["title"] or ("Answer Key" if answer_key else "Question Paper"),
    )
    navy = colors.black
    title = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=15, leading=19, alignment=TA_CENTER)
    subtitle = ParagraphStyle("Subtitle", parent=title, fontSize=12, leading=15)
    label = ParagraphStyle("Label", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=navy)
    right_label = ParagraphStyle("RightLabel", parent=label, alignment=TA_RIGHT)
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
    if flow:
        flow.append(Table([[""]], colWidths=[width], rowHeights=[4], style=[
            ("LINEABOVE", (0, 0), (-1, -1), .8, colors.black),
            ("LINEBELOW", (0, 0), (-1, -1), .8, colors.black),
        ]))
        flow.append(Spacer(1, 12))
    if answer_key:
        flow.append(Paragraph("Answer Key", subtitle))

    number = details["start_number"] - 1
    for subject, questions in sections:
        heading = Paragraph(subject.upper(), label)
        if answer_key and any(question.hint or question.structured for question in questions):
            for index, question in enumerate(questions):
                number += 1
                entry = [Paragraph(f"({question.correct_option})" if preview else f"{number}.  ({question.correct_option})", label)]
                if question.structured:
                    entry.extend(question_blocks(question.structured, width, answer_key=True))
                elif question.hint:
                    entry.append(artwork_image(question.hint, document.width - 12))
                flow.append(KeepTogether(([heading] if index == 0 else []) + entry + [Spacer(1, 9)]))
            continue
        if answer_key:
            answers = []
            for question in questions:
                number += 1
                answers.append(f"{number}.  ({question.correct_option})")
            rows = [answers[i:i + 5] for i in range(0, len(answers), 5)]
            rows[-1] += [""] * (5 - len(rows[-1]))
            table = Table(rows, colWidths=[document.width / 5] * 5, hAlign="LEFT")
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
            if question.structured:
                entry = question_blocks(question.structured, width, prefix="" if preview else f"{number}. ")
                flow.append(KeepTogether(([heading] if index == 0 else []) + entry + [Spacer(1, 8)]))
                continue
            picture = artwork_image(question.artwork, document.width - 52)
            table = Table([[Paragraph(f"{number}.", label), picture]], colWidths=[40, width - 40])
            table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                       ("ALIGN", (1, 0), (1, 0), "LEFT"),
                                       ("TOPPADDING", (0, 0), (-1, -1), 0),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            flow.append(KeepTogether(([heading] if index == 0 else []) + [table, Spacer(1, 8)]))

    def footer(canvas, doc):
        canvas.setFillColor(navy)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0] - 40, 23, f"Page {doc.page}")

    document.build(flow, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
