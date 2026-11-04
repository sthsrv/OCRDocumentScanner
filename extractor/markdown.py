"""Turn the lines of a field into its final value: text, list, Markdown prose or code block."""
from __future__ import annotations

import re
from statistics import median

from .fields import KIND
from .models import Line

GAP = 0.8  # vertical gap, in line heights, that starts a new paragraph
_BULLET = re.compile(r"^[•·●▪‣∙*]\s*")


def _gap(prev: Line, line: Line) -> bool:
    return prev.page == line.page and line.y0 - prev.y1 > GAP * (prev.y1 - prev.y0)


def prose(lines: list[Line], right: float) -> str:
    """Markdown: blank line at paragraph gaps, wrapped lines re-joined, bullets as '- '.

    A line that reaches the right margin (justified text) is taken to wrap onto the next one.
    """
    out: list[str] = []
    prev = None
    for line in lines:
        text = _BULLET.sub("- ", line.text)
        gap = prev is not None and _gap(prev, line)
        if prev is None:
            out.append(text)
        elif prev.x1 >= 0.98 * right and not gap and not text.startswith("- "):
            out[-1] += " " + text
        else:
            out += ["", text] if gap else [text]
        prev = line
    return "\n".join(out)


def code(lines: list[Line]) -> str:
    """Fenced block that keeps line breaks and indentation (estimated from x offsets)."""
    base = min(l.x0 for l in lines)
    char = median((l.x1 - l.x0) / max(len(l.text), 1) for l in lines)
    rows: list[str] = []
    prev = None
    for line in lines:
        if prev is not None and _gap(prev, line):
            rows.append("")
        rows.append(" " * round((line.x0 - base) / char) + line.text)
        prev = line
    return "```\n" + "\n".join(rows) + "\n```"


def render(key: str, blocks: list[list[Line]], right: float):
    blocks = [b for b in blocks if b]
    kind = KIND[key]
    if kind == "image":
        return ""
    if kind == "list":  # OCR reads the bullet glyph as stray punctuation, so strip any leading symbols
        return [t for b in blocks for l in b if (t := re.sub(r"^[\W_]+", "", l.text).strip())]
    if kind == "scalar":
        return " ".join(l.text for b in blocks for l in b)
    return "\n\n".join(code(b) if kind == "code" else prose(b, right) for b in blocks)
