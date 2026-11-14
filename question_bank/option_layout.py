"""Normalize unambiguous multiple-choice layouts without retyping formulas."""
import io
import re

from PIL import Image

from .pdf_import import render_crop


def aligned_artwork(document, text_page, box, mask):
    page, left, top, right, bottom = box
    words = text_page.crop((left, top, right, bottom)).extract_words(x_tolerance=1.5)
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
    artwork = [*words, *text_page.images, *text_page.edges, *text_page.curves]
    artwork = [obj for obj in artwork if obj["x1"] > left and obj["x0"] < right
               and obj["bottom"] > top and obj["top"] < bottom]
    horizontal = []
    for row in rows:
        marker_top = min(word["top"] for word in row)
        cuts = [marker_top - offset / 2 for offset in range(6, -1, -1)]
        cut = next((y for y in cuts if not any(obj["top"] < y < obj["bottom"]
                                             for obj in artwork)), None)
        if cut is None or cut <= (horizontal[-1] if horizontal else top):
            return None
        horizontal.append(cut)
    horizontal.append(bottom)

    crops = [[page, left, top, right, horizontal[0]]]
    for row, y0, y1 in zip(rows, horizontal, horizontal[1:]):
        cuts = [left]
        for marker in row[1:]:
            boundary = marker["x0"]
            cuts.append(next((x for x in (boundary - 1, boundary - .5, boundary)
                              if not any(obj["x0"] < x < obj["x1"] and obj["top"] < y1
                                         and obj["bottom"] > y0 for obj in artwork)), boundary))
        cuts.append(right)
        if any(obj["x0"] < cut < obj["x1"] and obj["top"] < y1 and obj["bottom"] > y0
               for cut in cuts[1:-1] for obj in artwork):
            return None
        crops.extend([page, x0, y0, x1, y1] for x0, x1 in zip(cuts, cuts[1:]))

    parts = []
    for index, crop in enumerate(crops):
        payload, _, _ = render_crop(document, [crop], first_mask=mask if index == 0 else None)
        with Image.open(io.BytesIO(payload)) as image:
            part = image.convert("RGB")
            if index:
                ink = part.convert("L").point(lambda tone: 255 if tone < 210 else 0).getbbox()
                if ink:
                    part = part.crop((ink[0], 0, part.width, part.height))
            parts.append(part)
    # A fixed left edge and row gap serve both short and long option text.
    canvas = Image.new("RGB", (max(part.width for part in parts), sum(part.height for part in parts)), "white")
    offset = 0
    for part in parts:
        canvas.paste(part, (0, offset))
        offset += part.height
    output = io.BytesIO()
    canvas.save(output, "WEBP", quality=94)
    return output.getvalue()
