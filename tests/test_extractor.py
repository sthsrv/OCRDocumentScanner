"""End-to-end check on a synthetic report: layout quirks in, expected JSON/Markdown out."""
import json
import sys
from pathlib import Path

import numpy as np
import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extractor import convert_pdf  # noqa: E402

VECTOR = "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N"


class NoOCR:
    def read(self, image):
        raise AssertionError("text-layer pages must not be OCR'd")


def _page(doc, items, image=None):
    page = doc.new_page()
    page.insert_text((60, 30), "ACME Pentest Report", fontsize=8)  # running header
    for text, x, y in items:
        page.insert_text((x, y), text, fontsize=10)
    for text in ("Powered by VOC.", "Confidential", "2026"):  # running footer
        page.insert_text((60 if text.startswith("P") else 300, 810), text, fontsize=8)
    if image:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 300, 150), False)
        pix.set_rect(pix.irect, (200, 40, 40))
        page.insert_image(pymupdf.Rect(60, 230, 400, 400), pixmap=pix)
        page.insert_text((100, 300), "SECRET SCREENSHOT TEXT", fontsize=10)


@pytest.fixture
def report(tmp_path):
    doc = pymupdf.open()
    _page(doc, [("Executive Summary", 60, 100), ("Port: 99", 60, 130), ("Description", 60, 160)])
    _page(doc, [
        ("Findings", 60, 90),
        ("Open Redirect", 60, 120), ("High (7.5)", 400, 120),   # title bar, no label
        (VECTOR, 60, 150),                                       # CVSS value without its label, above the type
        ("Vulnerability Type: Open Redirect", 60, 170),
        ("Resolved", 60, 190),                                   # status without its label
        ("Port", 60, 220), ("443", 60, 240),                     # port above scopes this time
        ("Scopes:", 60, 270), ("• 10.0.0.1", 70, 290), ("• 10.0.0.2", 70, 305),
        ("Description", 60, 340),
        ("The login page redirects users to any URL.", 60, 365),
        ("- first bullet", 60, 380),
    ])
    _page(doc, [
        ("Output", 60, 90),
        ("Port: 443", 60, 120), ("HTTP/1.1 302 Found", 60, 135), ("Location: https://evil.example", 80, 150),
        ("Remarks", 60, 200),
    ], image=True)
    _page(doc, [
        ("SQL Injection", 60, 100), ("Critical (9.8)", 400, 100),
        ("Vulnerability Type: SQL Injection", 60, 130),
        ("CVSS: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 60, 150),
        ("Status: New", 60, 170),
        ("Affected Endpoints:", 60, 200), ("Scopes:", 60, 230), ("api.example.com", 70, 250),
        ("Recommendation", 60, 290), ("Use parameterised queries.", 60, 310),
        ("Reference", 60, 340), ("https://owasp.org", 70, 360),
    ])
    _page(doc, [("Conclusion", 60, 90), ("Port: 1", 60, 120), ("Remarks", 60, 150)], image=True)
    pdf = tmp_path / "report.pdf"
    doc.save(pdf)
    return pdf


def test_findings_extracted(report, tmp_path):
    out = tmp_path / "out"
    convert_pdf(report, out, ocr=NoOCR())
    first, second = json.loads((out / "report.json").read_text())["findings"]

    assert first["title"] == "Open Redirect"
    assert first["cvss"] == VECTOR and first["status"] == "Resolved" and first["port"] == "443"
    assert first["scopes"] == ["10.0.0.1", "10.0.0.2"]
    assert "- first bullet" in first["description"].splitlines()
    assert first["output"].startswith("```\nPort: 443\n") and "    Location" in first["output"]
    assert first["remarks"] == "" and first["image_pages"] == ["images/page-0003.png"]

    assert second["title"] == "SQL Injection" and second["cvss"].endswith("A:H") and second["status"] == "New"
    assert second["affected_endpoints"] == [] and second["scopes"] == ["api.example.com"]
    assert second["reference"] == ["https://owasp.org"] and second["image_pages"] == []

    # only the findings page with a screenshot is saved; the one after Conclusion is not
    assert sorted(p.name for p in (out / "images").iterdir()) == ["page-0003.png"]
    crop = pymupdf.Pixmap(out / "images" / "page-0003.png")  # the 340x170 pt image plus padding, not the 595x842 page
    assert (crop.width, crop.height) == pytest.approx((696, 356), abs=6)


def test_page_with_two_screenshots_gives_two_numbered_crops(tmp_path):
    doc = pymupdf.open()
    _page(doc, [("Findings", 60, 90), ("Redirect", 60, 120), ("Low (3.1)", 400, 120), (VECTOR, 60, 150),
                ("Vulnerability Type: Redirect", 60, 170), ("Remarks", 60, 200)], image=True)
    blue = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 100), False)
    blue.set_rect(blue.irect, (30, 60, 200))
    doc[0].insert_image(pymupdf.Rect(60, 450, 300, 570), pixmap=blue)  # second screenshot, below the first
    _page(doc, [("Conclusion", 60, 90)])
    pdf = tmp_path / "two.pdf"
    doc.save(pdf)
    out = tmp_path / "out"
    convert_pdf(pdf, out, ocr=NoOCR())
    names = ["images/page-0001-1.png", "images/page-0001-2.png"]
    assert json.loads((out / "two.json").read_text())["findings"][0]["image_pages"] == names
    assert all((out / n).is_file() for n in names)


def test_nothing_else_leaks(report, tmp_path):
    out = tmp_path / "out"
    convert_pdf(report, out, ocr=NoOCR())
    text = (out / "report.json").read_text() + (out / "report.md").read_text()
    for noise in ("SECRET", "Powered by", "Confidential", "ACME", "Executive Summary", "Port: 99", "Port: 1\n"):
        assert noise not in text

    md = (out / "report.md").read_text()
    assert md.startswith("### Open Redirect\n\nVulnerability Type: Open Redirect\n\nCVSS: " + VECTOR)
    assert "\n\n### SQL Injection\n" in md


def test_unread_port_value_is_not_filled_from_the_next_line(tmp_path, capsys):
    doc = pymupdf.open()
    _page(doc, [
        ("Findings", 60, 90), ("Redirect", 60, 120), ("Low (3.1)", 400, 120), (VECTOR, 60, 150),
        ("Vulnerability Type: Redirect", 60, 170),
        ("Port", 60, 200),                                  # its value box was not read by OCR
        ("Output text under a heading OCR lost", 60, 230),
    ])
    _page(doc, [("Conclusion", 60, 90)])
    pdf = tmp_path / "port.pdf"
    doc.save(pdf)
    out = tmp_path / "out"
    convert_pdf(pdf, out, ocr=NoOCR())
    assert json.loads((out / "port.json").read_text())["findings"][0]["port"] == ""
    assert "fit no field" in capsys.readouterr().err


def test_second_report_layout(tmp_path, capsys):
    """Severity written '5.3 (Medium)', a wrapped title, no 'Vulnerability Type', extra headings,
    a title bar split by a page break, and a section that ends at 'Further Recommendations'."""
    from extractor.fields import SEVERITY

    assert SEVERITY.match("5.3（(Medium)")  # a bracket OCR may misread
    doc = pymupdf.open()
    _page(doc, [("Executive Summary", 60, 100)])  # headers and footers are found by repeating on 3 pages
    _page(doc, [
        ("Findings", 60, 90),
        ("Public Blob Enumeration", 60, 120), ("5.3 (Medium)", 400, 128), ("Container (db-backups)", 60, 140),
        ("Description", 60, 200), ("Anonymous listing is allowed.", 60, 220),
        ("Impact", 60, 260), ("Attackers can list blobs.", 60, 280),
        ("Recommendation", 60, 320), ("Make it private.", 60, 340),
        ("Affected System and Endpoint", 60, 380), ("https://acct.blob.example/db", 70, 400),
        ("Status", 60, 430), ("Not Remediated", 60, 450),
        ("CVSS:5.3/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N", 60, 480),  # no label
        ("Steps for Reproduction", 60, 520), ("Open the URL.", 60, 540),
        ("Evidence", 60, 580), ("text of a screenshot nobody detected", 70, 610),
        ("References", 60, 650), ("https://docs.example/ref", 70, 670),
        ("Management Response", 60, 700), ("5.3 (Medium)", 400, 740),  # severity box ends the page ...
    ])
    _page(doc, [("Azure SQL Exposed", 60, 100),  # ... and its title starts the next one
                ("Description", 60, 160), ("SQL is public.", 60, 180),
                ("Further Recommendations", 60, 250), ("Ignore this text", 60, 270)])
    pdf = tmp_path / "second.pdf"
    doc.save(pdf)
    out = tmp_path / "out"
    convert_pdf(pdf, out, ocr=NoOCR())
    first, second = json.loads((out / "second.json").read_text())["findings"]

    assert first["title"] == "Public Blob Enumeration Container (db-backups)"
    assert first["cvss"] == "CVSS:5.3/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N" and first["status"] == "Not Remediated"
    assert first["affected_endpoints"] == ["https://acct.blob.example/db"] and first["reference"] == ["https://docs.example/ref"]
    assert first["impact"] == "Attackers can list blobs." and first["steps_for_reproduction"] == "Open the URL."
    assert "evidence" not in first and "management_response" not in first  # empty or never wanted
    assert second["title"] == "Azure SQL Exposed" and second["description"] == "SQL is public."
    text = (out / "second.json").read_text() + (out / "second.md").read_text()
    assert "nobody detected" not in text and "Ignore this text" not in text
    assert "Evidence text on page(s) [2]" in capsys.readouterr().err


def test_scanned_page_dark_strip_is_a_screenshot_but_a_coloured_bar_is_not():
    from extractor import pictures

    img = np.full((842, 595, 3), 255, np.uint8)
    img[100:175, 54:541] = (50, 20, 50)    # a terminal capture, 487 x 75 pt
    img[300:375, 54:541] = (245, 166, 35)  # a title bar of exactly the same size
    page = pymupdf.open().new_page()
    page.insert_image(page.rect, pixmap=pymupdf.Pixmap(pymupdf.csRGB, 595, 842, img.tobytes(), False))
    found = pictures.scanned(page)
    assert len(found) == 1 and found[0][1] < 200


def test_result_folder_is_named_after_the_pdf_and_its_date(tmp_path):
    from extractor.cli import result_folder

    pdf = tmp_path / "My Report.pdf"
    pdf.write_bytes(b"")
    folder = result_folder(pdf, Path("outputs"))
    assert folder.parent == Path("outputs") and folder.name.startswith("My Report_")
    assert len(folder.name) == len("My Report_") + len("2026-11-04")


def test_no_findings_section(tmp_path):
    doc = pymupdf.open()
    _page(doc, [("Just a cover page with enough text", 60, 100)])
    pdf = tmp_path / "plain.pdf"
    doc.save(pdf)
    with pytest.raises(ValueError, match="Findings"):
        convert_pdf(pdf, tmp_path / "out", ocr=NoOCR())
