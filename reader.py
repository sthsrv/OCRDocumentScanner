"""Extract selectable text and scanned text from PDF files."""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from typing import Any
try:
    import pymupdf
except ImportError:
    import fitz as pymupdf
MIN_TEXT_CHARS = 20

def _normalise_ocr_result(result: Any) -> list[str]:
    """Extract recognized strings from PaddleOCR 2.x or 3.x output."""
    texts: list[str] = []
    if hasattr(result, "json"): result = result.json
    if callable(result): result = result()
    if isinstance(result, dict):
        result = result.get("res", result)
        if isinstance(result, dict):
            for key in ("rec_texts", "texts", "text"):
                value = result.get(key)
                if isinstance(value, list): return [str(x) for x in value if str(x).strip()]
                if isinstance(value, str) and value.strip(): return [value]
    if isinstance(result, (list, tuple)):
        for item in result:
            if hasattr(item, "json") or isinstance(item, dict):
                texts.extend(_normalise_ocr_result(item))
            elif isinstance(item, (list, tuple)):
                if len(item) >= 2 and isinstance(item[1], (list, tuple)) and item[1]: texts.append(str(item[1][0]))
                else: texts.extend(_normalise_ocr_result(item))
    return [text.strip() for text in texts if text.strip()]

class PaddlePageOCR:
    """Lazy adapter for PaddleOCR inference."""
    def __init__(self) -> None:
        try: from paddleocr import PaddleOCR
        except ImportError as exc: raise RuntimeError("PaddleOCR is not installed. Follow README.md setup steps.") from exc
        try: self.engine = PaddleOCR()
        except Exception as exc: raise RuntimeError(f"Could not initialize PaddleOCR: {exc}") from exc
    def read(self, page: Any) -> list[str]:
        import numpy as np
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if hasattr(self.engine, "predict"): result = self.engine.predict(image)
        else:
            try: result = self.engine.ocr(image, cls=True)
            except TypeError: result = self.engine.ocr(image)
        return _normalise_ocr_result(result)

def _save_page_images(document: Any, page: Any, page_number: int, image_dir: Path) -> list[str]:
    paths, seen = [], set()
    for image_index, info in enumerate(page.get_images(full=True), start=1):
        xref = info[0]
        if xref in seen: continue
        seen.add(xref)
        try:
            image = document.extract_image(xref)
            ext = re.sub(r"[^a-zA-Z0-9]", "", image.get("ext", "png")) or "png"
            filename = f"page-{page_number:04d}-image-{image_index:02d}.{ext}"
            image_dir.mkdir(parents=True, exist_ok=True)
            (image_dir / filename).write_bytes(image["image"])
            paths.append(f"images/{filename}")
        except (KeyError, RuntimeError, ValueError): continue
    return paths

def convert_pdf(input_path: Path, output_dir: Path, formats: tuple[str, ...] = ("md", "json"), min_text_chars: int = MIN_TEXT_CHARS) -> dict[str, Path]:
    """Convert a PDF; invoke OCR only for pages with little selectable text."""
    if not input_path.is_file(): raise FileNotFoundError(f"Input file does not exist: {input_path}")
    if input_path.suffix.lower() != ".pdf": raise ValueError("Input must be a .pdf file")
    output_dir.mkdir(parents=True, exist_ok=True)
    pages, ocr = [], None
    with pymupdf.open(input_path) as document:
        if document.is_encrypted and not document.authenticate(""): raise ValueError("This PDF is password-protected; unlock it before processing.")
        for index, page in enumerate(document, start=1):
            text, method = page.get_text("text").strip(), "text"
            if len(re.sub(r"\s", "", text)) < min_text_chars:
                if ocr is None: ocr = PaddlePageOCR()
                text, method = "\n".join(ocr.read(page)), "ocr"
            images = _save_page_images(document, page, index, output_dir / "images")
            pages.append({"page": index, "method": method, "text": text, "images": images})
    stem, outputs = input_path.stem, {}
    if "json" in formats:
        path = output_dir / f"{stem}.json"
        path.write_text(json.dumps({"source": input_path.name, "page_count": len(pages), "pages": pages}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs["json"] = path
    if "md" in formats:
        path, chunks = output_dir / f"{stem}.md", [f"# {stem}\n"]
        for item in pages:
            chunks.append(f"\n## Page {item['page']}\n")
            chunks.append(f"\n{item['text']}\n" if item["text"] else "\n_(No text could be recognized on this page.)_\n")
            chunks.extend(f"\n![Image from page {item['page']}]({image})\n" for image in item["images"])
        path.write_text("\n".join(chunks).rstrip() + "\n", encoding="utf-8")
        outputs["md"] = path
    return outputs

def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PDF text and OCR scanned pages into Markdown and/or JSON.")
    parser.add_argument("pdf", type=Path, help="PDF file to convert")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("output"), help="Output folder (default: ./output)")
    parser.add_argument("--format", choices=("md", "json", "both"), default="both")
    parser.add_argument("--min-text-chars", type=int, default=MIN_TEXT_CHARS, help="OCR pages with fewer non-whitespace text characters")
    args = parser.parse_args()
    if args.min_text_chars < 0: parser.error("--min-text-chars must be zero or greater")
    formats = ("md", "json") if args.format == "both" else (args.format,)
    try: outputs = convert_pdf(args.pdf, args.output_dir, formats, args.min_text_chars)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr); return 1
    for kind, path in outputs.items(): print(f"Created {kind.upper()}: {path}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
