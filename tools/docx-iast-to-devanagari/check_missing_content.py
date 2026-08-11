#!/usr/bin/env python3
"""Flags anucchedas where the docx has meaningfully more content than the
site currently does -- a signal (not proof) of a missing paragraph, the
same pattern found in अनुच्छेदः 28 of प्रमाण-प्रकरणम् (a whole मूल
sentence sitting in the docx between the verse-quote and बलदेवः's
commentary that never made it onto the site).

Usage:
    python check_missing_content.py <original_docx> <converted_devanagari_docx> \\
        <site_md_file> [<site_md_file> ...]
"""

import re
import sys

from docx import Document

from commentary_pipeline.color_tags import tagged_paragraphs
from commentary_pipeline.match_anucchedas import build_docx_search_index, match_all, normalize_for_matching
from commentary_pipeline.site_content import build_anuccheda_index
from run_match_report import TATTVA_SANDARBHA_COLOR_MAP

_BRACKET_NUM_RE = re.compile(r"^\[[\dA-Za-z\-–—]+\]$")
# The paragraph text checked here is the *converted* Devanagari (tagged_paragraphs
# reads from converted_doc), so the placeholder must be matched in Devanagari,
# not IAST -- and matched as the paragraph's entire content (after stripping an
# optional "commentator : " label prefix), not as a substring: a real, lengthy
# commentary paragraph can legitimately contain the word "व्याख्यातम्" itself
# (verified: this happened for अनुच्छेदः ११'s real सर्व-संवादिनी content,
# which got its whole ~10,000-char length wrongly zeroed out by a substring check).
_DOCX_PLACEHOLDER_RE = re.compile(r"^(?:[^:]+:\s*)?न\s*व्याख्यातम्\.?$")


def docx_range_normalized_length(tagged, start_para, end_para):
    total = 0
    for idx, tag, text in tagged:
        if idx < start_para or (end_para is not None and idx >= end_para):
            continue
        if _BRACKET_NUM_RE.match(text.strip()):
            continue  # stray old-numbering marker, not real content
        if _DOCX_PLACEHOLDER_RE.match(text.strip()):
            continue  # "न व्याख्यातम्।" placeholder, correctly omitted on site
        total += len(normalize_for_matching(text))
    return total


_SITE_PLACEHOLDER_RE = re.compile(r"^_?न\s*व्याख्यातम्\.?_?$")


def site_section_normalized_length(section):
    total = len(normalize_for_matching(section.root_quote))
    for label, text in section.commentaries.items():
        if _SITE_PLACEHOLDER_RE.match(text.strip()):
            continue  # "न व्याख्यातम्।" placeholder, correctly omitted
        total += len(normalize_for_matching(text))
    return total


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)

    original_path, converted_path = sys.argv[1], sys.argv[2]
    site_paths = sys.argv[3:]

    original_doc = Document(original_path)
    converted_doc = Document(converted_path)
    tagged = list(tagged_paragraphs(original_doc, converted_doc, TATTVA_SANDARBHA_COLOR_MAP))

    big_string, offset_map = build_docx_search_index(tagged)
    sections, _ = build_anuccheda_index(site_paths)
    results = {r.anuccheda_num: r for r in match_all(sections, big_string, offset_map)}

    section_by_num = {s.anuccheda_num: s for s in sections}
    nums_in_order = sorted(n for n in results if results[n].found)

    flagged = []
    for i, num in enumerate(nums_in_order):
        start = results[num].docx_start_para
        end = results[nums_in_order[i + 1]].docx_start_para if i + 1 < len(nums_in_order) else None
        docx_len = docx_range_normalized_length(tagged, start, end)
        site_len = site_section_normalized_length(section_by_num[num])
        if docx_len == 0:
            continue
        deficit = docx_len - site_len
        ratio = site_len / docx_len if docx_len else 1.0
        if deficit > 60 and ratio < 0.97:
            flagged.append((num, section_by_num[num].heading_text, docx_len, site_len, deficit))

    print(f"Checked {len(nums_in_order)} anucchedas.")
    print(f"Flagged {len(flagged)} with a meaningful docx-vs-site content deficit:\n")
    for num, heading, docx_len, site_len, deficit in flagged:
        print(f"  anuccheda #{num} ({heading}): docx={docx_len} chars, site={site_len} chars, deficit={deficit}")


if __name__ == "__main__":
    main()
