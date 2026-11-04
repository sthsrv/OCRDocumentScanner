"""End-to-end check on a synthetic report: layout quirks in, expected JSON/Markdown out."""
import json
import sys
from pathlib import Path

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


def test_no_findings_section(tmp_path):
    doc = pymupdf.open()
    _page(doc, [("Just a cover page with enough text", 60, 100)])
    pdf = tmp_path / "plain.pdf"
    doc.save(pdf)
    with pytest.raises(ValueError, match="Findings"):
        convert_pdf(pdf, tmp_path / "out", ocr=NoOCR())
