#!/usr/bin/env python3
"""Shared constants and helpers for extracting Krishna-sandarbha (the
fourth of Jiva Gosvamin's six Sandarbhas) into the site. Same overall
shape and methodology as Bhagavat-sandarbha's and Paramatma-sandarbha's
pipelines (see generate_paramatma_sandarbha.py):

  1. split_krishna_sandarbha.py splits the source docx into physical
     IAST docx files -- one anuccheda-mula file (each of the 181
     anuccheda built ENTIRELY from its own "[N]" marker range) and one
     sarva-samvadini file (her voice, per anuccheda, detected ONLY via
     her own literal "sarva-saṁvādinī:" label within that range -- not
     color, not a paragraph-index threshold).
  2. convert_no_hyphen_join.py converts each split file to Devanagari
     independently, preserving hyphens.
  3. build_krishna_sandarbha_site.py zips the converted files back
     together per anuccheda and assembles the site markdown, rendering
     her voice as a "### सर्व-संवादिनी" subsection inside that same
     anuccheda's section.

Source-file note: the docx as originally supplied had a corrupted image
relationship (word/_rels/document.xml.rels had a <Relationship> whose
Target was the literal string "NULL", which made python-docx's loader
raise a KeyError while resolving package parts). The committed docx here
is a patched copy (the broken relationship retargeted at a 1x1 PNG
placeholder embedded in the archive, and that extension registered in
[Content_Types].xml) -- no paragraph/text content was touched, so
patching didn't affect extraction, it just made the file openable at
all.

Version note in the source itself ("3.04 Sarva-saṁvādinī completed and
integrated to the text", idx 43): unlike Bhagavat-sandarbha and
Paramatma-sandarbha, this edition's sarva-saṁvādinī commentary is fully
merged into the main flow throughout, with no separate closing excerpt
after mula's own colophon -- so unlike those two, there is no
SARVA_SAMVADINI_ANUVYAKHYA range here.

Anuccheda numbering has a genuine gap in the source: [145] is followed
directly by [153] (no [146]-[152] anywhere in the docx) -- tolerated as-
is, not renumbered, matching this project's standing rule of trusting
the source's own numbering over inventing a "corrected" sequence.

This docx's color coding follows the same non-diagnostic pattern as the
other Sandarbhas -- no color marks a separate commentator -- but adds a
few more color values (990033, 800000, 993366, 6600FF, 7F7F7F) beyond
the ones seen in Bhagavat-sandarbha/Paramatma-sandarbha, all quoted-verse
variants. Rather than whitelist every color as "quoted" one at a time,
COLOR_MAP here whitelists the MULA colors (default/black) and treats
everything else as "quoted" by default -- safer against further color
variety in this text than an ever-growing quoted-color list.
"""
import re
from collections import Counter

from engines import transliterate_aksharamukha, normalize_avagraha_quotes, looks_like_sanskrit, has_mixed_language_run

# Patched copy of the source docx (image-relationship fix) -- see module docstring.
DOCX_PATH = "sat-sandarbha_-_4_-_krishna_sandarbha_-_jiva_gosvamin.docx"

# Content range: the docx's own title ("śrī-kṛṣṇa-sandarbhaḥ", idx 47)
# through mangalacharanam, to mula's own closing statement
# ("samāpto'yaṁ śrī-kṛṣṇa-sandarbhaḥ ||", idx 4733) -- right after it
# (idx 4735-37) the source has a "Śrī-Kṛṣṇa-sandarbhaḥ" / "1| Page" page
# header starting the page-numbered editorial footnote apparatus
# (English + Sanskrit textual-critical notes), excluded. Unlike
# Bhagavat-sandarbha, there's no separate sāra-niṣkarṣa or trailing
# sarva-saṁvādinī excerpt here -- her voice is fully integrated inline
# (see module docstring), and all 28 of her "sarva-saṁvādinī:" labels
# fall well inside this range (max idx 3250).
CONTENT_START = 47
CONTENT_END = 4734  # exclusive

COLOR_MAP = {
    "DEFAULT": "mula",
    "000000": "mula",
    "FF0000": "mula",  # single stray mis-colored character, negligible (same as other Sandarbhas)
}

_CONVERT_CACHE = {}


def convert_text(iast_text: str):
    if iast_text in _CONVERT_CACHE:
        return _CONVERT_CACHE[iast_text]
    if not looks_like_sanskrit(iast_text) or has_mixed_language_run(iast_text):
        _CONVERT_CACHE[iast_text] = None
        return None
    out = transliterate_aksharamukha(normalize_avagraha_quotes(iast_text))
    _CONVERT_CACHE[iast_text] = out
    return out


DEVNUMS = "०१२३४५६७८९"


def to_dev(n) -> str:
    return "".join(DEVNUMS[int(d)] for d in str(n))


_ANUCCHEDA_RE = re.compile(r"^\[(\d+)(?:\.+(\d+))?\]$")
# Matched against the IAST source text, before transliteration. The label
# sometimes opens with an inline "[N]" or "[N-M]" self-reference to
# another vakya number (not a real anuccheda boundary) before
# "sarva-saṁvādinī:" itself; strip both. This docx also has at least one
# label wrapped in its own stray, never-closed "[" (idx 1493:
# "[sarva-saṁvādinī: atha śṛṇu nārada ..." with no matching "]" anywhere
# nearby) -- tolerated the same way as the "[10..2]" double-dot marker
# typo elsewhere in this project: a bare optional "[" is allowed
# immediately before the label too, separate from the digit-bracket case.
_SARVA_PREFIX_RE = re.compile(r"^(?:\[[\d\-]+\]\s*)?\[?\s*sarva-sa[mṁ]v[āa]din[īi]\s*[:।]\s*", re.IGNORECASE)


def para_dominant_color(p):
    counts = Counter()
    for r in p.runs:
        t = r.text
        if not t.strip():
            continue
        c = r.font.color
        key = str(c.rgb) if (c is not None and c.rgb is not None) else "DEFAULT"
        counts[key] += len(t)
    if not counts:
        return "DEFAULT"
    return counts.most_common(1)[0][0]


def is_quoted_color(color: str) -> bool:
    return COLOR_MAP.get(color, "quoted") == "quoted"


def render_parts(parts):
    """parts: list of (text, is_quoted). Groups consecutive quoted lines
    into one blockquote, non-quoted lines into paragraphs."""
    out = []
    i = 0
    n = len(parts)
    while i < n:
        text, quoted = parts[i]
        if quoted:
            block = [text]
            i += 1
            while i < n and parts[i][1]:
                block.append(parts[i][0])
                i += 1
            out.append("> " + "  \n> ".join(block))
        else:
            out.append(text)
            i += 1
    return "\n\n".join(out)


def find_chunks(orig_paras):
    """Every "[N]" / "[N.M]" marker index, with its major anuccheda number.
    Decimal sub-parts are NOT separate anucchedas -- merged into a single
    "## अनुच्छेदः N". Returns (chunks, marker_indices); chunks is
    [(label, start, end), ...] with label=None for the mangalacharanam
    chunk before the first marker. Tolerates the source's own [145]->[153]
    gap (see module docstring) -- that chunk simply runs longer.
    """
    markers = []
    for i in range(CONTENT_START, CONTENT_END):
        m = _ANUCCHEDA_RE.match(orig_paras[i])
        if m:
            markers.append((i, int(m.group(1))))
    marker_indices = {i for i, _ in markers}

    major_boundaries = []  # (start_marker_idx, major), first occurrence only
    seen_majors = set()
    for i, major in markers:
        if major not in seen_majors:
            seen_majors.add(major)
            major_boundaries.append((i, major))

    chunks = [(None, CONTENT_START, major_boundaries[0][0])]
    for bi in range(len(major_boundaries)):
        start = major_boundaries[bi][0] + 1
        end = major_boundaries[bi + 1][0] if bi + 1 < len(major_boundaries) else CONTENT_END
        chunks.append((major_boundaries[bi][1], start, end))
    return chunks, marker_indices
