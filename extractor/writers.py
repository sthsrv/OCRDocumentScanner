"""Build the output structure and write the .json and .md files."""
from __future__ import annotations

import json
from pathlib import Path

from .fields import KIND, ORDER, TITLES
from .markdown import render
from .parser import Finding


def image_name(page: int) -> str:
    return f"images/page-{page:04d}.png"


def finding_dict(finding: Finding, right: float) -> dict:
    values = {key: render(key, finding.blocks.get(key, []), right) for key in ORDER}
    if not values["evidence"]:  # only shown when the report has a text Evidence section
        del values["evidence"]
    return {
        "title": finding.title or values["vulnerability_type"] or None,
        **values,
        "image_pages": [image_name(n) for n in finding.picture_pages],
    }


def write_json(items: list[dict], path: Path) -> None:
    path.write_text(json.dumps({"findings": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(items: list[dict], path: Path) -> None:
    chunks: list[str] = []
    for item in items:
        chunks.append(f"### {item['title'] or 'Untitled finding'}")
        for key in ORDER:
            value = item.get(key)
            if not value:
                continue
            if isinstance(value, list):
                chunks.append(f"{TITLES[key]}:\n" + "\n".join(f"- {v}" for v in value))
            elif KIND[key] == "scalar":
                chunks.append(f"{TITLES[key]}: {value}")
            else:
                chunks.append(f"{TITLES[key]}:\n\n{value}")
    path.write_text("\n\n".join(chunks) + "\n", encoding="utf-8")
