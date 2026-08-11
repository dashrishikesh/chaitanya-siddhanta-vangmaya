#!/usr/bin/env python3
"""Content-matches a Sandarbha docx's paragraphs against the site's
existing per-anuccheda root-quote text, reporting coverage before any
final content is generated.

Usage:
    python run_match_report.py <original_docx> <converted_devanagari_docx> \\
        <site_md_file> [<site_md_file> ...]
"""

import sys

from docx import Document

from commentary_pipeline.color_tags import tagged_paragraphs
from commentary_pipeline.match_anucchedas import build_docx_search_index, match_all
from commentary_pipeline.site_content import build_anuccheda_index

# Confirmed against sat-sandarbha_-_1_-_tattva_sandarbha_-_jiva_gosvamin.docx's
# own front-matter legend + explicit name-labels (baladevaḥ:/sarva-saṃvādinī:/
# rādhā-mohana-gosvāmī:/gaura-kiśora-gosvāmī:). Other Sandarbhas may use
# different hex values for the same roles -- check each docx's own legend
# and name-label colors before reusing this map.
TATTVA_SANDARBHA_COLOR_MAP = {
    "800080": "baladeva",
    "008000": "sarva-samvadini",
    "993300": "radha-mohana",
    "993366": "gaura-kishora",
    "0000FF": "quoted",
    "3366FF": "quoted",
    "DEFAULT": "mula",
}


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    original_path, converted_path = sys.argv[1], sys.argv[2]
    site_paths = sys.argv[3:]

    original_doc = Document(original_path)
    converted_doc = Document(converted_path)

    tagged = list(tagged_paragraphs(original_doc, converted_doc, TATTVA_SANDARBHA_COLOR_MAP))
    print(f"Tagged {len(tagged)} non-empty paragraphs from the docx.")

    big_string, offset_map = build_docx_search_index(tagged)

    sections, warnings = build_anuccheda_index(site_paths)
    print(f"Parsed {len(sections)} anuccheda sections from the site content.")
    if warnings:
        print(f"({len(warnings)} positional-vs-declared-number warnings -- expected, see site_content.py docstring)")

    results = match_all(sections, big_string, offset_map)

    found = [r for r in results if r.found]
    missing = [r for r in results if not r.found]

    print()
    print(f"Matched: {len(found)}/{len(results)}")
    if missing:
        print(f"NOT matched (need manual attention): {[r.anuccheda_num for r in missing]}")
    else:
        print("All anucchedas matched.")

    print()
    print("First 10 matches (anuccheda_num -> docx paragraph index):")
    for r in found[:10]:
        print(f"  {r.anuccheda_num} -> para {r.docx_start_para} (matched {r.match_length} chars)")

    # sanity check: matched docx paragraph positions should be monotonically
    # increasing (we read both sources front-to-back) -- a regression here
    # would mean two anucchedas matched to overlapping/out-of-order text.
    out_of_order = []
    prev = -1
    for r in found:
        if r.docx_start_para is not None:
            if r.docx_start_para < prev:
                out_of_order.append(r.anuccheda_num)
            prev = r.docx_start_para
    if out_of_order:
        print()
        print(f"WARNING -- matched out of paragraph order (investigate): {out_of_order}")


if __name__ == "__main__":
    main()
