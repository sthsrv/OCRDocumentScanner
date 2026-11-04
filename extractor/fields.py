"""Vocabulary of the findings pages. Edit this file to support new labels or value shapes."""
from __future__ import annotations

import re

# Heading text as printed in the report -> JSON key.
LABELS = {
    "vulnerability type": "vulnerability_type", "cvss": "cvss", "status": "status",
    "affected endpoints": "affected_endpoints", "affected endpoint": "affected_endpoints",
    "affected system and endpoint": "affected_endpoints",
    "scopes": "scopes", "scope": "scopes", "description": "description", "port": "port",
    "recommendation": "recommendation", "reference": "reference", "references": "reference",
    "remarks": "remarks", "evidence": "evidence", "output": "output",
    "impact": "impact", "steps for reproduction": "steps_for_reproduction",
    "management response": "management_response",
}

# How each key is written: one value, a list, Markdown prose, a fenced code block, or not at all
# ("image": a screenshot section, whose text is never wanted).
KIND = {
    "vulnerability_type": "scalar", "cvss": "scalar", "status": "scalar",
    "affected_endpoints": "list", "scopes": "list",
    "description": "prose", "port": "scalar", "recommendation": "prose",
    "reference": "list", "remarks": "prose", "evidence": "image", "output": "code",
    "impact": "prose", "steps_for_reproduction": "prose", "management_response": "prose",
}
ORDER = list(KIND)  # key order in the JSON and Markdown
# Sections only some reports have: left out of the output when empty.
OPTIONAL = {"evidence", "impact", "steps_for_reproduction", "management_response"}
TITLES = {k: k.replace("_", " ").title() for k in KIND} | {"cvss": "CVSS"}
# Keys whose value sits in the small metadata area, so "Label: value" may share a line.
SHORT = {k for k, v in KIND.items() if v in ("scalar", "list")}
# Values that fit on one line: the field closes after it, so a misread heading cannot leak into them.
ONE_LINE = {"cvss", "status", "port"}

# Labels may lose their spaces in OCR ("VulnerabilityType:"), hence \s* between words.
_ALT = "|".join(r"\s*".join(map(re.escape, w.split())) for w in sorted(LABELS, key=len, reverse=True))
BARE = re.compile(rf"^({_ALT})\s*:?$", re.I)           # a heading alone on its line
INLINE = re.compile(rf"^({_ALT})\s*:\s*(\S.*)$", re.I)  # "Label: value"
_KEY = {re.sub(r"\s+", "", label): key for label, key in LABELS.items()}

# Values recognised without their label, e.g. a bare CVSS vector or a bare "Resolved".
CVSS = re.compile(r"^CVSS\s*:\s*\d(\.\d)?\s*/.+$", re.I)
VALUE = {
    "status": re.compile(
        r"^(new|open|closed|resolved|reopened|re-?verification|in progress|partially resolved"
        r"|won'?t ?fix|accepted|false positive)$", re.I),
    "port": re.compile(r"^\d{1,5}(\s*[,;/-]\s*\d{1,5})*$"),
}
# Keys whose value must match VALUE[key]. If a heading's value box was not read, the next line is
# some other field's text; it is reported as unplaced instead of being filed under this key.
CHECKED = {"port"}

# The title bar: title text and a severity box, written "Informational (0.0)" or "5.3 (Medium)".
_SEV = r"(?:critical|high|medium|low|informational)"
_OPEN, _CLOSE = r"[(\[（]+", r"[)\]）]+"  # OCR sometimes reads the brackets as [ ] or full-width
SEVERITY = re.compile(
    rf"^(?P<title>.*?)\s*(?:{_SEV}\s*{_OPEN}\s*[\w.]*\s*{_CLOSE}|[\d.]+\s*{_OPEN}\s*{_SEV}\s*{_CLOSE})$", re.I)
END = {"conclusion", "appendix", "further recommendations"}  # headings that close the Findings section


def label_key(matched: str) -> str:
    return _KEY[re.sub(r"\s+", "", matched).casefold()]
