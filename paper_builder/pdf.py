from io import BytesIO
from xml.sax.saxutils import escape

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Image as PDFImage
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_pdf(details, sections, *, answer_key=False):
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40,
        title=details["title"],
    )
    navy = colors.HexColor("#102341")
    title = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=23, leading=29, textColor=navy)
    label = ParagraphStyle("Label", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=navy)
    body = ParagraphStyle("Body", fontSize=10, leading=14)
    flow = [Paragraph(escape(details["institution"]), label)]
    if details["logo"]:
        logo = PDFImage(BytesIO(details["logo"]))
        logo.drawWidth, logo.drawHeight = logo.imageWidth, logo.imageHeight
        scale = min(56 / logo.drawHeight, 150 / logo.drawWidth)
        logo.drawWidth *= scale
        logo.drawHeight *= scale
        logo.hAlign = "RIGHT"
        flow.insert(0, logo)
    flow.append(Paragraph(escape(details["title"]) + (" | Answer Key" if answer_key else ""), title))
    flow.extend([Spacer(1, 8), Paragraph(
        f"{details['date']:%d %b %Y} &nbsp; | &nbsp; {details['marks']} marks"
        f" &nbsp; | &nbsp; {details['duration']} minutes", body
    ), Spacer(1, 16)])

    number = details["start_number"] - 1
    for subject, questions in sections:
        heading = Paragraph(subject.upper(), label)
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
            with question.artwork.open("rb") as asset, Image.open(asset) as source:
                bitmap = BytesIO()
                source.convert("RGB").save(bitmap, "PNG")
            picture = PDFImage(bitmap)
            scale = min(.52, (document.width - 46) / picture.imageWidth, 680 / picture.imageHeight)
            picture.drawWidth = picture.imageWidth * scale
            picture.drawHeight = picture.imageHeight * scale
            table = Table([[Paragraph(f"{number}.", label), picture]], colWidths=[40, document.width - 40])
            table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                       ("ALIGN", (1, 0), (1, 0), "LEFT")]))
            flow.append(KeepTogether(([heading] if index == 0 else []) + [table, Spacer(1, 8)]))

    def footer(canvas, doc):
        canvas.setFillColor(navy)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(A4[0] - 40, 23, f"Page {doc.page}")

    document.build(flow, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
