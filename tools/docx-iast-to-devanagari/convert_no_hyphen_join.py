#!/usr/bin/env python3
"""Same docx-to-docx contract as convert.py (1:1 paragraph count, in
place text rewrite), but calls transliterate_aksharamukha directly
instead of transliterate_with_cross_check -- which applies
join_compound_hyphens and would strip this work's hyphens (e.g.
"śrīla-rūpa-sanātanau" -> "श्रीलरूपसनातनौ"), breaking the hyphen-preserving
convention this site uses for tattva-sandarbha, Govinda-bhashya, and
(via this script) Bhagavat-sandarbha alike.

Usage: python convert_no_hyphen_join.py input.docx output.docx
"""
import sys

from docx import Document

from docx_walk import iter_all_paragraphs
from engines import looks_like_sanskrit, has_mixed_language_run, transliterate_aksharamukha, normalize_avagraha_quotes
from paragraph_rewrite import paragraph_full_text, rewrite_paragraph_text


def main():
    input_docx, output_docx = sys.argv[1], sys.argv[2]
    document = Document(input_docx)
    all_paragraphs = list(iter_all_paragraphs(document))
    total = len(all_paragraphs)

    converted = skipped = mixed = 0
    for idx, paragraph in enumerate(all_paragraphs):
        text = paragraph_full_text(paragraph)
        if not looks_like_sanskrit(text):
            skipped += 1
            continue
        if has_mixed_language_run(text):
            mixed += 1
            continue
        out = transliterate_aksharamukha(normalize_avagraha_quotes(text))
        rewrite_paragraph_text(paragraph, out)
        converted += 1
        if (idx + 1) % 500 == 0:
            print(f"  {idx + 1}/{total} ({converted} converted, {skipped} skipped, {mixed} mixed)")

    document.save(output_docx)
    print(f"Wrote {output_docx}: {total} paragraphs "
          f"({converted} converted, {skipped} skipped, {mixed} mixed-language)")


if __name__ == "__main__":
    main()
