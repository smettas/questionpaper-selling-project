"""Validate a chapter package before writing any records."""
import json
import re
from base64 import b64encode
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import ZipFile

from PIL import Image

from .models import Chapter, Question

LIMIT = 150 * 1024 * 1024


def read_chapter_zip(path):
    if path.stat().st_size > LIMIT:
        raise ValueError("Chapter ZIP exceeds 150 MB. Split it into partial packages.")
    with ZipFile(path) as archive:
        members = archive.infolist()
        names = {item.filename for item in members if not item.is_dir()}
        if (len(members) > 12000 or len({item.filename for item in members}) != len(members)
                or sum(item.file_size for item in members) > 300 * 1024 * 1024):
            raise ValueError("Chapter ZIP has duplicate entries or exceeds package limits.")
        for item in members:
            name = item.filename
            if name.startswith("/") or "\\" in name or ":" in name or ".." in PurePosixPath(name).parts:
                raise ValueError("Invalid ZIP path.")

        def get(name, suffix, max_bytes):
            if not isinstance(name, str) or name not in names or not name.endswith(suffix):
                raise ValueError(f"Missing or invalid file: {name}")
            if archive.getinfo(name).file_size > max_bytes:
                raise ValueError(f"File too large: {name}")
            return archive.read(name)

        def text(value, max_length):
            if not isinstance(value, str) or not value.strip() or len(value) > max_length:
                raise ValueError("Missing or invalid text in manifest or question data.")
            return value.strip()

        manifest = json.loads(get("manifest.json", ".json", 2_000_000))
        if (manifest["schema_version"] != 1 or manifest["subject"] not in Chapter.Subject.values
                or manifest["level"] not in (11, 12) or type(manifest["complete"]) is not bool
                or not isinstance(manifest["parts"], list) or not manifest["parts"]):
            raise ValueError("Invalid manifest version, subject, class, or parts.")
        text(manifest["chapter"], 150)
        ids, fingerprints, parts, used_paths = set(), set(), set(), set()
        records = []
        for part in manifest["parts"]:
            topic = text(part["subtopic"], 150)
            difficulty, count = part["difficulty"], part["count"]
            if (difficulty not in Question.Difficulty.values or type(count) is not int or not 1 <= count <= 250
                    or type(part["part"]) is not int or part["part"] < 1):
                raise ValueError("Invalid difficulty, part number or count.")
            key = (" ".join(topic.split()).casefold(), difficulty, part["part"])
            if key in parts:
                raise ValueError(f"Duplicate part: {key}")
            parts.add(key)
            for field in ("questions_docx", "answers_docx", "data_json"):
                if part[field] in used_paths:
                    raise ValueError(f"File listed twice: {part[field]}")
                used_paths.add(part[field])
            word_answers = []
            for field in ("questions_docx", "answers_docx"):
                with ZipFile(BytesIO(get(part[field], ".docx", 30 * 1024 * 1024))) as word:
                    if word.getinfo("word/document.xml").file_size > 15 * 1024 * 1024:
                        raise ValueError("Word document XML exceeds size limit.")
                    root = ElementTree.fromstring(word.read("word/document.xml"))
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                    paragraphs = ["".join(node.text or "" for node in p.findall(".//w:t", ns)).strip()
                                  for p in root.findall(".//w:p", ns)]
                    pattern = r"^(\d+)\.\s*Ans\s*\(([1-4])\)" if field == "answers_docx" else r"^(\d+)\."
                    matches = [match for para in paragraphs if (match := re.match(pattern, para, re.I))]
                    if [int(match[1]) for match in matches] != list(range(1, count + 1)):
                        raise ValueError(f"Word numbering does not match manifest: {part[field]}")
                    if field == "answers_docx":
                        if "Hints and Solutions" not in paragraphs:
                            raise ValueError(f"Missing Hints and Solutions heading: {part[field]}")
                        word_answers = [int(match[2]) for match in matches]

            data = json.loads(get(part["data_json"], ".json", 3_000_000))
            if not isinstance(data, list) or len(data) != count:
                raise ValueError(f"JSON count does not match manifest: {key}")
            for number, entry in enumerate(data, 1):
                uid = text(entry["id"], 120)
                if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", uid) or uid in ids or entry["number"] != number:
                    raise ValueError(f"Duplicate ID or invalid numbering: {uid}")
                ids.add(uid)
                stem, hint = text(entry["stem"], 5000), text(entry["hint"], 8000)
                options = entry["options"]
                answer = entry["correct_option"]
                if not isinstance(options, list) or len(options) != 4 or type(answer) is not int or not 1 <= answer <= 4:
                    raise ValueError(f"Invalid options or answer: {uid}")
                if answer != word_answers[number - 1]:
                    raise ValueError(f"Word answer does not match JSON: {uid}")
                options = [text(option, 2000) for option in options]
                if len({" ".join(option.split()).casefold() for option in options}) != 4:
                    raise ValueError(f"Repeated option: {uid}")
                fingerprint = (" ".join(stem.split()).casefold(),
                               tuple(sorted(" ".join(option.split()).casefold() for option in options)))
                if fingerprint in fingerprints:
                    raise ValueError(f"Repeated question: {uid}")
                fingerprints.add(fingerprint)
                assets = entry["assets"]
                if not isinstance(assets, list) or len(assets) > 4:
                    raise ValueError(f"Too many assets: {uid}")
                diagrams = []
                for asset in assets:
                    if asset["placement"] not in ("question", "hint"):
                        raise ValueError(f"Invalid diagram placement: {uid}")
                    raw = get(asset["path"], ".png", 1_000_000)
                    with Image.open(BytesIO(raw)) as image:
                        if image.format != "PNG" or max(image.size) > 3000:
                            raise ValueError(f"Invalid diagram: {uid}")
                        image.verify()
                    diagrams.append({"placement": asset["placement"], "png": b64encode(raw).decode("ascii")})
                records.append((uid, topic, difficulty, answer,
                                {"stem": stem, "options": options, "hint": hint, "diagrams": diagrams}))
        if len(records) > 20000:
            raise ValueError("Use partial ZIPs of at most 20,000 questions.")
        return manifest, records
