#!/usr/bin/env python3
"""Generic document OCR pipeline CLI. Operates on a user-provided local
PDF or image directory -- no source is bundled, downloaded, or hardcoded
by this tool. Each stage is independently runnable and resumable.

Usage:
    python3 pipeline.py extract-pages --input /path/to/document.pdf
    python3 pipeline.py ocr --pages 1-10
    python3 pipeline.py normalize
    python3 pipeline.py validate
    python3 pipeline.py status
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from extract_pages import extract_pages
from normalize import main as normalize_main
from run_ocr import ocr_pages
from validate import validate_pages

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ocr-pipeline")


def cmd_extract_pages(args):
    extract_pages(args.input, args.out_dir, dpi=args.dpi, start=args.start, end=args.end, force=args.force)


def cmd_ocr(args):
    ocr_pages(args.pages_dir, args.out_dir, engine_name=args.engine, lang=args.lang, page_range=args.pages, force=args.force)


def cmd_normalize(args):
    import sys

    sys.argv = ["normalize.py", "--ocr-dir", args.ocr_dir, "--out-dir", args.out_dir] + (["--force"] if args.force else [])
    normalize_main()


def cmd_validate(args):
    report = validate_pages(Path(args.cleaned_dir))
    flagged = [r for r in report if r["status"] == "needs_review"]
    Path(args.out).write_text(
        json.dumps({"total_pages": len(report), "flagged_pages": len(flagged), "pages": report}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("%d page(s), %d flagged -> %s", len(report), len(flagged), args.out)


def cmd_status(args):
    base = Path(args.data_dir)
    for stage, pattern in [("pages", "page_*.png"), ("ocr", "page_*.json"), ("cleaned", "page_*.json")]:
        d = base / stage
        n = len(list(d.glob(pattern))) if d.exists() else 0
        print(f"{stage:10s} {n:5d} file(s)  ({d})")
    report_path = base / "validation_report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        print(f"validation: {report['flagged_pages']} of {report['total_pages']} page(s) flagged for review")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract-pages")
    p.add_argument("--input", required=True)
    p.add_argument("--out-dir", default="data/pages")
    p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--start", type=int)
    p.add_argument("--end", type=int)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_extract_pages)

    p = sub.add_parser("ocr")
    p.add_argument("--pages-dir", default="data/pages")
    p.add_argument("--out-dir", default="data/ocr")
    p.add_argument("--engine", default="tesseract", choices=["tesseract", "paddleocr", "google-vision"])
    p.add_argument("--lang", default="ben")
    p.add_argument("--pages", help="e.g. 1-10 or 5")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_ocr)

    p = sub.add_parser("normalize")
    p.add_argument("--ocr-dir", default="data/ocr")
    p.add_argument("--out-dir", default="data/cleaned")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_normalize)

    p = sub.add_parser("validate")
    p.add_argument("--cleaned-dir", default="data/cleaned")
    p.add_argument("--out", default="data/validation_report.json")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("status")
    p.add_argument("--data-dir", default="data")
    p.set_defaults(func=cmd_status)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
