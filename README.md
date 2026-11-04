# Findings Extractor

Reads a vulnerability-report PDF and writes only what is under its **Findings** heading, as JSON and Markdown. Pages with a text layer are read directly; scanned pages go through PaddleOCR. Screenshots on findings pages are cropped out and saved as PNGs.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

PaddleOCR downloads its models the first time a scanned page needs OCR.

## Run

```bash
python run.py report.pdf                      # -> outputs/report_2026-11-04/report.json, report.md, images/
python run.py report.pdf -o results --format json
python -m pytest                              # tests (no OCR or model download needed)
```

Results go in their own folder, `outputs/<pdf name>_<YYYY-MM-DD>/`. The date is when the PDF file was created (macOS keeps a creation time; on other systems it is the modified time). `-o` changes the parent folder (`outputs`).

OCR is the slow part: pages are OCR'd from page 1 until the Findings heading is found, then through the findings, and it stops at Conclusion, Appendix or Further Recommendations.

## Output

Each finding has `title` (the unlabeled coloured bar that holds a severity box, written `Informational (0.0)` or `5.3 (Medium)`; it may wrap over two lines or be split by a page break; falls back to the vulnerability type), then `vulnerability_type`, `cvss`, `status`, `affected_endpoints`, `scopes`, `description`, `port`, `recommendation`, `reference`, `remarks`, `output` and `image_pages`. Fields can appear in any order in the PDF. `scopes`, `affected_endpoints` and `reference` are lists; `description`, `recommendation` and `remarks` are Markdown; `output` is a fenced code block. A section that has only an image gives an empty value.

Three more sections are written only when a report has them: `impact`, `steps_for_reproduction` and `management_response`. "Affected System and Endpoint" is read as `affected_endpoints`. An Evidence section holds screenshots, so its text is never written.

A value whose label is missing is still recognised when its shape is unambiguous: a CVSS vector (`CVSS:3.1/AV:N/...`), a status word (`Resolved`, `Wont Fix`, ...) or a bare port number.

The Markdown file has one `###` title per finding, followed by `Label: value` lines. Header, footer, page headings and anything inside a screenshot are left out of both files. Each screenshot on a findings page is cropped out of the page and saved as `images/page-NNNN.png` (`page-NNNN-1.png`, `page-NNNN-2.png`, ... when a page has several, top to bottom). `image_pages` in the JSON lists the files that belong to each finding.

## Where to change things

| To change | Edit |
|---|---|
| Labels, status words, value shapes, key order | `extractor/fields.py` |
| How a field is written (Markdown, lists, code blocks) | `extractor/markdown.py` |
| JSON / Markdown layout | `extractor/writers.py` |
| Header and footer bands | `extractor/margins.py` |
| Screenshot detection and cropping (padding `CROP_PAD`, scale `CROP_ZOOM`) | `extractor/pictures.py` |
| OCR engine and render scale | `extractor/ocr.py`, `ZOOM` in `extractor/pages.py` |
| Finding boundaries and field assignment | `extractor/parser.py` |

## Limits

- OCR must read the section headings. If one is misread, the lines under it are reported on stderr as `fit no field` instead of landing in the wrong field. Check the pages it names.
- On scanned pages, screenshots are found by their dark or coloured areas. A mostly white, light-themed screenshot may be missed: it is then not cropped, and its text is left out of Evidence with a warning that names the page. On text-layer pages embedded images are used, which is exact.
- Header and footer removal assumes they sit in the top 7% and bottom 10% of the page.
- Bullets read by OCR as stray punctuation are cleaned from list fields only.
- A crop is the detected rectangle plus 4 points of padding. If one is cut short or includes too much, raise or lower `CROP_PAD`, or send me that page.
- A `Port` value must look like a port (`443`, `80, 443`). If the box under the heading was not read, the next line is reported as unplaced instead of being filed as the port.
