"""Import the single-column Hints and Solutions section of an answer PDF."""
import io
import re

from .pdf_import import CHOICE, _choice_number, _validate_numbers, pdfplumber

TITLE = re.compile(r"hints\s+(?:and|&)\s+solutions", re.I)
LABEL = re.compile(rf"^\s*(\d{{1,3}})\s*[.)]\s*ans\.?\s*:?\s*\(\s*({CHOICE})\s*\)", re.I)


def read_hints(payload, count):
    """Return answer choices and artwork crops, or None for a regular key."""
    entries = {}
    active = None
    started = False
    with pdfplumber.open(io.BytesIO(payload)) as document:
        for page in document.pages:
            lines = page.extract_text_lines(return_chars=True)
            heading = next((i for i, line in enumerate(lines)
                            if TITLE.fullmatch(line["text"].strip())), None)
            if heading is not None:
                started = True
                lines = lines[heading + 1:]
            if not started:
                continue

            # Trim page numbers while retaining the solution lines above them.
            lines = [line for line in lines
                     if not (line["top"] > page.height * .9
                             and re.fullmatch(r"(?:page\s+)?\d+", line["text"].strip(), re.I))]
            if not lines:
                continue
            markers = [(index, match) for index, line in enumerate(lines)
                       if (match := LABEL.match(line["text"]))]
            bottom = min(page.height, lines[-1]["bottom"] + 3)
            if active and (not markers or markers[0][0]):
                continuation_bottom = lines[markers[0][0]]["top"] - 2 if markers else bottom
                active.append([page.page_number, 0, max(0, lines[0]["top"] - 2),
                               page.width - 1, continuation_bottom])
            for position, (index, marker) in enumerate(markers):
                number = int(marker[1])
                if number in entries:
                    raise ValueError(f"Hints and Solutions repeats question {number}.")
                line = lines[index]
                next_index = markers[position + 1][0] if position + 1 < len(markers) else len(lines)
                end = lines[next_index]["top"] - 2 if next_index < len(lines) else bottom
                # pdfplumber's text map includes synthetic spaces. The PDF's
                # actual characters do not necessarily include those spaces.
                prefix_length = len(re.sub(r"\s", "", marker[0]))
                characters = [char for char in line["chars"] if not char["text"].isspace()]
                prefix = characters[:prefix_length]
                if len(prefix) != prefix_length:
                    raise ValueError(f"Could not isolate the answer label for question {number}.")
                mask = (min(char["x0"] for char in prefix), min(char["top"] for char in prefix),
                        max(char["x1"] for char in prefix), max(char["bottom"] for char in prefix))
                active = [[page.page_number, 0, max(0, line["top"] - 3), page.width - 1, end]]
                entries[number] = (_choice_number(marker[2]), active, mask)
    if not started:
        return None
    _validate_numbers(entries.keys(), count, "Hints and Solutions")
    return entries
