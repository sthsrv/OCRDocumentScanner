"""PaddleOCR wrapper. Models load on first use, so text-layer PDFs never pay for them."""
from __future__ import annotations

import sys

import numpy as np

Box = tuple[float, float, float, float]


class PaddleReader:
    def __init__(self) -> None:
        self._engine = None

    def read(self, image: np.ndarray) -> list[tuple[str, Box]]:
        """Return (text, (x0, y0, x1, y1)) for each detected text line, in image pixels."""
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError("PaddleOCR is not installed; run: pip install -r requirements.txt") from exc
            print("Loading PaddleOCR (the first run downloads models)...", file=sys.stderr)
            self._engine = PaddleOCR(
                use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False
            )
        result = self._engine.predict(image)[0]
        return [
            (text.strip(), tuple(map(float, box)))
            for text, box in zip(result["rec_texts"], result["rec_boxes"])
            if text.strip()
        ]
