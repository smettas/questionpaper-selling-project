"""Convert unambiguous Unicode roots to the shared inline equation format.

This is display-only: stored questions and already-delimited equations stay
unchanged. Balanced operands are parsed instead of guessed with a short regex.
"""
import re

MATH = re.compile(r"(\\\(.*?\\\)|\\\[.*?\\\])", re.S)
ATOM = re.compile(r"(?:\d+(?:\.\d+)?|\.\d+|[A-Za-z\u0370-\u03ff]+)(?:(?:_[A-Za-z0-9]+)|(?:[₀-₉₊₋]+)|(?:[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+)|(?:<(?:sub|sup)>[^<>]+</(?:sub|sup)>))*")
SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")
SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋", "0123456789+-")
PAIRS = {"(": ")", "[": "]", "{": "}"}


def _math_end(text, start):
    close = {r"\(": r"\)", r"\[": r"\]"}.get(text[start:start + 2])
    if close is None:
        return None
    end = text.find(close, start + 2)
    return end + 2 if end >= 0 else None


def _operand(text, start):
    while start < len(text) and text[start] in " \t":
        start += 1
    if start >= len(text):
        return None
    end = _math_end(text, start)
    if end is not None:
        return text[start:end], end
    if text[start] in PAIRS:
        stack = [PAIRS[text[start]]]
        pos = start + 1
        while pos < len(text):
            end = _math_end(text, pos)
            if end is not None:
                pos = end
                continue
            char = text[pos]
            if char in PAIRS:
                stack.append(PAIRS[char])
            elif char in ")]}":
                if char != stack.pop():
                    return None
                if not stack:
                    return text[start + 1:pos], pos + 1
            elif char == "\n":
                return None
            pos += 1
        return None
    match = ATOM.match(text, start)
    if match:
        return match[0], match.end()
    return None


def _plain_latex(text):
    text = re.sub(r"<sub>([^<>]+)</sub>", r"_{\1}", text)
    text = re.sub(r"<sup>([^<>]+)</sup>", r"^{\1}", text)
    text = re.sub(r"[₀-₉₊₋]+", lambda m: "_{" + m[0].translate(SUB) + "}", text)
    text = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+", lambda m: "^{" + m[0].translate(SUPER) + "}", text)
    text = re.sub(r"_([A-Za-z0-9]+)", r"_{\1}", text)
    text = text.replace("−", "-").replace("×", r"\times ").replace("·", r"\cdot ").replace("÷", "/")
    text = text.replace("°", r"^{\circ}").replace("±", r"\pm ")
    text = re.sub(r"\b(sin|cos|tan|log|ln|exp)\b", r"\\\1 ", text)
    return text


def _fraction(text):
    """Stack a single top-level quotient without changing operator precedence."""
    depth = 0
    slash = []
    for pos, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif depth == 0:
            if char in "+-=":
                return text
            if char == "/":
                slash.append(pos)
    if len(slash) == 1:
        pos = slash[0]
        a, b = text[:pos].strip(), text[pos + 1:].strip()
        # A product after '/' is ambiguous in plain text; leave its slash
        # notation intact instead of silently changing the grouping.
        simple_denominator = re.fullmatch(r"(?:[A-Za-z\u0370-\u03ff]+(?:_\{[^{}]+\})?|\d+(?:\.\d+)?)", b)
        if a and simple_denominator and r"\pm" not in text:
            return r"\frac{" + a + "}{" + b + "}"
    return text


def _root_latex(raw, depth):
    if depth > 16 or not raw.strip():
        return None
    # Only source-delimited math may introduce existing LaTeX commands.
    check = MATH.sub("x", raw)
    check = re.sub(r"</?(?:sub|sup)>", "", check)
    word_check = re.sub(r"\b(?:sin|cos|tan|log|ln|exp)\b", "x", check)
    if re.search(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}", word_check):
        return None
    if re.search(r"[^0-9A-Za-z\u0370-\u03ff₀-₉₊₋⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻\s_{}\[\]().+*/^−×·÷±=°√]", check):
        return None
    parts = []
    for part in MATH.split(raw):
        if MATH.fullmatch(part):
            parts.append(part[2:-2])
        else:
            converted = _convert(part, False, depth + 1)
            if "√" in converted:
                return None
            parts.append(_plain_latex(converted))
    return r"\sqrt{" + _fraction("".join(parts).strip()) + "}"


def _convert(text, delimit, depth=0):
    out = []
    pos = 0
    while pos < len(text):
        end = _math_end(text, pos)
        if end is not None:
            out.append(text[pos:end] if delimit else text[pos + 2:end - 2])
            pos = end
            continue
        if text[pos] == "√":
            operand = _operand(text, pos + 1)
            if operand:
                raw, end = operand
                expression = _root_latex(raw, depth)
                if expression:
                    out.append(r"\(" + expression + r"\)" if delimit else expression)
                    pos = end
                    continue
        out.append(text[pos])
        pos += 1
    return "".join(out)


def normalize_math_text(value):
    if "√" not in value:
        return value
    return _convert(value, True)
