"""Conservative offline diagnostics. No model writes and no generic answer oracle."""
import html
import re
import unicodedata

VERSION = '1.0'

def plain(value):
    s = html.unescape(str(value or ''))
    s = re.sub(r'<[^>]+>', '', s)
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'\s+', ' ', s).strip()

def inspect_record(content, key):
    findings = []
    def flag(code, severity, reason):
        findings.append((code, severity, reason))
    if not isinstance(content, dict) or not content:
        flag('IMAGE_OR_EMPTY_RECORD', 'not_checked', 'No structured text; requires image review.')
        return findings
    stem, hint = plain(content.get('stem')), plain(content.get('hint'))
    options = content.get('options')
    if not stem:
        flag('EMPTY_STEM', 'error', 'Structured stem is empty.')
    if type(key) is not int or key not in range(1,5):
        flag('INVALID_KEY', 'error', 'Key must be 1–4.')
    if not isinstance(options, list) or len(options) != 4:
        flag('OPTION_COUNT', 'error', 'Expected four text options.')
    else:
        normalized = [plain(x).casefold() for x in options]
        if any(not x for x in normalized):
            flag('EMPTY_OPTION', 'error', 'At least one option is empty.')
        if len(set(normalized)) != 4:
            flag('DUPLICATE_OPTIONS', 'error', 'Options collide after text normalization.')
    raw = ' '.join(str(content.get(x,'')) for x in ('stem','hint','options'))
    if re.search(r'<\s*/?\s*(?:sup|sub)\b', raw, re.I):
        flag('HTML_SCRIPT_MARKUP', 'review', 'Check whether HTML superscript/subscript markup renders correctly.')
    diagrams = content.get('diagrams', [])
    if not isinstance(diagrams,list):
        flag('DIAGRAM_METADATA', 'error', 'Diagram metadata is not a list.')
        diagrams = []
    if re.search(r'\b(?:shown in (?:the )?(?:figure|diagram)|see the figure|structures shown in the figure)\b',stem,re.I):
        if not any(isinstance(x,dict) and x.get('placement') == 'question' for x in diagrams):
            flag('POSSIBLE_MISSING_FIGURE', 'review', 'Stem refers to a figure but has no question diagram metadata.')
    # This explanation embodies the faulty rule observed in the supplied paper.
    if re.search(r'ionisation isomerism needs', hint, re.I) and re.search(r'Br.*I',hint) and re.search(r'absent',hint,re.I):
        flag('RESTRICTED_IONISATION_RULE', 'review', 'Explanation may wrongly restrict exchangeable anionic ligands to bromide/iodide. Nitrite and other anions can also exchange; independently review stem and key.')
    if re.search(r'one formula unit.*gives 1 ion in water',stem,re.I):
        flag('ONE_ION_ASSERTION', 'review', 'Check charge and counterions. A neutral intact complex gives zero ions; do not count one molecule as one ion. Assertion may intentionally be false: verify keyed logic.')
    # Never label a record scientifically verified merely because no rule fired.
    return findings
