"""Color-based commentator tagging, reusable across all six Sandarbhas.

Each Sandarbha docx color-codes which commentator wrote which passage
(see the docx's own front-matter legend). The exact hex values differ
per edition, so callers pass in a COLOR_MAP; this module only knows how
to (a) find each paragraph's dominant color and (b) group consecutive
same-tag paragraphs into blocks.
"""

import os
import sys
from collections import Counter
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text

MULA_TAG = "mula"
QUOTED_TAG = "quoted"


def paragraph_dominant_color(paragraph) -> str:
    """Hex color (e.g. '800080') of the majority of a paragraph's
    non-whitespace characters, or 'DEFAULT' if no run has an explicit
    color (this is how the bulk of the plain root-text paragraphs are
    formatted -- no explicit rPr color, inherits document default black).
    """
    counts = Counter()
    for run in paragraph.runs:
        text = run.text
        if not text.strip():
            continue
        color = run.font.color
        key = str(color.rgb) if (color is not None and color.rgb is not None) else "DEFAULT"
        counts[key] += len(text)
    if not counts:
        return "DEFAULT"
    return counts.most_common(1)[0][0]


def paragraph_tag(paragraph, color_map: dict) -> str:
    dominant = paragraph_dominant_color(paragraph)
    return color_map.get(dominant, f"OTHER:{dominant}")


@dataclass
class Block:
    tag: str
    start_para: int
    end_para: int
    texts: list = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.texts)


def tagged_paragraphs(original_doc, converted_doc, color_map: dict):
    """Zip the original docx (for color) with the converted docx (for
    Devanagari text) by paragraph index -- both were produced by
    convert.py's 1:1, count-preserving walk, so index i in one
    corresponds to index i in the other.

    Yields (paragraph_index, tag, devanagari_text) for every non-empty
    paragraph, skipping paragraphs with no text in the converted doc.
    """
    orig_paras = list(iter_all_paragraphs(original_doc))
    conv_paras = list(iter_all_paragraphs(converted_doc))
    if len(orig_paras) != len(conv_paras):
        raise ValueError(
            f"Paragraph count mismatch: original={len(orig_paras)} "
            f"converted={len(conv_paras)} -- are these really the same document?"
        )
    for i, (orig_p, conv_p) in enumerate(zip(orig_paras, conv_paras)):
        text = paragraph_full_text(conv_p).strip()
        if not text:
            continue
        tag = paragraph_tag(orig_p, color_map)
        yield i, tag, text


def segment_into_blocks(tagged_paras) -> list:
    """Group consecutive paragraphs sharing the same tag into Blocks."""
    blocks = []
    cur = None
    for idx, tag, text in tagged_paras:
        if cur is None or cur.tag != tag:
            if cur is not None:
                blocks.append(cur)
            cur = Block(tag=tag, start_para=idx, end_para=idx, texts=[text])
        else:
            cur.end_para = idx
            cur.texts.append(text)
    if cur is not None:
        blocks.append(cur)
    return blocks
