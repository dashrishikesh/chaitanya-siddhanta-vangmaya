#!/usr/bin/env python3
"""Slices a docx into per-anuccheda, per-commentator content using the
color-tag + content-match pipeline, and writes a human-readable review
file -- NOT a final site-content generator. Nothing here touches the
live .md files; this is purely for validating the split before that
next step is built.

Usage:
    python generate_review.py <original_docx> <converted_devanagari_docx> \\
        <output_review.md> <site_md_file> [<site_md_file> ...]
"""

import sys

from docx import Document

from commentary_pipeline.color_tags import tagged_paragraphs, segment_into_blocks, MULA_TAG, QUOTED_TAG
from commentary_pipeline.match_anucchedas import build_docx_search_index, match_all
from commentary_pipeline.site_content import build_anuccheda_index
from run_match_report import TATTVA_SANDARBHA_COLOR_MAP

NAMED_COMMENTATOR_ORDER = ["sarva-samvadini", "baladeva", "radha-mohana", "gaura-kishora"]


def merge_quoted_into_context(blocks):
    """A 'quoted' block (embedded citation) isn't its own commentary
    track -- it's always part of whichever mula/commentator context it
    sits inside. Merge each quoted block into the preceding block (same
    running discussion); if a quoted block is the very first thing in
    an anuccheda's range, treat it as part of mula.
    """
    merged = []
    for b in blocks:
        if b.tag == QUOTED_TAG:
            if merged:
                merged[-1].texts.extend(b.texts)
                merged[-1].end_para = b.end_para
            else:
                b.tag = MULA_TAG
                merged.append(b)
        else:
            merged.append(b)
    return merged


def group_by_tag_in_order(blocks):
    """Within one anuccheda's range, concatenate all same-tag blocks
    (they may be non-contiguous if the docx interleaves e.g. multiple
    baladeva paragraphs with quotes in between) preserving first-seen
    order for stable output (mula, then named commentators as they
    appear).
    """
    order = []
    by_tag = {}
    for b in blocks:
        if b.tag not in by_tag:
            by_tag[b.tag] = []
            order.append(b.tag)
        by_tag[b.tag].append(b.text)
    return [(tag, " ".join(texts)) for tag, texts in ((t, by_tag[t]) for t in order)]


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)

    original_path, converted_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]
    site_paths = sys.argv[4:]

    original_doc = Document(original_path)
    converted_doc = Document(converted_path)
    tagged = list(tagged_paragraphs(original_doc, converted_doc, TATTVA_SANDARBHA_COLOR_MAP))

    big_string, offset_map = build_docx_search_index(tagged)
    sections, _ = build_anuccheda_index(site_paths)
    results = match_all(sections, big_string, offset_map)

    starts = {r.anuccheda_num: r.docx_start_para for r in results if r.found}
    all_nums = sorted(starts)

    out_lines = []
    for i, num in enumerate(all_nums):
        start_para = starts[num]
        end_para = starts[all_nums[i + 1]] if i + 1 < len(all_nums) else None

        range_paras = [
            (idx, tag, text) for idx, tag, text in tagged
            if idx >= start_para and (end_para is None or idx < end_para)
        ]
        blocks = segment_into_blocks(range_paras)
        blocks = merge_quoted_into_context(blocks)
        grouped = group_by_tag_in_order(blocks)

        out_lines.append(f"\n{'=' * 60}\nअनुच्छेदः {num}  (docx paras {start_para}-{(end_para or '?')})\n{'=' * 60}")
        for tag, text in grouped:
            out_lines.append(f"\n--- {tag} ---")
            out_lines.append(text[:600] + ("..." if len(text) > 600 else ""))

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

    print(f"Wrote review file: {output_path}")
    print(f"Covered {len(all_nums)} anucchedas.")


if __name__ == "__main__":
    main()
