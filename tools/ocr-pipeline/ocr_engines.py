#!/usr/bin/env python3
"""OCR engine adapters. Each adapter implements a single method,
recognize(image_path, lang) -> str, so the pipeline can swap engines
without touching the rest of the code. Only TesseractEngine is wired up
to an installed dependency right now -- the others are documented stubs
that raise a clear "not installed" error rather than silently failing,
per the project's convention of logging/flagging rather than guessing
(see tools/wisdomlib-scraper's review-log pattern).
"""
from __future__ import annotations

import abc


class OcrEngine(abc.ABC):
    name: str

    @abc.abstractmethod
    def recognize(self, image_path: str, lang: str) -> str:
        """Returns raw recognized text for one page image."""


class TesseractEngine(OcrEngine):
    name = "tesseract"

    def __init__(self):
        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "pytesseract not installed -- run: pip install pytesseract Pillow"
            ) from exc
        self._pytesseract = __import__("pytesseract")
        self._Image = __import__("PIL.Image", fromlist=["Image"])

    def recognize(self, image_path: str, lang: str) -> str:
        img = self._Image.open(image_path)
        return self._pytesseract.image_to_string(img, lang=lang)


class PaddleOcrEngine(OcrEngine):
    name = "paddleocr"

    def __init__(self):
        raise RuntimeError(
            "PaddleOCR not installed (heavy dependency, pulls in PaddlePaddle) -- "
            "run: pip install paddleocr paddlepaddle, then re-select this engine"
        )

    def recognize(self, image_path: str, lang: str) -> str:  # pragma: no cover
        raise NotImplementedError


class GoogleVisionEngine(OcrEngine):
    name = "google-vision"

    def __init__(self):
        raise RuntimeError(
            "Google Cloud Vision not configured -- requires google-cloud-vision "
            "package and GOOGLE_APPLICATION_CREDENTIALS pointing at a service-account key"
        )

    def recognize(self, image_path: str, lang: str) -> str:  # pragma: no cover
        raise NotImplementedError


ENGINES = {
    "tesseract": TesseractEngine,
    "paddleocr": PaddleOcrEngine,
    "google-vision": GoogleVisionEngine,
}


def get_engine(name: str) -> OcrEngine:
    if name not in ENGINES:
        raise ValueError(f"unknown engine {name!r} -- choices: {sorted(ENGINES)}")
    return ENGINES[name]()
