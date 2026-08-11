#!/usr/bin/env python3
"""Batch IAST -> Devanagari converter for large .docx files.

Usage:
    python convert.py input.docx output.docx [--checkpoint-every 200]

Resumable: if output.docx + output.progress.json already exist from a
previous (interrupted) run, this resumes from where it left off instead
of starting over.
"""

import argparse
import csv
import json
import os
import sys
import time

from docx import Document

from docx_walk import iter_all_paragraphs, count_all_paragraphs
from engines import (
    looks_like_sanskrit,
    has_mixed_language_run,
    transliterate_with_cross_check,
    has_devanagari,
    has_latin_letters,
)
from paragraph_rewrite import paragraph_full_text, has_mixed_formatting, rewrite_paragraph_text


def progress_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return base + ".progress.json"


def diffs_csv_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return base + ".review_diffs.csv"


def formatting_csv_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return base + ".review_formatting.csv"


def mixed_language_csv_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return base + ".review_mixed_language.csv"


def report_path(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return base + ".sanity_report.txt"


def load_progress(output_path: str):
    p = progress_path(output_path)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "processed_count": 0,
        "converted_count": 0,
        "skipped_count": 0,
        "disagreement_count": 0,
        "mixed_language_count": 0,
    }


def save_progress(output_path: str, progress: dict):
    with open(progress_path(output_path), "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def append_csv_row(path: str, header: list, row: list):
    is_new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(header)
        writer.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input_docx")
    ap.add_argument("output_docx")
    ap.add_argument("--checkpoint-every", type=int, default=200,
                     help="Save an intermediate .docx + progress file every N "
                          "paragraphs processed (python-docx has no page concept, "
                          "so this counts paragraphs, not pages).")
    args = ap.parse_args()

    # Resume from the checkpoint docx if one exists; otherwise start fresh
    # from the input.
    resuming = os.path.exists(args.output_docx) and os.path.exists(progress_path(args.output_docx))
    source_path = args.output_docx if resuming else args.input_docx
    progress = load_progress(args.output_docx)
    start_index = progress["processed_count"]

    if resuming:
        print(f"Resuming from checkpoint: {start_index} paragraphs already processed.")
    document = Document(source_path)

    all_paragraphs = list(iter_all_paragraphs(document))
    total = len(all_paragraphs)
    print(f"Total paragraphs (body + tables + headers/footers + footnotes/endnotes): {total}")

    diffs_csv = diffs_csv_path(args.output_docx)
    formatting_csv = formatting_csv_path(args.output_docx)
    mixed_csv = mixed_language_csv_path(args.output_docx)

    t0 = time.time()
    for idx in range(start_index, total):
        paragraph = all_paragraphs[idx]
        text = paragraph_full_text(paragraph)

        if not looks_like_sanskrit(text):
            progress["skipped_count"] += 1
        elif has_mixed_language_run(text):
            # Contains both IAST and a run of plain-English prose --
            # converting the whole paragraph would corrupt the English
            # part (see README). Leave untouched and flag for a human.
            progress["mixed_language_count"] += 1
            append_csv_row(
                mixed_csv,
                ["paragraph_index", "original_text"],
                [idx, text],
            )
        else:
            mixed_fmt = has_mixed_formatting(paragraph)
            chosen, agree, out_a, out_b = transliterate_with_cross_check(text)

            if not agree:
                progress["disagreement_count"] += 1
                append_csv_row(
                    diffs_csv,
                    ["paragraph_index", "original_iast", "aksharamukha_output", "sanscript_output"],
                    [idx, text, out_a, out_b],
                )

            if mixed_fmt:
                append_csv_row(
                    formatting_csv,
                    ["paragraph_index", "original_iast", "run_count"],
                    [idx, text, len(paragraph.runs)],
                )

            rewrite_paragraph_text(paragraph, chosen)
            progress["converted_count"] += 1

        progress["processed_count"] = idx + 1

        if (idx + 1) % args.checkpoint_every == 0:
            document.save(args.output_docx)
            save_progress(args.output_docx, progress)
            elapsed = time.time() - t0
            rate = (idx + 1 - start_index) / elapsed if elapsed > 0 else 0
            remaining = total - (idx + 1)
            eta = remaining / rate if rate > 0 else float("inf")
            print(f"  checkpoint: {idx + 1}/{total} paragraphs "
                  f"({progress['converted_count']} converted, "
                  f"{progress['skipped_count']} skipped, "
                  f"{progress['mixed_language_count']} mixed-language, "
                  f"{progress['disagreement_count']} disagreements) "
                  f"-- ETA {eta / 60:.1f} min")

    document.save(args.output_docx)
    save_progress(args.output_docx, progress)

    # --- sanity report ---
    input_para_count = count_all_paragraphs(Document(args.input_docx))
    output_para_count = count_all_paragraphs(document)

    stray_latin_count = 0
    for p in iter_all_paragraphs(document):
        t = paragraph_full_text(p)
        if has_devanagari(t) and has_latin_letters(t):
            stray_latin_count += 1

    report_lines = [
        f"Input:  {args.input_docx}",
        f"Output: {args.output_docx}",
        "",
        f"Input paragraph count:  {input_para_count}",
        f"Output paragraph count: {output_para_count}",
        f"Paragraph count match: {'YES' if input_para_count == output_para_count else 'NO -- INVESTIGATE'}",
        "",
        f"Converted paragraphs:    {progress['converted_count']}",
        f"Skipped (non-Sanskrit):  {progress['skipped_count']}",
        f"Mixed English+Sanskrit (left unconverted, needs a human): "
        f"{progress['mixed_language_count']} (see {os.path.basename(mixed_csv) if os.path.exists(mixed_csv) else '(none found)'})",
        f"Engine disagreements:    {progress['disagreement_count']} (see {os.path.basename(diffs_csv)})",
        f"Mixed-formatting paras:  see {os.path.basename(formatting_csv) if os.path.exists(formatting_csv) else '(none found)'}",
        "",
        f"Paragraphs with Devanagari + stray Latin letters mixed together: {stray_latin_count}",
        "  (worth a manual spot-check -- may be legitimate citations/abbreviations, or leftover conversion gaps)",
    ]
    report = "\n".join(report_lines)
    with open(report_path(args.output_docx), "w", encoding="utf-8") as f:
        f.write(report + "\n")

    print("\n" + report)
    print(f"\nDone. Wrote {args.output_docx}")


if __name__ == "__main__":
    sys.exit(main())
