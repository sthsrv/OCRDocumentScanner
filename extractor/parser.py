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


END_NORM = {_norm(heading) for heading in END}


def _is_meta(text: str) -> bool:
    """A 'Vulnerability Type' label or a CVSS vector: what every finding opens with."""
    m = INLINE.match(text) or BARE.match(text)
    return bool(CVSS.match(text) or (m and label_key(m[1]) == "vulnerability_type"))


def locate(lines: list[Line]) -> tuple[int | None, int | None]:
    """Slice of `lines` between the 'Findings' heading and Conclusion/Appendix.

    start is None until the heading is seen, end is None until a closing heading follows.
    The heading must be followed by a finding (a title bar or its metadata), so a
    table-of-contents entry is skipped.
    """
    start = next((i + 1 for i, l in enumerate(lines)
                  if _norm(l.text) == "findings"
                  and any(_is_meta(x.text) or SEVERITY.match(x.text) for x in lines[i + 1:i + 13])), None)
    if start is None:
        return None, None
    return start, next((i for i in range(start, len(lines)) if _norm(lines[i].text) in END_NORM), None)


def _is_field(text: str) -> bool:
    """A heading, a 'Label: value' line, or a bare CVSS vector / status / port."""
    return bool(BARE.match(text) or INLINE.match(text) or CVSS.match(text)
                or any(p.match(text) for p in VALUE.values()))


def _near(a: Line, b: Line) -> bool:
    """b follows a closely enough to be the same block of text, such as a title wrapped over two lines."""
    return (a.page == b.page and not (a.picture or b.picture)
            and not (_is_field(a.text) or _is_field(b.text)) and b.y0 - a.y1 < b.y1 - b.y0)


def _continues(lines: list[Line], i: int) -> bool:
    """The line after lines[i] opens the next page and is plain text: where a split bar's title would be."""
    nxt = lines[i + 1] if i + 1 < len(lines) else None
    return bool(nxt) and nxt.page != lines[i].page and not nxt.picture and not BARE.match(nxt.text)


def _title_bars(lines: list[Line]) -> dict[int, tuple[str | None, int]]:
    """Title bars: {first line index: (title, last line index)}.

    The title has no label; it is the text of the bar that holds a severity box ("Informational
    (0.0)", "5.3 (Medium)"). A long title wraps, so the bar is the severity line plus the lines
    next to it. A severity box on its own line is enough; one sharing a line with other text
    must be followed by the metadata, so a stray "Risk: High (7.5)" in the text is not a bar.
    """
    bars: dict[int, tuple[str | None, int]] = {}
    for i, line in enumerate(lines):
        m = SEVERITY.match(line.text)
        if not m or (m["title"].strip() and not any(_is_meta(x.text) for x in lines[i + 1:i + 5])):
            continue
        first, last = i, i
        while first and _near(lines[first - 1], lines[first]):
            first -= 1
        while last + 1 < len(lines) and _near(lines[last], lines[last + 1]):
            last += 1
        if first == last and not m["title"].strip() and _continues(lines, last):  # a page break split the bar
            last += 1
            while last + 1 < len(lines) and _near(lines[last], lines[last + 1]):
                last += 1
        texts = [(m["title"] if j == i else lines[j].text).strip() for j in range(first, last + 1)]
        bars[first] = (" ".join(t for t in texts if t) or None, last)  # no text: falls back to the vulnerability type
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
