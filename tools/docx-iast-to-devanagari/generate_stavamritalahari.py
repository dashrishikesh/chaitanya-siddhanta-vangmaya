#!/usr/bin/env python3
"""Extracts Vishvanatha Chakravartin's Stavamritalahari (a 28-poem stotra
anthology) from sanskritdocuments.org's ITX source
(stavAmRRitalaharIsangraha.itx), following the same approach as
generate_stavamala_from_itx.py for Rupa Gosvamin's Stavamala.

Structure:
  \\chapter{##(N) English title## .. (N) itrans-title ..}   -- one per
    poem; the leading "(N)" in each half is the work's own front-matter
    numbering (matches its table of contents) and is stripped before
    building the site heading.
  \\section{(N)}                                             -- marks
    the N-th item within the two poems that are themselves internally
    numbered anthologies: Nikunjakelivirudavali (16 items) and
    Gitavali 2 (11 items).
  "iti ... virachita[mMHA] ... samApta[mMHA]/sampUrNa[mMHA]"  -- a
    colophon closing each poem, repeating the poem's own name and
    author; kept (not dropped) as an italicized closing line, matching
    this project's Stavamala convention. The colophon-start signal here
    is any line beginning "iti " that contains "virachit" (the
    consistent structural marker across all its several worded variants
    in this source, verified against every one of its 29 occurrences --
    28 per-poem plus the work's own closing colophon at the very end).
  One one-off glitch: chapter 28 (Gitavali 2)'s opening verse ends in a
    truncated "|| dhR^i||" fragment (not a real verse-end marker or
    metre caption -- just a source-level typo/truncation, verified by
    inspection), stripped here.

Verses are split into their own blank-line-separated paragraphs (the
source runs a whole poem together with no blank lines at all), matching
generate_stavamala_from_itx.py's add_verse_breaks() convention for a
chantable reading rhythm.
"""
import re

from aksharamukha import transliterate

ITX_PATH = "stavamritalahari.itx"
END_MARKER = "Please send corrections to sanskrit@cheerful.com"

_CHAPTER_RE = re.compile(r"^\\chapter\{##(.+?)##\s*\.\.\s*(.+?)\s*\.\.\}$")
_SECTION_RE = re.compile(r"^\\section\{\(?(\d+)\)?\}$")
_LEADING_NUM_RE = re.compile(r"^\((\d+)\)\s*(.+)$")
_TRAILING_NUM_RE = re.compile(r"^(.*?)\s+(\d+)$")
_COLOPHON_START_RE = re.compile(r"^iti\s.*virachit", re.IGNORECASE)
_COLOPHON_END_RE = re.compile(
    r"(samAptam|samAptA|samAptaH|sampUrNam|sampUrNaH|sampUrNA)\s*\|{1,2}\s*$"
)
_VERSE_END_RE = re.compile(r"\|\|\s*\d+\|\|\s*$")
_STANDALONE_MARKER_RE = re.compile(r"^(\|\|.*\|\||\(.*\))$")
# One-off source glitch: a truncated "|| dhR^i||" fragment at the end of
# Gitavali 2's opening verse (not a real verse-end marker or caption).
_STRAY_GLITCH_RE = re.compile(r"\s*\|\|\s*dhR\^i\|\|\s*$")

DEVNUMS = "०१२३४५६७८९"


def to_dev(n) -> str:
    return "".join(DEVNUMS[int(d)] for d in str(n))


def convert(text: str) -> str:
    return transliterate.process("ITRANS", "Devanagari", text)


def dehyphenate(lines):
    """Rejoins a "...\\-" line with the line(s) that follow, no space, up
    until a line that doesn't end in "\\-" -- a single pada's printed
    line-wrap, not a new pada."""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        while line.rstrip().endswith("\\-"):
            i += 1
            line = line.rstrip()[:-2] + lines[i].strip()
        out.append(line)
        i += 1
    return out


def add_verse_breaks(lines):
    """Inserts a blank-line paragraph break after every numbered
    verse-end marker and after every standalone metre-name caption line,
    so each verse renders as its own paragraph (blank-line separated)."""
    out = []
    n = len(lines)
    for i, line in enumerate(lines):
        out.append(line)
        stripped = line.strip()
        if _VERSE_END_RE.search(stripped) or _STANDALONE_MARKER_RE.match(stripped):
            nxt = lines[i + 1].strip() if i + 1 < n else ""
            if nxt != "":
                out.append("")
    return out


def split_paragraphs(lines):
    paragraphs = []
    current = []
    for line in lines:
        if line.strip() == "":
            if current:
                paragraphs.append(current)
                current = []
        else:
            current.append(line.strip())
    if current:
        paragraphs.append(current)
    return paragraphs


def render_body(lines):
    paragraphs = split_paragraphs(lines)
    rendered = []
    for para in paragraphs:
        converted = [convert(l) for l in para]
        rendered.append("  \n".join(converted))
    return "\n\n".join(rendered)


def parse_chapter_title(raw_title: str):
    """raw_title is the itrans-title half of a \\chapter{##Eng## ..itrans..}
    line, e.g. "(1) shrIgurudevAShTakam" or "(25) shrIvR^indAvanAShTakam
    2". Strips the work's own leading "(N)" front-matter number, then
    splits off a trailing bare number (disambiguating a repeated title,
    e.g. Vrindavanashtakam 2) the same way Stavamala's pipeline does."""
    m = _LEADING_NUM_RE.match(raw_title)
    if m:
        raw_title = m.group(2)
    m2 = _TRAILING_NUM_RE.match(raw_title)
    if m2:
        return convert(m2.group(1)), int(m2.group(2))
    return convert(raw_title), None


def main():
    with open(ITX_PATH, encoding="utf-8") as f:
        raw_lines = f.read().split("\n")

    start = next(i for i, l in enumerate(raw_lines) if _CHAPTER_RE.match(l.strip()))
    end = next(i for i, l in enumerate(raw_lines) if l.strip() == END_MARKER)
    lines = add_verse_breaks(dehyphenate(raw_lines[start:end]))

    sections = []  # (heading, body_lines)
    heading = None
    chapter_base = None
    item_counter = 0
    body = []

    def flush():
        text = render_body(body)
        if text.strip():
            sections.append((heading, text))

    in_colophon = False
    colophon_buf = []
    for line in lines:
        stripped = _STRAY_GLITCH_RE.sub("", line.strip())
        if in_colophon:
            colophon_buf.append(stripped)
            if _COLOPHON_END_RE.search(stripped):
                in_colophon = False
                body.append("*" + " ".join(colophon_buf) + "*")
                colophon_buf = []
            continue
        if _COLOPHON_START_RE.match(stripped):
            if _COLOPHON_END_RE.search(stripped):
                body.append("*" + stripped + "*")
            else:
                in_colophon = True
                colophon_buf = [stripped]
            continue
        m_chap = _CHAPTER_RE.match(stripped)
        m_sec = None if m_chap else _SECTION_RE.match(stripped)
        if m_chap:
            flush()
            body = []
            base, num = parse_chapter_title(m_chap.group(2).strip())
            # chapter_base folds in the chapter's own trailing
            # disambiguator (e.g. "Gitavali 2"'s "2") so that a
            # multi-item chapter's per-item headings read "...2 1",
            # "...2 2" -- not a bare "...1" indistinguishable from an
            # unrelated same-named chapter's own item 1.
            chapter_base = base if num is None else f"{base} {to_dev(num)}"
            item_counter = 0
            heading = chapter_base
            continue
        if m_sec:
            flush()
            body = []
            item_counter += 1
            heading = f"{chapter_base} {to_dev(item_counter)}"
            continue
        body.append(stripped)
    flush()

    body_parts = [f"## {heading}\n\n{text}" for heading, text in sections]
    with open("/tmp/stavamritalahari_body.md", "w", encoding="utf-8") as f:
        f.write("\n\n".join(body_parts))
    print(f"wrote /tmp/stavamritalahari_body.md, {len(body_parts)} sections")


if __name__ == "__main__":
    main()
