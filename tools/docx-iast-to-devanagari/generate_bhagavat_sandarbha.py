#!/usr/bin/env python3
"""Extracts Bhagavat-sandarbha (the second of Jiva Gosvamin's six
Sandarbhas) from the source docx into a single site markdown file: one
'## अनुच्छेदः N' section per bracket-numbered anuccheda (renumbered
sequentially -- the source's own labels have decimal sub-parts like
"[10.1]".."[10.7]", collapsed here to plain whole numbers), followed by
ONE trailing '## श्री-सर्व-संवादिनी' section holding her entire continuous
commentary (Jiva Gosvamin's own auto-commentary) as a single block.

Pipeline is three explicit phases, in this order:
  1. separate_iast()  -- walk the docx once, in IAST, splitting content
     into anuccheda-mula vs sarva-samvadini WITHOUT transliterating yet.
  2. to_devanagari()   -- convert each side to Devanagari independently.
  3. main()'s merge loop -- assemble the converted anuccheda sections and
     the converted sarva-samvadini stream into the final markdown.

This docx's color coding does NOT mark separate commentator voices the way
tattva-sandarbha's does -- there is no "baladeva"/"vidyabhushana" anywhere
in the text, and every color turns out to mark a TYPE OF QUOTE, not an
author:
  DEFAULT/000000 = mula (root text) below SARVA_SAMVADINI_START_IDX
  0000FF/3366FF  = quoted Bhagavatam verse (mixed sources)
  800080         = quoted Bhagavatam verse (Bhagavata-purana only --
                   likely the verse currently under examination)
  008000/009900  = quoted citation of a traditional Bhagavata
                   commentator ("ṭīkā ca--...", e.g. Sridhara Svamin)
Quote colors are rendered as blockquotes wherever they land (mula tab
below the threshold, her trailing section at/above it).

Sarva-samvadini's own explicit "sarva-saṁvādinī:" label occurs only 7
times across ~5200 paragraphs. The two EARLY occurrences (indices 59, 67,
within anuccheda 1) are brief one-line asides -- content reverts to mula
immediately after, before the next anuccheda boundary -- and stay as a
small per-anuccheda "### सर्व-संवादिनी" tab. But starting at the label at
index 559 (right after anuccheda 10's own closing colophon), her voice
runs CONTINUOUSLY through the labels at 1203, 1713, 3307, 4449 (restatement
markers within one discourse, not zone restarts) to the end of the work --
and critically, that discourse does NOT track the "[N]" anuccheda sequence
1:1: she jumps back and forth referencing earlier/later vakya numbers in
prose (confirmed -- a passage discussing "the 45th statement" was found
landing inside whatever chunk the LAST "[N]" marker before it happened to
be, not anuccheda 45, purely from chunk position). So at/above that
threshold her prose AND the quotes she cites within it are collected into
one continuous stream in document order and rendered as a single trailing
section, not split across anucchedas.

Anuccheda boundaries are the docx's own standalone "[N]" / "[N.M]"
bracket markers (some anucchedas have numbered sub-parts, one of which is
a "[10..2]" double-dot typo in the source, tolerated by the regex below).
"""
import re
import sys
from collections import Counter

from docx import Document

sys.path.insert(0, ".")
from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text
from engines import transliterate_aksharamukha, normalize_avagraha_quotes, looks_like_sanskrit, has_mixed_language_run

DOCX_PATH = "sat-sandarbha_-_2_-_bhagavat_sandarbha_-_jiva_gosvamin.docx"

# Content range for the numbered-anuccheda portion: title/mangalacharanam
# through the LAST "[N]" anuccheda's own content. Mula's own text closes
# at idx 4975 ("samāpto'yaṁ śrī-śrī-bhagavat-sandarbhaḥ" follows at 4982)
# -- no more "[N]" anuccheda markers appear after that. CONTENT_END is
# capped at SARA_NISHKARSHA_HEADING_IDX (not the true end of her
# commentary) so anuccheda 102's own chunk doesn't swallow the separate
# sara-nishkarsha section that follows it (see below) as extra content of
# its own.
CONTENT_START = 46
CONTENT_END = 4990  # exclusive; == SARA_NISHKARSHA_HEADING_IDX

# The source docx has its own explicit heading "śrī-sarva-saṁvādinyāḥ
# śrī-jīva-gosvāmi-pāda-viracitāyāḥ sāra-niṣkarṣaḥ" (idx 4990) -- her own
# closing essence-summary, positioned after mula's closing colophon and
# before her own separate closing colophon. Content runs 4992..5007 (the
# summary prose ends there); right after it (idx 5009, 5011) the source
# has its own two-line title -- "śrī-sarva-saṁvādinī" / "bhagavat-
# sandarbhānuvyākhyā" -- introducing a further excerpt of her running
# commentary (see SARVA_SAMVADINI_ANUVYAKHYA below), which is a distinct
# section, not a continuation of the summary itself.
SARA_NISHKARSHA_HEADING_IDX = 4990
SARA_NISHKARSHA_START = 4992
SARA_NISHKARSHA_END = 5008  # exclusive -- her two-line title starts at idx 5009

# Her own two-line title (idx 5009 "śrī-sarva-saṁvādinī", idx 5011
# "bhagavat-sandarbhānuvyākhyā") introduces this excerpt; content runs
# 5014 up to her own closing colophon at idx 5171-5172 (exclusive of it).
SARVA_SAMVADINI_ANUVYAKHYA_START = 5014
SARVA_SAMVADINI_ANUVYAKHYA_END = 5171  # exclusive -- her closing colophon starts here

# Right after her closing colophon (idx 5171-5172), the source has an
# explicit "Appendix" heading (idx 5174) starting a genuine supplementary
# discussion (no "sarva-saṁvādinī:" label appears in it -- treated as
# mula) -- a further discourse on viśuddha-sattva quoting several verses,
# same treatise voice as the rest of the work. It ends at idx 5253; right
# after that (idx 5255-56, "BHAGAVAT-SANDARBHA" / "174") is a page marker
# followed by the page-numbered editorial footnote apparatus (English
# textual-critical notes comparing published editions) -- not treatise
# content, excluded.
APPENDIX_START = 5176
APPENDIX_END = 5254  # exclusive

# See module docstring. Below this index, mula/quoted split by color as
# normal; at/above it, non-quote content is sarva-samvadini's voice.
SARVA_SAMVADINI_START_IDX = 559
# The two early explicit "sarva-saṁvādinī:" labels that are brief asides,
# not the start of the extended zone (content reverts to mula right after
# each, well before SARVA_SAMVADINI_START_IDX).
EARLY_SARVA_SAMVADINI_INDICES = {59, 67}

COLOR_MAP = {
    "DEFAULT": "mula",
    "000000": "mula",
    "0000FF": "quoted",
    "3366FF": "quoted",
    # 008000/009900 (green): sampled paragraphs are all citations of
    # traditional Bhagavata commentators ("tika ca--...", i.e. Sridhara
    # Svamin etc., quoted by Jiva Gosvamin as supporting authority), not a
    # commentary voice of this Sandarbha itself -- treated as quoted too.
    "008000": "quoted",
    "009900": "quoted",
    # 800080 (purple) was initially assumed to mean Baladeva's tika, by
    # analogy with tattva-sandarbha's color convention -- but there is no
    # "baladeva"/"vidyabhushana" anywhere in this docx, every purple
    # paragraph checked is verse (never explanatory prose), and purple
    # citations are Bhagavata-purana only (124/124 sampled) vs blue's mix
    # of sources. It marks the Bhagavatam verse currently under
    # discussion, not a commentator -- treated as quoted material too.
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


_ANUCCHEDA_RE = re.compile(r"^\[(\d+)(?:\.+(\d+))?\]$")  # source has one "[10..2]" double-dot typo
# Matched against the IAST source text, before transliteration -- not
# against the converted Devanagari. The label sometimes opens with an
# inline "[N]" self-reference to another vakya number (not a real
# anuccheda boundary -- N doesn't match the paragraph's actual position)
# before "sarva-saṁvādinī:" itself; strip both.
_SARVA_PREFIX_RE = re.compile(r"^(?:\[\d+\]\s*)?sarva-sa[mṁ]v[āa]din[īi]\s*[:।]\s*", re.IGNORECASE)


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
    Decimal sub-parts (e.g. "[10.1]".."[10.7]") are NOT separate
    anucchedas -- they're numbered sub-divisions of content within one
    anuccheda's citation block, merged here into a single "## अनुच्छेदः N".
    Returns (chunks, marker_indices); chunks is [(label, start, end), ...]
    with label=None for the mangalacharanam chunk before the first marker.
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


def separate_iast(orig_para_objs, orig_paras, chunks, marker_indices):
    """Phase 1: walk the docx ONCE, in IAST, and separate content into two
    independent collections -- no transliteration yet. Returns:
      anuccheda_iast: [(label, [(text, is_quoted), ...]), ...] in order,
                      label=None for mangalacharanam
      early_aside_iast: {label: [text, ...]} -- the two brief asides at
                      idx 59/67, kept attached to their own anuccheda
      sarva_iast: [(text, is_quoted), ...] -- her continuous discourse,
                      document order, spanning anuccheda boundaries
    """
    anuccheda_iast = []
    early_aside_iast = {}
    sarva_iast = []  # (text, is_quoted), is_sarva-zone content, doc order

    for label, start, end in chunks:
        mula_parts = []
        for idx in range(start, end):
            if idx in marker_indices:
                continue  # a sub-part "[N.M]" marker mid-chunk, not content
            t = orig_paras[idx].strip()
            if not t or "o)0(o" in t:
                continue

            m = _SARVA_PREFIX_RE.match(t)
            if m:
                t = t[m.end():]

            color = para_dominant_color(orig_para_objs[idx])
            is_quoted = COLOR_MAP.get(color, "mula") == "quoted"

            if idx in EARLY_SARVA_SAMVADINI_INDICES:
                early_aside_iast.setdefault(label, []).append(t)
            elif idx >= SARVA_SAMVADINI_START_IDX:
                sarva_iast.append((t, is_quoted))
            else:
                mula_parts.append((t, is_quoted))
        anuccheda_iast.append((label, mula_parts))

    return anuccheda_iast, early_aside_iast, sarva_iast


def to_devanagari(parts):
    """Phase 2: convert a list of (iast_text, is_quoted) to
    (devanagari_text, is_quoted), dropping any paragraph that doesn't
    survive convert_text (non-Sanskrit / mixed-language)."""
    out = []
    for t, is_quoted in parts:
        conv = convert_text(t)
        if conv:
            out.append((conv, is_quoted))
    return out


def main():
    doc = Document(DOCX_PATH)
    orig_para_objs = list(iter_all_paragraphs(doc))
    orig_paras = [paragraph_full_text(p).strip() for p in orig_para_objs]

    chunks, marker_indices = find_chunks(orig_paras)

    # Phase 1: separate anuccheda-mula from sarva-samvadini, still in IAST.
    anuccheda_iast, early_aside_iast, sarva_iast = separate_iast(
        orig_para_objs, orig_paras, chunks, marker_indices
    )

    # Phase 2: convert each side to Devanagari independently.
    anuccheda_dev = [(label, to_devanagari(parts)) for label, parts in anuccheda_iast]
    early_aside_dev = {
        label: [d for d in (convert_text(t) for t in texts) if d]
        for label, texts in early_aside_iast.items()
    }
    sarva_dev = to_devanagari(sarva_iast)

    # Phase 3: merge into the final site markdown.
    out_lines = []
    anuccheda_counter = 0
    for label, mula_parts in anuccheda_dev:
        aside_parts = early_aside_dev.get(label, [])

        if label is None and not mula_parts and not aside_parts:
            continue  # only mangalacharanam can legitimately have nothing

        if label is None:
            heading = "## मङ्गलाचरणम्"
        else:
            anuccheda_counter += 1
            heading = f"## अनुच्छेदः {to_dev(anuccheda_counter)}"
        out_lines.append(heading)
        out_lines.append("")
        if mula_parts:
            out_lines.append(render_parts(mula_parts))
            out_lines.append("")
        if aside_parts:
            out_lines.append("### सर्व-संवादिनी")
            out_lines.append("")
            out_lines.append("\n\n".join(aside_parts))
            out_lines.append("")

    if sarva_dev:
        out_lines.append("## श्री-सर्व-संवादिनी")
        out_lines.append("")
        out_lines.append(render_parts(sarva_dev))
        out_lines.append("")

    body = "\n".join(out_lines)
    body = re.sub(r"\n{3,}", "\n\n", body)
    with open("/tmp/bhagavat_sandarbha_body.md", "w", encoding="utf-8") as f:
        f.write(body)

    n_sections = sum(1 for l in out_lines if l.startswith("## "))
    print(f"wrote /tmp/bhagavat_sandarbha_body.md, {n_sections} sections", file=sys.stderr)


if __name__ == "__main__":
    main()
