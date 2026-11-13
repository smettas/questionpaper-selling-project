"""Locate questions by selectable numbering and render original artwork."""
import io
import re
from collections import Counter
from contextlib import ExitStack

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageDraw

NUMBER = re.compile(r'(\d{1,3})[.)]')
CHOICE = r'[1-4A-Da-d]'
KEY_PAIR = rf'(\d{{1,3}})\s*[.)]\s*\(\s*({CHOICE})\s*\)'
COMPACT_KEY_ROW = re.compile(rf'(?:{KEY_PAIR}\s*){{2,}}')
ACADEMY_FOOTER = re.compile(r'(?:\d+\s+)?OJAS ONE ACADEMY OF EXCELLENCE(?:\s+\d+)?', re.I)
RUNNING_HEADER = {'SIT', 'NMT', 'OWT', 'ODT'}
SUBJECT_HEADINGS = {'PHYSICS', 'CHEMISTRY', 'BIOLOGY', 'BOTANY', 'ZOOLOGY', 'MATHEMATICS', 'MATHS'}
MODEL_HEADER = re.compile(r'NEET MODEL (?:EXAM|TEST)\s*\(NMT\)\s*[-–]\s*\d+', re.I)
MAX_BYTES = 25 * 1024 * 1024


def _validate_numbers(numbers, count, name):
    counts = Counter(numbers)
    missing = sorted(set(range(1, count + 1)) - counts.keys())
    duplicates = sorted(n for n, v in counts.items() if v > 1)
    extra = sorted(counts.keys() - set(range(1, count + 1)))
    if missing or duplicates or extra:
        raise ValueError(f'{name}: missing {missing}; duplicate {duplicates}; unexpected {extra}.')


def _lanes(page, words, *, cutoff=None, answers=False):
    width, height = page.width, page.height
    left, right = [], []
    for index, w in enumerate(words):
        m = NUMBER.fullmatch(w['text'])
        label_end = w['x1']
        if not m and w['text'].isdigit() and index + 1 < len(words):
            punctuation = words[index + 1]
            if (
                punctuation['text'] in {'.', ')'}
                and abs(punctuation['bottom'] - w['bottom']) < 2
                and 0 <= punctuation['x0'] - w['x1'] <= w['height']
            ):
                m = NUMBER.fullmatch(w['text'] + punctuation['text'])
                label_end = punctuation['x1']
        if not m or w['top'] < height * .029 or w['bottom'] > (cutoff or height * .96):
            continue
        if answers:
            # Numbered steps inside an explanation are not answer headings.
            # Check the text directly to the right on the same baseline.
            following = sorted(
                (word for word in words
                 if 0 <= word['x0'] - label_end <= w['height'] * 5
                 and abs(word['bottom'] - w['bottom']) <= 3),
                key=lambda word: word['x0'],
            )
            if not re.match(rf'\(\s*{CHOICE}\s*\)', ' '.join(word['text'] for word in following)):
                continue
        if w['x0'] < width * .125:
            left.append((int(m[1]), w))
        elif width * .502 < w['x0'] < width * .56:
            right.append((int(m[1]), w))
    def aligned(anchors, tolerance=2.5):
        if not anchors:
            return anchors
        x = max((w['x0'] for _, w in anchors),
                key=lambda x: sum(abs(w['x0'] - x) < tolerance for _, w in anchors))
        return [(n, w) for n, w in anchors if abs(w['x0'] - x) < tolerance]

    left, right = aligned(left), aligned(right, tolerance=4)
    left_edge = max(0, min([width * .043] + [w['x0'] - 3 for _, w in left]))
    # Numbered choices in a full-width question may sit near the middle.
    if right and max(n for n, _ in right) > max((n for n, _ in left), default=0):
        return [(left_edge, width * .498, sorted(left, key=lambda a: a[1]['top'])),
                (width * .502, width * .957, sorted(right, key=lambda a: a[1]['top']))]
    return [(left_edge, width * .957, sorted(left, key=lambda a: a[1]['top']))]


def _choice_number(choice):
    return int(choice) if choice.isdigit() else ord(choice.upper()) - ord('A') + 1


def _inline_image_crop_top(anchor, images, right):
    default = anchor['top'] - 3
    image_top = min((
        image['top'] for image in images
        if anchor['x1'] <= image['x0'] < right
        and anchor['top'] - 2 * anchor['height'] <= image['top'] < default
        and image['bottom'] >= anchor['top']
    ), default=default)
    return image_top - 1 if image_top < default else default


def _heading_crop_top(anchor, words, images, right):
    """Follow the raised parts of an equation attached to the heading line."""
    limit = anchor['top'] - 2 * anchor['height']
    top = anchor['top']
    # Stacked parts of a limit or fraction can connect through another glyph.
    # Only look to the right of the question number and near its first line.
    for word in sorted(words, key=lambda w: w['top'], reverse=True):
        if (anchor['x1'] <= word['x0'] < right
                and limit <= word['top'] < top <= word['bottom']):
            top = word['top']
    return min(top - 3, _inline_image_crop_top(anchor, images, right))


def _page_border_rules(page):
    """Recognize the repeated full-width double rules in the academy frame."""
    rules = sorted(
        (obj for obj in (*page.lines, *page.curves, *page.rects)
         if obj['width'] >= page.width * .75 and obj['height'] <= 1
         and (obj['top'] <= page.height * .085 or obj['top'] >= page.height * .9)),
        key=lambda obj: obj['top'],
    )
    return [(first['top'], second['bottom']) for first, second in zip(rules, rules[1:])
            if 1 <= second['top'] - first['top'] <= 6
            and abs(first['x0'] - second['x0']) < 2
            and abs(first['x1'] - second['x1']) < 2]


def _segments(doc, *, answer_tables=False):
    """Return PDF-coordinate segments, including column/page continuations."""
    items = []
    key_rows = []
    active = None
    if not 1 <= len(doc.pages) <= 100:
        raise ValueError('Each PDF must have between 1 and 100 pages.')
    for page_no, page in enumerate(doc.pages):
        if page.width > 1200 or page.height > 1500:
            raise ValueError('Unsupported page size. Export at A4 or US Letter.')
        words = page.extract_words()
        if not words:
            raise ValueError(f'Page {page_no + 1} has no selectable text.')
        lines = page.extract_text_lines(return_chars=False)
        footer = min((
            line['top'] - 3 for line in lines
            if line['top'] > page.height * .88 and ACADEMY_FOOTER.fullmatch(line['text'].strip())
        ), default=None)
        body_top = max([page.height * .032] + [
            line['bottom'] + 4 for line in lines
            if line['top'] < page.height * .07 and line['text'].strip().upper() in RUNNING_HEADER
        ])
        for rule_top, rule_bottom in _page_border_rules(page):
            if rule_top < page.height / 2:
                body_top = max(body_top, rule_bottom + 1)
            else:
                footer = min(footer or page.height, rule_top - 1)
        if not answer_tables:
            # The final question may be followed by an end mark and an answers heading.
            if page_no == len(doc.pages) - 1:
                tail = [line for line in lines if footer is None or line['top'] < footer]
                if tail and tail[-1]['text'].strip().upper() == 'ANSWERS':
                    footer = tail.pop()['top'] - 3
                if tail and re.fullmatch(r'(?:\*\s*){3,}', tail[-1]['text'].strip()):
                    footer = tail[-1]['top'] - 3
        model_headers = [
            line for line in lines
            if line['top'] < page.height * .09 and MODEL_HEADER.fullmatch(line['text'].strip())
        ]
        cutoff = None
        if answer_tables:
            for table in page.find_tables():
                pairs = []
                for row in table.extract():
                    cells = [c.strip() for c in row if c and c.strip()]
                    if len(cells) % 2 == 0 and all(
                        re.fullmatch(r'\d{1,3}', n) and a in ('1','2','3','4')
                        for n, a in zip(cells[::2], cells[1::2])
                    ):
                        pairs.extend((int(n), int(a)) for n, a in zip(cells[::2], cells[1::2]))
                if pairs:
                    cutoff = min(cutoff or page.height, table.bbox[1])
                    key_rows.extend(pairs)
        # Some keys are laid out in unbordered rows of two or more numbered
        # options, with columns anywhere on the page. Read these before the
        # explanatory column splitter so they cannot be swallowed by a crop.
        compact = []
        if answer_tables:
            for line in lines:
                if cutoff is not None and line['top'] >= cutoff:
                    continue
                text = line['text'].strip()
                if COMPACT_KEY_ROW.fullmatch(text):
                    compact.append((line['top'], line['bottom']))
                    key_rows.extend((int(n), _choice_number(choice)) for n, choice in re.findall(KEY_PAIR, text))
            if compact:
                words = [w for w in words if not any(
                    top - 1 <= (w['top'] + w['bottom']) / 2 <= bottom + 1
                    for top, bottom in compact
                )]
        body_bottom = cutoff or page.height * .966
        lane_cutoff = cutoff
        if footer is not None:
            body_bottom = min(body_bottom, footer)
            lane_cutoff = min(lane_cutoff or page.height * .96, footer)
        lanes = _lanes(page, words, cutoff=lane_cutoff, answers=answer_tables)
        full_width_title = page_no == 0 and len(lanes) > 1 and any(
            line['top'] < page.height * .09
            and line['x0'] < lanes[0][1] and line['x1'] > lanes[1][0]
            and ACADEMY_FOOTER.fullmatch(line['text'].strip())
            for line in lines
        )
        for col, (x0, x1, anchors) in enumerate(lanes):
            lane_top = max([body_top] + [
                header['bottom'] + 1 for header in model_headers
                if header['x0'] < x1 and header['x1'] > x0
            ])
            if page_no == 0 and (col == 0 or full_width_title) and lanes[0][2]:
                lane_top = max(lane_top, lanes[0][2][0][1]['top'] - 30)
            # Compact key rows also stop explanation crops. A later numbered
            # explanation can start normally below the compact block.
            events = sorted(
                [(_heading_crop_top(w, words, page.images, x1), number)
                 for number, w in anchors] + [(top - 3, None) for top, _ in compact],
                key=lambda event: event[0],
            )
            if active and events:
                first_top = min(events[0][0], body_bottom)
                if not answer_tables:
                    first_top = min([first_top] + [
                        line['top'] - 3 for line in lines
                        if lane_top <= line['top'] < first_top
                        and x0 <= line['x0'] < x1 and line['text'].strip().upper() in SUBJECT_HEADINGS
                    ])
                if first_top > lane_top + 3 and any(
                    x0 <= w['x0'] < x1 and lane_top <= w['top'] < first_top
                    and w['text'].upper() not in SUBJECT_HEADINGS
                    for w in words
                ):
                    active[1].append([page_no + 1, x0, lane_top, x1, first_top])
            elif active and not events and cutoff is None:
                raise ValueError(f'Page {page_no + 1}, column {col + 1}: no question numbers found.')
            for index, (crop_top, number) in enumerate(events):
                if number is None:
                    active = None
                    continue
                top = max(lane_top, crop_top)
                bottom = events[index + 1][0] if index + 1 < len(events) else body_bottom
                active = (number, [[page_no + 1, x0, top, x1, bottom]])
                items.append(active)
        if cutoff is not None:
            active = None
    return items, key_rows


def inspect_papers(question_pdf, answer_pdf, count, *, overrides=None):
    with pdfplumber.open(io.BytesIO(question_pdf)) as q, pdfplumber.open(io.BytesIO(answer_pdf)) as a, pdfium.PdfDocument(answer_pdf) as key_doc:
        questions, _ = _segments(q)
        _validate_numbers([n for n, _ in questions], count, 'Question paper')
        if [n for n, _ in questions] != list(range(1, count + 1)):
            raise ValueError('Question numbering does not follow the detected page and column order.')
        answers, key_rows = _segments(a, answer_tables=True)
        explanations = {}
        for n, boxes in answers:
            page, x0, y0, x1, y1 = boxes[0]
            text = text_in_crop(key_doc, boxes[0])
            marker = re.search(rf'(?m)^\s*{n}\s*[.)]\s*\(\s*({CHOICE})\s*\)', text)
            if not marker:
                if 'answer' not in (overrides or {}).get(str(n), {}):
                    raise ValueError(f'Answer {n}: expected (1) to (4) or (A) to (D).')
            else:
                key_rows.append((n, _choice_number(marker[1])))
            if marker:
                has_illustration = any(
                    x0 < (image['x0'] + image['x1']) / 2 < x1
                    and y0 < (image['top'] + image['bottom']) / 2 < y1
                    for image in a.pages[page - 1].images
                )
                if text[marker.end():].strip() or len(boxes) > 1 or has_illustration:
                    explanations[n] = boxes
        found = {n for n, _ in key_rows}
        key_rows.extend((int(n), patch['answer']) for n, patch in (overrides or {}).items()
                        if 'answer' in patch and int(n) not in found)
        _validate_numbers([n for n, _ in key_rows], count, 'Answer key')
        key = dict(key_rows)
        return [(n, boxes, key[n], explanations.get(n, [])) for n, boxes in questions]


def text_in_crop(document, box):
    number, x0, y0, x1, y1 = box
    page = document[number - 1]
    with ExitStack() as stack:
        stack.callback(page.close)
        layer = page.get_textpage()
        stack.callback(layer.close)
        height = page.get_height()
        return layer.get_text_bounded(x0, height - y1, x1, height - y0)


def missing_option_markers(document, boxes):
    text = '\n'.join(text_in_crop(document, box) for box in boxes)
    options = {int(n) for n in re.findall(r'\(\s*([1-4])\s*\)', text)}
    return sorted({1, 2, 3, 4} - options)


def render_crop(document, boxes, *, first_mask=None):
    pieces = []
    for index, (number, x0, top, x1, bottom) in enumerate(boxes):
        if not 1 <= number <= len(document):
            raise ValueError('Crop page is outside the PDF.')
        page = document[number - 1]
        with ExitStack() as stack:
            stack.callback(page.close)
            width, height = page.get_size()
            if not (0 <= x0 < x1 <= width and 0 <= top < bottom <= height):
                raise ValueError('Crop bounds are outside the PDF page.')
            bitmap = page.render(scale=2.2, crop=(x0, height - bottom, width - x1, top))
            stack.callback(bitmap.close)
            image = bitmap.to_pil().convert('RGB')
        if index == 0 and first_mask:
            left, upper, right, lower = first_mask
            ImageDraw.Draw(image).rectangle(
                ((left - x0) * 2.2 - 1, (upper - top) * 2.2 - 2,
                 (right - x0) * 2.2 + 1, (lower - top) * 2.2 + 1),
                fill="white",
            )
        bounds = ImageChops.difference(image, Image.new('RGB', image.size, 'white')).getbbox()
        if bounds:
            pieces.append(image.crop((max(0, bounds[0]-9), max(0, bounds[1]-5),
                                      min(image.width, bounds[2]+9), min(image.height, bounds[3]+5))))
    if not pieces:
        raise ValueError('Crop contains no visible content.')
    result = Image.new('RGB', (max(im.width for im in pieces), sum(im.height+8 for im in pieces)), 'white')
    offset = 4
    for im in pieces:
        result.paste(im, (0, offset))
        offset += im.height + 8
    out = io.BytesIO()
    result.save(out, 'WEBP', quality=90)
    return out.getvalue(), result.width, result.height
