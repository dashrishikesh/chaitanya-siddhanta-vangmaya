#!/usr/bin/env python3
"""Shared constants and helpers for extracting Paramatma-sandarbha (the
third of Jiva Gosvamin's six Sandarbhas, "sarva-saṁvādinī-samupetaḥ" per
its own title page) into the site. Same overall shape and methodology as
Bhagavat-sandarbha's pipeline (see generate_bhagavat_sandarbha.py,
split_bhagavat_sandarbha.py, build_bhagavat_sandarbha_site.py):

  1. split_paramatma_sandarbha.py splits the source docx into physical
     IAST docx files -- one anuccheda-mula file (each of the 110
     anuccheda built ENTIRELY from its own "[N]" marker range) and one
     sarva-samvadini file (her voice, per anuccheda, detected ONLY via
     her own literal "sarva-saṁvādinī:" label within that range -- not
     color, not a paragraph-index threshold; both were tried for
     Bhagavat-sandarbha and both mis-attributed content).
  2. convert_no_hyphen_join.py converts each split file to Devanagari
     independently, preserving hyphens.
  3. build_paramatma_sandarbha_site.py zips the converted files back
     together per anuccheda and assembles the site markdown, rendering
     her voice as a "### सर्व-संवादिनी" subsection inside its own
     anuccheda's section.

This docx's color coding matches Bhagavat-sandarbha's: no color marks a
separate commentator (no "baladeva"/"vidyabhushana" text anywhere) --
DEFAULT/000000 is unquoted prose, 0000FF/800080/008000 are all quoted
material (verses or citations), rendered as blockquotes.
"""
import re
from collections import Counter

from engines import transliterate_aksharamukha, normalize_avagraha_quotes, looks_like_sanskrit, has_mixed_language_run

DOCX_PATH = "sat-sandarbha_-_3_-_paramatma_sandarbha_-_jiva_gosvamin.docx"

# Content range for the numbered-anuccheda portion: the docx's own
# (second) title block through mula's own closing colophon
# ("samāpto'yaṁ tṛtīyaḥ sandarbhaḥ", idx 3337) and its closing verse
# couplet, ending at idx 3339 (the "…" separator right after it). No
# more "[N]" anuccheda markers appear after idx 3301 (the [110] marker).
# Right after this range (idx 3341), the source has her own one-line
# title ("sarva-saṁvādinī śrī-paramātma-sandarbhānuvyākhyā") introducing
# a further excerpt of her commentary (see below) -- a distinct section,
# excluded from anuccheda 110's own range so it isn't swallowed as extra
# content of that anuccheda.
CONTENT_START = 25
CONTENT_END = 3340  # exclusive

# Her own one-line title (idx 3341) introduces a further excerpt of her
# running commentary; content runs 3346..3359 (exclusive of idx 3360's
# "—o)0(o—" separator, right after which idx 3365 has a
# "PARAMĀTMA-SANDARBHA" page marker followed by the page-numbered
# editorial footnote apparatus -- not treatise content, excluded).
# Unlike Bhagavat-sandarbha, this docx has no separate closing
# "sāra-niṣkarṣa" essence-summary section.
SARVA_SAMVADINI_ANUVYAKHYA_HEADING_IDX = 3341
SARVA_SAMVADINI_ANUVYAKHYA_START = 3346
SARVA_SAMVADINI_ANUVYAKHYA_END = 3360  # exclusive

COLOR_MAP = {
    "DEFAULT": "mula",
    "000000": "mula",
    "0000FF": "quoted",
    "3366FF": "quoted",
    "008000": "quoted",
    "009900": "quoted",
    "339933": "quoted",
    "800080": "quoted",
    "FF0000": "mula",  # single stray mis-colored character, negligible
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
# "sarva-saṁvādinī:" itself; strip both.
_SARVA_PREFIX_RE = re.compile(r"^(?:\[[\d\-]+\]\s*)?sarva-sa[mṁ]v[āa]din[īi]\s*[:।]\s*", re.IGNORECASE)


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
    chunk before the first marker.
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
