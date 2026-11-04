"""Find the Findings section and split it into findings and their fields."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from .fields import BARE, CHECKED, CVSS, END, INLINE, ONE_LINE, SEVERITY, SHORT, VALUE, label_key
from .models import Line


@dataclass
class Finding:
    title: str | None = None
    blocks: dict[str, list[list[Line]]] = field(default_factory=dict)  # key -> one block per heading seen
    picture_pages: list[int] = field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"[\s:]+", "", text).casefold()


def _is_meta(text: str) -> bool:
    """A 'Vulnerability Type' label or a CVSS vector: what every finding opens with."""
    m = INLINE.match(text) or BARE.match(text)
    return bool(CVSS.match(text) or (m and label_key(m[1]) == "vulnerability_type"))


def locate(lines: list[Line]) -> tuple[int | None, int | None]:
    """Slice of `lines` between the 'Findings' heading and Conclusion/Appendix.

    start is None until the heading is seen, end is None until a closing heading follows.
    The heading must be followed by a finding, so a table-of-contents entry is skipped.
    """
    start = next((i + 1 for i, l in enumerate(lines)
                  if _norm(l.text) == "findings" and any(_is_meta(x.text) for x in lines[i + 1:i + 13])), None)
    if start is None:
        return None, None
    return start, next((i for i in range(start, len(lines)) if _norm(lines[i].text) in END), None)


def _title_bars(lines: list[Line]) -> dict[int, tuple[str | None, int]]:
    """Title bars: {first line index: (title, last line index)}.

    The title has no label; it is the text beside a severity box, right above the metadata.
    """
    bars: dict[int, tuple[str | None, int]] = {}
    for i, line in enumerate(lines):
        m = SEVERITY.match(line.text)
        if not m or not any(_is_meta(x.text) for x in lines[i + 1:i + 5]):
            continue
        prev = lines[i - 1] if i else None
        if m["title"].strip():
            bars[i] = (m["title"].strip(), i)
        elif prev and not prev.picture and abs(prev.y0 - line.y0) < line.y1 - line.y0:
            bars[i - 1] = (prev.text, i)
        else:
            bars[i] = (None, i)  # no title text found: falls back to the vulnerability type
    return bars


def _classify(line: Line, cur: Finding | None, key: str | None) -> tuple[str | None, Line | None]:
    """(key opened by this line, value line). (None, line) means plain content of the open field."""
    text = line.text
    if m := BARE.match(text):
        return label_key(m[1]), None
    seen = cur.blocks if cur else {}
    meta = key is None or key in SHORT  # not inside a prose or output block
    if meta:
        if "cvss" not in seen and CVSS.match(text):
            return "cvss", line
        for name, pattern in VALUE.items():
            if name not in seen and pattern.match(text):
                return name, line
    # Inside an Output box "Port: 0" is content, so only the finding marker is accepted there.
    if (m := INLINE.match(text)) and (meta or label_key(m[1]) == "vulnerability_type"):
        return label_key(m[1]), replace(line, text=m[2])
    return None, line


def parse_findings(lines: list[Line]) -> tuple[list[Finding], list[Line]]:
    """Findings, plus the lines that fit no field (usually a heading the OCR misread)."""
    bars = _title_bars(lines)
    consumed = {j for first, (_, last) in bars.items() for j in range(first, last + 1)}
    findings: list[Finding] = []
    dropped: list[Line] = []
    cur: Finding | None = None
    key: str | None = None
    for i, line in enumerate(lines):
        if i in bars:
            cur, key = Finding(title=bars[i][0]), None
            findings.append(cur)
            continue
        if i in consumed:
            continue
        if line.picture:
            if cur and line.page not in cur.picture_pages:
                cur.picture_pages.append(line.page)
            continue
        opened, value = _classify(line, cur, key)
        if opened:
            if opened == "vulnerability_type" and (cur is None or "vulnerability_type" in cur.blocks):
                cur = Finding()  # a finding without a title bar
                findings.append(cur)
            if cur is None:
                continue
            cur.blocks.setdefault(opened, []).append([])
            key = opened
        if value and key in CHECKED and not VALUE[key].match(value.text.strip()):
            key = None
        if value and cur and key:
            cur.blocks[key][-1].append(value)
            if key in ONE_LINE:
                key = None
        elif value and cur:
            dropped.append(value)
    return findings, dropped
