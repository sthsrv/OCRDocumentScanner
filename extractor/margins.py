"""Remove running headers and footers."""
from __future__ import annotations

import math
import re
from collections import Counter

from .models import Line, Page

HEADER = 0.07  # a line ending above this share of the page height is in the header band
FOOTER = 0.90  # a line starting below this share is in the footer band
BOILERPLATE = re.compile(r"powered\s*by.*|confidential|page\s*\d+(\s*of\s*\d+)?|\d{1,3}|(19|20)\d\d", re.I)


def _in_band(line: Line, page: Page) -> bool:
    return line.y1 < HEADER * page.height or line.y0 > FOOTER * page.height


def _key(line: Line) -> str:
    return re.sub(r"\W+", "", line.text).casefold()  # OCR spacing differs page to page


def strip_margins(pages: list[Page]) -> None:
    """Drop band lines that repeat on many pages or are footer boilerplate (page numbers included)."""
    counts = Counter(k for p in pages for k in {_key(l) for l in p.lines if not l.picture and _in_band(l, p)})
    need = max(3, math.ceil(len(pages) * 0.25))
    for page in pages:
        page.lines = [
            l for l in page.lines
            if l.picture or not _in_band(l, page)
            or not (counts[_key(l)] >= need or BOILERPLATE.fullmatch(l.text.strip()))
        ]
