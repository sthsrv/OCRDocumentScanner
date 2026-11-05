"""Find screenshots on a page. Rects are (x0, y0, x1, y1) in PDF points."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pymupdf

from .models import Line

MIN_AREA = 0.03  # share of the page; smaller blobs are icons, logos, rules
MAX_ASPECT = 5   # wider or taller blobs are bars and dividers, not screenshots ...
DARK = 80        # ... unless they are this dark (mean grey, 0 black to 255 white): a terminal capture, not a coloured title bar
CROP_PAD = 4     # points of margin around a crop, so a few pixels of detection error do not cut the picture
CROP_ZOOM = 2    # render scale of a crop


def _area(rect) -> float:
    return (rect[2] - rect[0]) * (rect[3] - rect[1])


def embedded(page) -> list[tuple]:
    """Placed images on a page that has a text layer."""
    page_area = page.rect.width * page.rect.height
    return [tuple(i["bbox"]) for i in page.get_image_info() if _area(i["bbox"]) >= MIN_AREA * page_area]


def scanned(page) -> list[tuple]:
    """Find screenshot regions on a page that is itself a single scanned image.

    Dark screenshots are found from connected dark/coloured areas.  A second, lighter
    pass uses the fine edges and text inside a light UI; this is deliberately more
    conservative than the dark pass because ordinary page text also produces edges.
    """
    pix = page.get_pixmap(alpha=False)  # 72 dpi: one pixel per point
    rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    found = _dark_candidates(gray)
    found += _light_candidates(gray, found)
    return found


def _valid_candidate(gray, x, y, w, h) -> bool:
    page_h, page_w = gray.shape
    if w * h < MIN_AREA * page_w * page_h:
        return False
    if max(w / h, h / w) > MAX_ASPECT and gray[y:y + h, x:x + w].mean() >= DARK:
        return False
    # The scanned page itself is not a screenshot.  Leave a small margin for a
    # screenshot that touches one side, while rejecting the page-sized contour.
    return w < page_w * 0.97 or h < page_h * 0.97


def _dark_candidates(gray):
    mask = (gray < 200).astype(np.uint8) * 255
    k = max(3, gray.shape[1] // 70)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3 * k, 3 * k), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    found = []
    for x, y, w, h, _ in stats[1:count]:
        if not _valid_candidate(gray, x, y, w, h):
            continue
        top, bottom = _extend(gray, x, y, w, h)
        found.append((x, top, x + w, bottom))
    return found


def _light_candidates(gray, existing):
    """Find mostly-white screenshots from their border and UI/text edges."""
    edges = cv2.Canny(gray, 30, 100)
    k = max(5, gray.shape[1] // 100)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not _valid_candidate(gray, x, y, w, h):
            continue
        # A screenshot has substantially more edge detail than a plain page area.
        density = cv2.countNonZero(edges[y:y + h, x:x + w]) / (w * h)
        if density < 0.012:
            continue
        rect = (x, y, x + w, y + h)
        if any(_overlap(rect, old) > 0.5 for old in existing + candidates):
            continue
        candidates.append(rect)
    return candidates


def _overlap(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    return intersection / min(_area(a), _area(b))


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


def save_crops(doc, pictures: list[Line], image_dir: Path) -> dict[int, list[str]]:
    """Cut each picture out of its page and save it as a PNG.

    Returns {page number: file names relative to the output folder}, top to bottom. A page with
    one picture gives page-0022.png, a page with several gives page-0022-1.png, page-0022-2.png.
    """
    for old in image_dir.glob("page-*.png"):  # leftovers from an earlier run
        old.unlink()
    saved: dict[int, list[str]] = {}
    for number in sorted({p.page for p in pictures}):
        page = doc[number - 1]
        found = sorted((p for p in pictures if p.page == number), key=lambda p: (p.y0, p.x0))
        for index, pic in enumerate(found, start=1):
            box = pymupdf.Rect(float(pic.x0), float(pic.y0), float(pic.x1), float(pic.y1))
            clip = (box + (-CROP_PAD, -CROP_PAD, CROP_PAD, CROP_PAD)) & page.rect
            name = f"page-{number:04d}{f'-{index}' if len(found) > 1 else ''}.png"
            image_dir.mkdir(exist_ok=True)
            page.get_pixmap(matrix=pymupdf.Matrix(CROP_ZOOM, CROP_ZOOM), clip=clip, alpha=False).save(image_dir / name)
            saved.setdefault(number, []).append(f"{image_dir.name}/{name}")
    return saved
