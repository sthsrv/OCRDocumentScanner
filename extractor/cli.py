"""Command line entry point."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .pipeline import MIN_TEXT_CHARS, convert_pdf


def result_folder(pdf: Path, root: Path) -> Path:
    """<root>/<pdf name>_<date the PDF file was created>, e.g. outputs/report_2026-11-04."""
    stat = pdf.stat()
    created = getattr(stat, "st_birthtime", stat.st_mtime)  # macOS records a creation time; elsewhere use the modified time
    return root / f"{pdf.stem}_{datetime.fromtimestamp(created):%Y-%m-%d}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract the Findings section of a report PDF into JSON and Markdown.")
    parser.add_argument("pdf", type=Path, help="PDF file to convert")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("outputs"),
                        help="parent folder; each PDF gets its own subfolder inside it")
    parser.add_argument("--format", choices=("md", "json", "both"), default="both")
    parser.add_argument("--min-text-chars", type=int, default=MIN_TEXT_CHARS,
                        help="pages with fewer characters than this are OCR'd")
    args = parser.parse_args(argv)
    formats = ("md", "json") if args.format == "both" else (args.format,)
    try:
        outputs = convert_pdf(args.pdf, result_folder(args.pdf, args.output_dir), formats, min_chars=args.min_text_chars)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for kind, path in outputs.items():
        print(f"Created {kind.upper()}: {path}")
    return 0
