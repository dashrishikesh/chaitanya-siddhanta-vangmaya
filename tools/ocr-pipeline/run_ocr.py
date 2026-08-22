#!/usr/bin/env python3
"""OCR stage: page images -> per-page structured JSON. Never merges
pages into one file (each page's result is independently inspectable and
resumable, matching the project's page-level provenance requirement).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from ocr_engines import get_engine

log = logging.getLogger("ocr-pipeline.ocr")

_PAGE_NUM_RE = re.compile(r"page_(\d+)\.png$")


def parse_page_range(spec: str | None) -> tuple[int | None, int | None]:
    if not spec:
        return None, None
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    n = int(spec)
    return n, n


def ocr_pages(
    pages_dir: str,
    out_dir: str,
    engine_name: str = "tesseract",
    lang: str = "ben",
    page_range: str | None = None,
    force: bool = False,
) -> list[str]:
    pages_path = Path(pages_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    start, end = parse_page_range(page_range)
    images = sorted(pages_path.glob("page_*.png"))
    if start is not None:
        images = [
            p for p in images
            if start <= int(_PAGE_NUM_RE.search(p.name).group(1)) <= end
        ]

    if not images:
        raise FileNotFoundError(f"no page_*.png images found in {pages_dir}")

    engine = get_engine(engine_name)
    written = []
    for img in images:
        page_num = int(_PAGE_NUM_RE.search(img.name).group(1))
        out_file = out_path / f"page_{page_num:04d}.json"
        if out_file.exists() and not force:
            written.append(str(out_file))
            continue

        log.info("OCR page %d (%s)", page_num, engine_name)
        text = engine.recognize(str(img), lang=lang)
        record = {
            "page": page_num,
            "source_image": str(img),
            "ocr_engine": engine_name,
            "raw_text": text,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        written.append(str(out_file))

    log.info("OCR'd %d page(s) -> %s", len(written), out_dir)
    return written


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pages-dir", default="data/pages")
    ap.add_argument("--out-dir", default="data/ocr")
    ap.add_argument("--engine", default="tesseract", choices=["tesseract", "paddleocr", "google-vision"])
    ap.add_argument("--lang", default="ben", help="tesseract language code (e.g. ben, eng, ben+eng)")
    ap.add_argument("--pages", help="page range for testing, e.g. 1-10 or 5")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    ocr_pages(args.pages_dir, args.out_dir, engine_name=args.engine, lang=args.lang, page_range=args.pages, force=args.force)


if __name__ == "__main__":
    main()
