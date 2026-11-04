"""Find screenshots on a page. Rects are (x0, y0, x1, y1) in PDF points."""
from __future__ import annotations

import cv2
import numpy as np

MIN_AREA = 0.03  # share of the page; smaller blobs are icons, logos, rules
MAX_ASPECT = 5   # wider or taller blobs are bars and dividers, not screenshots


def _area(rect) -> float:
    return (rect[2] - rect[0]) * (rect[3] - rect[1])


def embedded(page) -> list[tuple]:
    """Placed images on a page that has a text layer."""
    page_area = page.rect.width * page.rect.height
    return [tuple(i["bbox"]) for i in page.get_image_info() if _area(i["bbox"]) >= MIN_AREA * page_area]


def scanned(page) -> list[tuple]:
    """Dark or coloured blobs on a page that is itself a single scanned image.

    shortcut: light-themed screenshots (mostly white UI) are not detected; use a layout
    model such as PaddleOCR's PP-DocLayout if those show up.
    """
    pix = page.get_pixmap(alpha=False)  # 72 dpi: one pixel per point
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    mask = (gray < 200).astype(np.uint8) * 255
    k = max(3, pix.width // 70)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))  # drops thin text strokes
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3 * k, 3 * k), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    found = []
    for x, y, w, h, _ in stats[1:count]:
        if w * h >= MIN_AREA * pix.width * pix.height and max(w / h, h / w) <= MAX_ASPECT:
            top, bottom = _extend(gray, x, y, w, h)
            found.append((x, top, x + w, bottom))
    return found


def _extend(gray, x, y, w, h):
    """Vertical extent of a screenshot, from the faint edge line it has on both sides.

    The dark core of a mostly white screenshot (a cover page, say) is smaller than the
    screenshot itself, and text in the white part would otherwise leak into the output.
    Falls back to the blob when no continuous edge is found.
    """
    ink = gray < 255
    both = ink[:, max(x - 3, 0):x + 3].any(axis=1) & ink[:, x + w - 3:x + w + 3].any(axis=1)
    top = bottom = y + h // 2
    if not both[top]:
        return y, y + h
    while top > 0 and both[top - 1]:
        top -= 1
    while bottom < len(both) - 1 and both[bottom + 1]:
        bottom += 1
    return min(top, y), max(bottom + 1, y + h)
