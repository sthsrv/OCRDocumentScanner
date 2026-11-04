# Findings Extractor

Reads a vulnerability-report PDF and writes only what is under its **Findings** heading, as JSON and Markdown. Pages with a text layer are read directly; scanned pages go through PaddleOCR. Findings pages that contain screenshots are saved as PNGs.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

PaddleOCR downloads its models the first time a scanned page needs OCR.

## Run

```bash
python run.py report.pdf                      # -> output/report.json, output/report.md, output/images/
python run.py report.pdf -o results --format json
python -m pytest                              # tests (no OCR or model download needed)
```

OCR is the slow part: pages are OCR'd from page 1 until the Findings heading is found, then through the findings, and it stops at Conclusion/Appendix.

## Output

Each finding has `title` (the unlabeled bar above the metadata; falls back to the vulnerability type), then `vulnerability_type`, `cvss`, `status`, `affected_endpoints`, `scopes`, `description`, `port`, `recommendation`, `reference`, `remarks`, `output` and `image_pages`. Fields can appear in any order in the PDF. `scopes`, `affected_endpoints` and `reference` are lists; `description`, `recommendation` and `remarks` are Markdown; `output` is a fenced code block. A section that has only an image gives an empty value. An `evidence` key appears only when the report has a text Evidence section.

A value whose label is missing is still recognised when its shape is unambiguous: a CVSS vector (`CVSS:3.1/AV:N/...`), a status word (`Resolved`, `Wont Fix`, ...) or a bare port number.

The Markdown file has one `###` title per finding, followed by `Label: value` lines. Header, footer, page headings and anything inside a screenshot are left out of both files. `images/page-NNNN.png` holds each findings page that contains a screenshot, and `image_pages` in the JSON says which finding it belongs to.

## Where to change things

| To change | Edit |
|---|---|
| Labels, status words, value shapes, key order | `extractor/fields.py` |
| How a field is written (Markdown, lists, code blocks) | `extractor/markdown.py` |
| JSON / Markdown layout | `extractor/writers.py` |
| Header and footer bands | `extractor/margins.py` |
| Screenshot detection | `extractor/pictures.py` |
| OCR engine and render scale | `extractor/ocr.py`, `ZOOM` in `extractor/pages.py` |
| Finding boundaries and field assignment | `extractor/parser.py` |

## Limits

- OCR must read the section headings. If one is misread, the lines under it are reported on stderr as `fit no field` instead of landing in the wrong field. Check the pages it names.
- On scanned pages, screenshots are found by their dark or coloured areas. A mostly white, light-themed screenshot may be missed. On text-layer pages embedded images are used, which is exact.
- Header and footer removal assumes they sit in the top 7% and bottom 10% of the page.
- Bullets read by OCR as stray punctuation are cleaned from list fields only.
- A `Port` value must look like a port (`443`, `80, 443`). If the box under the heading was not read, the next line is reported as unplaced instead of being filed as the port.
