"""Plain data shared by every module."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Line:
    """One text line (or an image region) with its position in PDF points."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 0
    picture: bool = False  # image region placeholder; text is empty


@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
