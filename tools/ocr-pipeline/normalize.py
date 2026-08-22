#!/usr/bin/env python3
"""OCR normalization stage. Reads data/ocr/*.json (raw_text), writes
data/cleaned/*.json with a normalized_text field ADDED alongside the
untouched raw_text -- normalization never overwrites or discards the
original OCR output, so later stages can always fall back to it.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("ocr-pipeline.normalize")

# Bengali uses U+09E6-U+09EF for digits and its own punctuation forms;
# this only touches whitespace/control artifacts, never rewrites actual
# Bengali characters, so nothing meaningful is altered by the pipeline.
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_HYPHEN_LINEBREAK_RE = re.compile(r"-\n(?=\S)")  # OCR-era hyphen line-wrap, mirrors this project's existing dehyphenate() convention elsewhere


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _HYPHEN_LINEBREAK_RE.sub("", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()


def normalize_page(ocr_json_path: Path, out_dir: Path, force: bool = False) -> Path:
    out_path = out_dir / ocr_json_path.name
    if out_path.exists() and not force:
        return out_path

    with ocr_json_path.open(encoding="utf-8") as f:
        record = json.load(f)

    record["normalized_text"] = normalize_text(record.get("raw_text", ""))
    record["normalized_at"] = datetime.now(timezone.utc).isoformat()

    out_dir.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return out_path


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ocr-dir", default="data/ocr")
    ap.add_argument("--out-dir", default="data/cleaned")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    ocr_dir = Path(args.ocr_dir)
    out_dir = Path(args.out_dir)
    files = sorted(ocr_dir.glob("page_*.json"))
    if not files:
        log.warning("no OCR output found in %s -- run the ocr stage first", args.ocr_dir)
        return

    count = 0
    for f in files:
        normalize_page(f, out_dir, force=args.force)
        count += 1
    log.info("normalized %d page(s) -> %s", count, args.out_dir)


if __name__ == "__main__":
    main()
