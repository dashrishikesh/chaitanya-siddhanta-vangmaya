#!/usr/bin/env python3
"""QC stage. Reads data/cleaned/*.json and flags pages whose OCR output
looks unreliable, instead of silently trusting every page -- mirrors
this project's established "log ambiguous cases for manual review, don't
guess" convention (see tools/wisdomlib-scraper's review_needed.csv).

Never invents or fills in missing text -- a flagged page's normalized_text
is left exactly as produced by the OCR stage.
"""
from __future__ import annotations

import json
import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("ocr-pipeline.validate")

# A page shorter than this fraction of the document's average length is
# flagged -- catches blank/near-blank OCR results without needing a fixed
# absolute threshold that wouldn't generalize across document sizes.
SHORT_PAGE_RATIO = 0.3
MIN_CHARS_ABSOLUTE = 20


def validate_pages(cleaned_dir: Path) -> list[dict]:
    files = sorted(cleaned_dir.glob("page_*.json"))
    records = []
    for f in files:
        with f.open(encoding="utf-8") as fh:
            records.append(json.load(fh))

    if not records:
        return []

    lengths = [len(r.get("normalized_text", "")) for r in records]
    avg_len = statistics.mean(lengths) if lengths else 0

    report = []
    for r, length in zip(records, lengths):
        status = "ok"
        reason = None
        if length < MIN_CHARS_ABSOLUTE:
            status = "needs_review"
            reason = "near-empty OCR output"
        elif avg_len > 0 and length < avg_len * SHORT_PAGE_RATIO:
            status = "needs_review"
            reason = "text length significantly below document average"

        report.append(
            {
                "page": r.get("page"),
                "status": status,
                "characters": length,
                "reason": reason,
            }
        )
    return report


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cleaned-dir", default="data/cleaned")
    ap.add_argument("--out", default="data/validation_report.json")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    report = validate_pages(Path(args.cleaned_dir))
    if not report:
        log.warning("no cleaned pages found in %s -- run the normalize stage first", args.cleaned_dir)
        return

    flagged = [r for r in report if r["status"] == "needs_review"]
    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_pages": len(report),
                "flagged_pages": len(flagged),
                "pages": report,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    log.info("validated %d page(s), %d flagged for review -> %s", len(report), len(flagged), args.out)


if __name__ == "__main__":
    main()
