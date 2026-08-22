#!/usr/bin/env python3
"""Splits a local PDF into per-page PNG images via poppler's pdftoppm
(shelling out, matching this project's existing convention of using CLI
poppler tools rather than a heavy Python PDF-rendering dependency).

Takes a user-provided --input path at runtime; no source is bundled or
hardcoded here.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("ocr-pipeline.extract")


def extract_pages(
    input_pdf: str,
    out_dir: str,
    dpi: int = 300,
    start: int | None = None,
    end: int | None = None,
    force: bool = False,
) -> list[str]:
    """Renders input_pdf's pages to out_dir/page_%04d.png. Returns the
    list of page image paths produced or already present."""
    src = Path(input_pdf)
    if not src.is_file():
        raise FileNotFoundError(f"input PDF not found: {input_pdf}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    existing = sorted(out.glob("page_*.png"))
    if existing and not force and start is None and end is None:
        log.info("found %d existing page(s) in %s, skipping (use --force to redo)", len(existing), out_dir)
        return [str(p) for p in existing]

    cmd = ["pdftoppm", "-png", "-r", str(dpi), "-progress"]
    if start is not None:
        cmd += ["-f", str(start)]
    if end is not None:
        cmd += ["-l", str(end)]
    cmd += [str(src), str(out / "page")]

    log.info("running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # pdftoppm names output page-1.png, page-2.png, ... (no zero-padding
    # by default for small page counts) -- normalize to page_0001.png so
    # downstream stages can sort/resume reliably regardless of page count.
    for p in out.glob("page-*.png"):
        num = int(p.stem.split("-")[-1])
        target = out / f"page_{num:04d}.png"
        if target.exists() and not force:
            p.unlink()
            continue
        p.rename(target)

    pages = sorted(out.glob("page_*.png"))
    log.info("extracted %d page(s) to %s", len(pages), out_dir)
    return [str(p) for p in pages]


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="path to a local PDF file")
    ap.add_argument("--out-dir", default="data/pages")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--start", type=int, help="first page (1-indexed) for range processing")
    ap.add_argument("--end", type=int, help="last page (1-indexed) for range processing")
    ap.add_argument("--force", action="store_true", help="re-extract even if pages already exist")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    extract_pages(args.input, args.out_dir, dpi=args.dpi, start=args.start, end=args.end, force=args.force)


if __name__ == "__main__":
    main()
