"""Command line entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import MIN_TEXT_CHARS, convert_pdf


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract the Findings section of a report PDF into JSON and Markdown.")
    parser.add_argument("pdf", type=Path, help="PDF file to convert")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--format", choices=("md", "json", "both"), default="both")
    parser.add_argument("--min-text-chars", type=int, default=MIN_TEXT_CHARS,
                        help="pages with fewer characters than this are OCR'd")
    args = parser.parse_args(argv)
    formats = ("md", "json") if args.format == "both" else (args.format,)
    try:
        outputs = convert_pdf(args.pdf, args.output_dir, formats, min_chars=args.min_text_chars)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    for kind, path in outputs.items():
        print(f"Created {kind.upper()}: {path}")
    return 0
