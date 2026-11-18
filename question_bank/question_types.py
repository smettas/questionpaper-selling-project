"""Classify the question formats available in existing structured banks."""
import re

QUESTION_TYPES = (
    ("mcq", "Standard MCQs"),
    ("assertion-reason", "Assertion–reason"),
    ("statement", "Statement-based"),
    ("matching", "Match the following"),
    ("diagram", "Diagrams"),
    ("graph", "Graphs"),
)

ASSERTION = re.compile(r"(?im)^\s*(?:Assertion(?:\s*\(A\))?|\(A\))\s*[:–—-]")
REASON = re.compile(r"(?im)^\s*(?:Reason(?:\s*\(R\))?|\(R\))\s*[:–—-]")
MATCHING = re.compile(r"\bmatch(?:ing)?\b|\blist\s*[-–—]?\s*(?:II|2)\b", re.I)
STATEMENT = re.compile(r"\bstatements?\b|\bstatements?\s*[-–—]?\s*(?:I|1)\b", re.I)
GRAPH = re.compile(r"\b(?:graphs?|plots?|curves?)\b", re.I)


def classify_question(content, declared=""):
    stem = content.get("stem", "")
    options = " ".join(content.get("options", ()))
    if declared == "assertion-reason" or (ASSERTION.search(stem) and REASON.search(stem)):
        kind = "assertion-reason"
    elif declared == "matching" or MATCHING.search(stem):
        kind = "matching"
    elif declared == "statement" or STATEMENT.search(stem):
        kind = "statement"
    else:
        kind = "mcq"
    visual = ""
    if any(asset.get("placement") == "question" for asset in content.get("diagrams", ())):
        visual = "graph" if GRAPH.search(f"{stem} {options}") else "diagram"
    return kind, visual
