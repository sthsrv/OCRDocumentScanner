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
from .pictures import save_crops
from .writers import finding_dict, write_json, write_markdown

MIN_TEXT_CHARS = 20  # fewer characters than this on a page means it is scanned and needs OCR


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
        missed = sorted({l.page for f in findings for b in f.blocks.get("evidence", []) for l in b})
        if missed:  # a detected screenshot takes its own text with it, so text left here means it was not detected
            print(f"Warning: Evidence text on page(s) {missed} was left out, but no screenshot was found "
                  "there, so nothing was cropped; check those pages.", file=sys.stderr)
        right = max((l.x1 for l in section if not l.picture), default=0)
        out_dir.mkdir(parents=True, exist_ok=True)
        wanted = {n for f in findings for n in f.picture_pages}
        crops = save_crops(doc, [l for l in section if l.picture and l.page in wanted], out_dir / "images")
    items = [finding_dict(f, right) for f in findings]
    for item, f in zip(items, findings):  # file names of the crops, not the whole-page names writers.py builds
        item["image_pages"] = [name for n in f.picture_pages for name in crops[n]]
    outputs = {}
    if "json" in formats:
        outputs["json"] = out_dir / f"{pdf.stem}.json"
        write_json(items, outputs["json"])
    if "md" in formats:
        outputs["md"] = out_dir / f"{pdf.stem}.md"
        write_markdown(items, outputs["md"])
    return outputs
