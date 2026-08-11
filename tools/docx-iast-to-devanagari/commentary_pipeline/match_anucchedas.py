"""Anchors the site's existing per-anuccheda root-quote text to positions
in a docx's paragraph sequence, via content-matching rather than trusting
either source's own numbering (the site uses one continuous 1..N count;
the docx re-starts per-prakarana; neither is reliable input to the other).

Matching is normalized-substring based: strip markdown/citation/hyphen
noise from both sides, then search forward through the docx's paragraph
stream (never backward -- anucchedas are read in order) for each site
anuccheda's root-quote text in turn.
"""

import re
from dataclasses import dataclass

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")


def normalize_for_matching(text: str) -> str:
    """Strip everything that's allowed to differ between the docx's raw
    transliteration and the site's hand-typeset prose: markdown syntax,
    citation brackets, parenthetical notes, hyphens, punctuation,
    whitespace. What's left is bare Devanagari letters, which is what
    should actually agree between the two sources.
    """
    t = text
    # A leading bold-only line is a topic-name label some sections carry
    # (e.g. "**व्यास-चित्तनुगत्वम्**", "**आत्म-स्तुतिः**") -- these are the
    # site's own editorial headers, not part of the underlying Sanskrit,
    # so they have no counterpart in the docx and must be dropped before
    # searching (confirmed against the two anucchedas that otherwise
    # failed to match: 16 and 24, both carrying exactly this pattern).
    t = re.sub(r"^\s*\*\*[^\n*]+\*\*\s*\n", "", t)
    t = re.sub(r"^\s*>+\s*", "", t, flags=re.MULTILINE)  # blockquote markers
    t = re.sub(r"\*\*|\*|_", "", t)  # markdown emphasis
    t = re.sub(r"\[[^\]]*\]", "", t)  # citation brackets [भा.पु. ...]
    t = re.sub(r"\([^)]*\)", "", t)  # parenthetical notes (नमः N)
    # keep only Devanagari letters (drops hyphens, daṇḍa, digits, latin,
    # whitespace, and em-dashes -- no separate em-dash strip needed here,
    # an earlier version tried to strip "trailing citation after em-dash"
    # with `—.*$` in MULTILINE mode, which doesn't actually stay
    # "trailing": this text uses em-dash constantly as ordinary mid-
    # paragraph punctuation introducing a quote (e.g. "āhuḥ—", "yathā—"),
    # so that regex silently deleted everything after the first such dash
    # on each line -- verified: it undercounted a real site paragraph by
    # thousands of characters, corrupting content-length comparisons.
    t = "".join(_DEVANAGARI_RE.findall(t))
    return t


@dataclass
class AnucchedaMatch:
    anuccheda_num: int
    found: bool
    docx_start_para: int | None = None
    match_length: int | None = None  # normalized chars matched


def build_docx_search_index(tagged_paras):
    """tagged_paras: list of (paragraph_index, tag, text) as produced by
    color_tags.tagged_paragraphs(). Returns (big_normalized_string,
    offset_to_paragraph_index) where offset_to_paragraph_index maps each
    character offset in the big string back to the paragraph it came
    from (for locating match positions).
    """
    pieces = []
    offset_map = []  # parallel list: offset_map[i] = paragraph_index for pieces up to char i
    big = []
    pos = 0
    for para_idx, tag, text in tagged_paras:
        norm = normalize_for_matching(text)
        if not norm:
            continue
        big.append(norm)
        offset_map.append((pos, pos + len(norm), para_idx))
        pos += len(norm)
    return "".join(big), offset_map


def _offset_to_para(offset_map, char_offset):
    for start, end, para_idx in offset_map:
        if start <= char_offset < end:
            return para_idx
    return offset_map[-1][2] if offset_map else None


def match_all(sections, big_string, offset_map, min_match_len=12):
    """sections: list of site_content.AnucchedaSection, in order.
    Returns list[AnucchedaMatch], one per section, searching strictly
    forward through big_string as sections are processed in order.
    """
    results = []
    search_from = 0
    for section in sections:
        query = normalize_for_matching(section.root_quote)
        if len(query) < min_match_len:
            # too short a root-quote to search reliably (e.g. a bare
            # citation with no real verse text) -- try anyway but note
            # it's a weak match if found.
            pass
        found_at = big_string.find(query, search_from) if query else -1
        if found_at == -1 and len(query) > min_match_len:
            # retry with a shorter prefix in case of a minor mismatch
            # (e.g. one differing syllable) partway through a long quote
            prefix = query[:min_match_len]
            found_at = big_string.find(prefix, search_from)
        if found_at == -1:
            results.append(AnucchedaMatch(anuccheda_num=section.anuccheda_num, found=False))
            continue
        para_idx = _offset_to_para(offset_map, found_at)
        results.append(
            AnucchedaMatch(
                anuccheda_num=section.anuccheda_num,
                found=True,
                docx_start_para=para_idx,
                match_length=len(query),
            )
        )
        search_from = found_at + max(1, len(query) // 2)
    return results
