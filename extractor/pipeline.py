"""PDF in, findings.json / findings.md / images/ out."""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

from .margins import strip_margins
from .models import Line, Page
from .ocr import PaddleReader
from .pages import load_page
from .parser import locate, parse_findings
from .writers import finding_dict, image_name, write_json, write_markdown

MIN_TEXT_CHARS = 20  # fewer characters than this on a page means it is scanned and needs OCR
IMAGE_ZOOM = 1.5


def _flat(pages: list[Page]) -> list[Line]:
    return [l for p in pages for l in p.lines]


def convert_pdf(pdf: Path, out_dir: Path, formats=("md", "json"), ocr=None, min_chars: int = MIN_TEXT_CHARS):
    if not pdf.is_file():
        raise FileNotFoundError(f"Input file does not exist: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise ValueError("Input must be a .pdf file")
    ocr = ocr or PaddleReader()
    pages: list[Page] = []
    with pymupdf.open(pdf) as doc:
        if doc.is_encrypted and not doc.authenticate(""):
            raise ValueError("This PDF is password-protected; unlock it before processing.")
        for page in doc:
            pages.append(load_page(page, ocr, min_chars))
            if locate(_flat(pages))[1] is not None:  # Conclusion reached: later pages are not needed
                break
        strip_margins(pages)
        lines = _flat(pages)
        start, end = locate(lines)
        if start is None:
            raise ValueError("No 'Findings' section found in this PDF")
        section = lines[start:end]
        findings, dropped = parse_findings(section)
        if dropped:
            where = sorted({l.page for l in dropped})
            print(f"Warning: {len(dropped)} line(s) on page(s) {where} fit no field, so they were left out; "
                  "a heading was probably misread by OCR.", file=sys.stderr)
        right = max((l.x1 for l in section if not l.picture), default=0)
        out_dir.mkdir(parents=True, exist_ok=True)
        _save_image_pages(doc, sorted({n for f in findings for n in f.picture_pages}), out_dir)
    items = [finding_dict(f, right) for f in findings]
    outputs = {}
    if "json" in formats:
        outputs["json"] = out_dir / f"{pdf.stem}.json"
        write_json(items, outputs["json"])
    if "md" in formats:
        outputs["md"] = out_dir / f"{pdf.stem}.md"
        write_markdown(items, outputs["md"])
    return outputs


def _save_image_pages(doc, numbers: list[int], out_dir: Path) -> None:
    """Whole-page PNGs of the findings pages that hold screenshots."""
    image_dir = out_dir / "images"
    for old in image_dir.glob("page-*.png"):  # leftovers from an earlier run
        old.unlink()
    for n in numbers:
        image_dir.mkdir(exist_ok=True)
        doc[n - 1].get_pixmap(matrix=pymupdf.Matrix(IMAGE_ZOOM, IMAGE_ZOOM), alpha=False).save(
            out_dir / image_name(n)
        )
