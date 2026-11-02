# OCR Document Scanner

Convert a PDF into Markdown and/or JSON. Pages with selectable text are extracted directly with PyMuPDF. Pages with little or no selectable text are rendered and passed to PaddleOCR. Embedded raster images are saved under `images/` and referenced by the outputs.

## Requirements

Use **Python 3.12** for the local macOS setup. The default Python on this machine is 3.15, which may not have compatible PaddlePaddle wheels yet. Use a project-local virtual environment:

```bash
cd /Users/sauravshrestha/Documents/OCRDocumentScanner
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PaddleOCR downloads model files the first time a scanned page needs OCR. Selectable-text PDFs do not initialize OCR.

## Run

```bash
source .venv/bin/activate
python reader.py /path/to/document.pdf
```

By default, this creates `output/document.md`, `output/document.json`, and any extracted images under `output/images/`.

```bash
python reader.py document.pdf --format md
python reader.py document.pdf --format json --output-dir results
python reader.py document.pdf --min-text-chars 40
```

JSON includes the source filename and a page array containing page number, extraction method (`text` or `ocr`), text, and relative image paths. Markdown is organized by page. Mixed PDFs can use direct extraction on some pages and OCR on others.

## Current scope

This is a local command-line conversion tool, not yet a hosted web reader or enterprise service. Table structure and text flow are best-effort; inspect outputs on representative documents before treating them as authoritative.
