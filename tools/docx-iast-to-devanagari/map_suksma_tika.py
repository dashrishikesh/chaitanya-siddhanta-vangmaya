#!/usr/bin/env python3
"""Maps Baladeva's Suksma-tika (a terse gloss on his own Govinda-bhashya,
adhyaya 1 only) onto the site's (now reference-table-corrected) adhikarana
boundaries, as a "### सूक्ष्म-टीका" commentary tab appended after each
adhikarana's existing root content.

The tika has no adhikarana-level markers of its own; it's split into 4
pada blocks by explicit "prathamapadah/dvitiyapadah/..." headings, and
within each pada, individual sutra-commentary segments are delimited by
the tika's own embedded "||N||" sutra-completion markers. Those per-pada
segment counts (31, 33, 43, 28) match the site's corrected per-pada sutra
counts (32, 33, 43, 28) almost exactly -- pada 1 is off by one somewhere
in a multi-sutra adhikarana (confirmed the mismatch isn't at the
adhikarana-4/5 boundary via the tika's own "ekadasa-sutri" ["eleven
sutras"] cross-reference right after segment 11) -- so content is
aggregated per-ADHIKARANA (not per-sutra), which tolerates that one
internal ambiguity without affecting any adhikarana boundary.
"""
import re
import sys

from docx import Document

sys.path.insert(0, ".")
from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text
from generate_govinda_bhashya import convert_text, to_dev

TIKA_PATH = "suksma_tika_chapter_1_-_baladeva_vidyabhusana.docx"

PADA_BOUNDS = [(0, 186), (186, 280), (280, 430), (430, None)]

# (adhikarana count) per pada, matching PADA_ADHIKARANAS in
# rebuild_adhyaya1.py, used only to size each pada's cumulative boundaries.
# Pada 1 has 32 sutras but only 31 tika segments. Pratika word-matching
# confirms segments 1-19 (adhikarana 1-6) align 1:1 with sutras 1-19 with
# NO shift (e.g. "vikara iti" = segment 13 = sutra 13's own first word;
# "netara iti" = segment 16 = sutra 16's own first word) -- segment 15 is
# a trailing clause of segment 14's comment, not an independent gloss, but
# it still occupies its own numbered slot in the tika's sequence, so it
# does NOT shift anything after it. That means the missing sutra-worth of
# content is somewhere in adhikarana 11 (indra-prana, sutra 28-32, the
# last of the pada) instead -- tried assigning the deficit to adhikarana 6
# directly and it produced a verifiable, worse regression (a mid-sentence
# cut bleeding into adhikarana 7's block), so it's left here, at the tail
# end, where under-counting by one just shortens the last excerpt instead
# of corrupting a boundary.
PADA_ADHIKARANA_SUTRA_COUNTS = [
    [1, 1, 1, 1, 7, 8, 2, 1, 1, 4, 5],       # pada 1 (32 sutras nominal; 31 tika segments)
    [8, 2, 2, 7, 1, 4, 9],                    # pada 2 (33)
    [7, 2, 3, 1, 10, 2, 5, 3, 5, 2, 1, 2],     # pada 3 (43)
    [7, 3, 3, 2, 3, 4, 5, 1],                  # pada 4 (28)
]

_VYAKHYATAH_RE = re.compile(r"vyākhyātaḥ", re.IGNORECASE)
_MARKER_RE = re.compile(r"\|\|\s*\d+")


def get_pada_segments(texts, start, end):
    segs = []
    cur = []
    for i in range(start, end):
        t = texts[i].strip()
        if not t or _VYAKHYATAH_RE.search(t):
            continue
        cur.append(t)
        if _MARKER_RE.search(t):
            segs.append(" ".join(cur))
            cur = []
    return segs


def clean_segment_iast(seg: str) -> str:
    # Drop the tika's own citation-style prefix on segment 1 (invocation)
    # and any trailing "||N||" markers throughout.
    seg = re.sub(r"\|\|\s*\d+\s*\|\|?", "", seg)
    return seg.strip()


def main():
    doc = Document(TIKA_PATH)
    paras = list(iter_all_paragraphs(doc))
    texts = [paragraph_full_text(p) for p in paras]
    total_len = len(texts)

    bounds = [(0, 186), (186, 280), (280, 430), (430, total_len)]

    pada_adhikarana_blocks = []  # per pada: list of tika text blocks, one per adhikarana
    for p, (start, end) in enumerate(bounds):
        segs = get_pada_segments(texts, start, end)
        counts = PADA_ADHIKARANA_SUTRA_COUNTS[p]
        n_expected = sum(counts)
        n_actual = len(segs)
        deficit = n_expected - n_actual
        if deficit < 0:
            raise ValueError(f"pada {p+1}: tika has MORE segments ({n_actual}) than sutras ({n_expected})")

        # Walk adhikaranas in order, consuming `count` segments each; if we
        # run short near the end (deficit), the last adhikarana(s) simply
        # get fewer segments than sutras rather than raising -- this is the
        # documented pada-1 tolerance.
        blocks = []
        pos = 0
        for count in counts:
            take = min(count, len(segs) - pos)
            take = max(take, 0)
            block_segs = segs[pos:pos + take]
            pos += take
            blocks.append(" ".join(clean_segment_iast(s) for s in block_segs))
        pada_adhikarana_blocks.append(blocks)

    # adhikaranam 1 (pada 0, adhikarana index 0) is hand-built on the site
    # already -- still map its tika block, output separately for manual
    # splicing since it's not part of the automated adhyaya-1 body file.
    adhikaranam1_tika = pada_adhikarana_blocks[0][0]

    devanagari_blocks = []
    for p in range(4):
        for a_idx, block in enumerate(pada_adhikarana_blocks[p]):
            if p == 0 and a_idx == 0:
                continue  # handled separately (adhikaranam 1)
            dev = convert_text(block) if block.strip() else ""
            devanagari_blocks.append((p, a_idx, dev))

    with open("/tmp/tika_adhikaranam1.txt", "w", encoding="utf-8") as f:
        f.write(convert_text(adhikaranam1_tika) or "")

    with open("/tmp/tika_blocks.tsv", "w", encoding="utf-8") as f:
        for p, a_idx, dev in devanagari_blocks:
            f.write(f"{p}\t{a_idx}\t{dev}\n")

    print(f"wrote /tmp/tika_adhikaranam1.txt and /tmp/tika_blocks.tsv ({len(devanagari_blocks)} blocks)")


if __name__ == "__main__":
    main()
