"""Turn a PDF page into positioned lines, from its text layer or from OCR."""
from __future__ import annotations

import re
import sys

import numpy as np
import pymupdf

from . import pictures
from .models import Line, Page

ZOOM = 3  # OCR render scale; small red headings are misread at 2, lower it only if OCR is too slow


def load_page(page, ocr, min_chars: int) -> Page:
    number, height = page.number + 1, page.rect.height
    if len(re.sub(r"\s", "", page.get_text("text"))) >= min_chars:
        raw, pics = list(_text_lines(page)), pictures.embedded(page)
    else:
        raw, pics = _ocr_lines(page, ocr), pictures.scanned(page)
    pics = [p for p in pics if not (p[3] < 0.1 * height or p[1] > 0.9 * height)]  # header/footer logos
    # Whatever the screenshot contains must not reach the output, so its text is dropped here.
    lines = [Line(t, *b, page=number) for t, b in raw if not any(_inside(b, p) for p in pics)]
    lines += [Line("", *p, page=number, picture=True) for p in pics]
    return Page(number, page.rect.width, height, _reading_order(lines))


def _text_lines(page):
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                yield text, tuple(line["bbox"])


def _ocr_lines(page, ocr):
    print(f"OCR page {page.number + 1}...", file=sys.stderr)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(ZOOM, ZOOM), alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return [(text, tuple(v / ZOOM for v in box)) for text, box in ocr.read(image)]


def _inside(box, rect) -> bool:
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]


def _reading_order(lines: list[Line]) -> list[Line]:
    """Top to bottom, and left to right within a visual row (title and severity share one)."""
    rows: list[list] = []  # [centre_y, [lines]]
    for line in sorted(lines, key=lambda l: l.y0):
        centre = (line.y0 + line.y1) / 2
        if rows and abs(centre - rows[-1][0]) < (line.y1 - line.y0) / 2:
            rows[-1][1].append(line)
        else:
            rows.append([centre, [line]])
    return [l for _, row in rows for l in sorted(row, key=lambda l: l.x0)]
