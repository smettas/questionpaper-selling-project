"""Normalize unambiguous multiple-choice layouts without retyping formulas."""
import io
import re

from PIL import Image

from .pdf_import import render_crop


def aligned_artwork(document, text_page, box, mask):
    page, left, top, right, bottom = box
    words = text_page.crop((left, top, right, bottom)).extract_words()
    markers = [word for word in words if re.fullmatch(r"\([1-4]\)", word["text"])]
    markers.sort(key=lambda word: word["top"])
    if len(markers) != 4:
        return None
    rows = []
    for marker in markers:
        if not rows or abs(rows[-1][0]["top"] - marker["top"]) > 4:
            rows.append([])
        rows[-1].append(marker)
    if not rows or len({len(row) for row in rows}) != 1:
        return None
    for row in rows:
        row.sort(key=lambda word: word["x0"])
    if [word["text"] for row in rows for word in row] != ["(1)", "(2)", "(3)", "(4)"]:
        return None
    first_top = min(word["top"] for word in rows[0])
    if first_top - top < 8:
        return None
    # Use the whitespace between rows and between option columns. If a
    # boundary intersects text, keep the source artwork for that question.
    horizontal = [min(word["top"] for word in row) - 3 for row in rows] + [bottom]
    vertical = [left] + [min(row[i]["x0"] for row in rows) - 3
                          for i in range(1, len(rows[0]))] + [right]
    artwork = [*words, *text_page.images, *text_page.edges, *text_page.curves]
    artwork = [obj for obj in artwork if obj["x1"] > left and obj["x0"] < right
               and obj["bottom"] > top and obj["top"] < bottom]
    for cut in horizontal[:-1]:
        if any(word["top"] < cut < word["bottom"] for word in artwork):
            return None
    for cut in vertical[1:-1]:
        if any(word["bottom"] > horizontal[0] and word["x0"] < cut < word["x1"] for word in artwork):
            return None

    crops = [[page, left, top, right, horizontal[0]]]
    for y0, y1 in zip(horizontal, horizontal[1:]):
        crops.extend([page, x0, y0, x1, y1] for x0, x1 in zip(vertical, vertical[1:]))

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
