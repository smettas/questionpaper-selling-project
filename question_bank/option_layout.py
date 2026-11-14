"""Normalize unambiguous multiple-choice layouts without retyping formulas."""
import io
import re

from PIL import Image

from .pdf_import import render_crop


def aligned_artwork(document, text_page, box, mask):
    page, left, top, right, bottom = box
    words = text_page.crop((left, top, right, bottom)).extract_words()
    markers = [word for word in words if re.match(r"^\([1-4]\)", word["text"])]
    markers.sort(key=lambda word: word["top"])
    if len(markers) != 4:
        return None
    rows = []
    for marker in markers:
        if not rows or abs(rows[-1][0]["top"] - marker["top"]) > 4:
            rows.append([])
        rows[-1].append(marker)
    for row in rows:
        row.sort(key=lambda word: word["x0"])
    if [word["text"][:3] for row in rows for word in row] != ["(1)", "(2)", "(3)", "(4)"]:
        return None
    first_top = min(word["top"] for word in rows[0])
    if first_top - top < 8:
        return None
    # Use the whitespace between rows and between option columns. If a
    # boundary intersects text, keep the source artwork for that question.
    horizontal = [min(word["top"] for word in row) - 3 for row in rows] + [bottom]
    artwork = [*words, *text_page.images, *text_page.edges, *text_page.curves]
    artwork = [obj for obj in artwork if obj["x1"] > left and obj["x0"] < right
               and obj["bottom"] > top and obj["top"] < bottom]
    if any(obj["top"] < cut < obj["bottom"] for cut in horizontal[:-1] for obj in artwork):
        return None

    crops = [[page, left, top, right, horizontal[0]]]
    for row, y0, y1 in zip(rows, horizontal, horizontal[1:]):
        cuts = [left, *(marker["x0"] - 1 for marker in row[1:]), right]
        if any(obj["x0"] < cut < obj["x1"] and obj["top"] < y1 and obj["bottom"] > y0
               for cut in cuts[1:-1] for obj in artwork):
            return None
        crops.extend([page, x0, y0, x1, y1] for x0, x1 in zip(cuts, cuts[1:]))

    parts = []
    for index, crop in enumerate(crops):
        payload, _, _ = render_crop(document, [crop], first_mask=mask if index == 0 else None)
        with Image.open(io.BytesIO(payload)) as image:
            parts.append(image.convert("RGB"))
    # A fixed left edge and row gap serve both short and long option text.
    canvas = Image.new("RGB", (max(part.width for part in parts), sum(part.height for part in parts)), "white")
    offset = 0
    for part in parts:
        canvas.paste(part, (0, offset))
        offset += part.height
    output = io.BytesIO()
    canvas.save(output, "WEBP", quality=94)
    return output.getvalue()
