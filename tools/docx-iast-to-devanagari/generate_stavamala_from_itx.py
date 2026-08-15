#!/usr/bin/env python3
"""Extracts Rupa Gosvamin's Stavamala from sanskritdocuments.org's ITX
source (stavamAlAsangraha.itx) -- the actual ITRANS/LaTeX typesetting
source used to generate the PDF the site's earlier pipeline
(generate_stavamala.py) extracted from via pdftotext.

Replaces the PDF-based pipeline: PDF text extraction lost some
word-spacing at page-internal line-wrap points (e.g. anuccheda 4 of
chaitanyAShTakam 1, "abhibhavann A~NgikaruchA", came out of the PDF as
one merged word with no space -- not a pdftotext bug, the space is
simply gone from the PDF's own text layer, but present correctly in
this ITX source) -- so any verse whose original line happened to wrap
across a printed page-line at that exact point could be quietly
corrupted, and there was no way to detect or fix this from the PDF
alone. The ITX has no such artifacts: it's the actual per-pada line
structure the PDF was typeset from, with explicit "\\-" markers where a
single (long) pada's PRINTED line had to wrap -- rejoined here with no
space, vs. every other line break, which is a real new pada/line
getting its own hard markdown break.

Structure:
  \\chapter{##English title## .. itrans-title ..}   -- one per poem,
    except three anthologies (Chando'shtadashakam / Gitavali / Shri
    Govindavirudavali) that each contain multiple items internally.
  \\section{N}                                       -- marks the N-th
    item within one of those three multi-item chapters.
  "iti shrIrUpagosvAmivirachitastavamAlAyAM ... samAptam/samAptA/
    samAptaH/sampUrNam/sampUrNaH" -- a colophon repeating the poem's own
    name at its end, sometimes wrapping across two physical lines;
    dropped (matches generate_stavamala.py's PDF-era convention).
  Everything before the first \\chapter is the work's own 4-verse
    maNgalAcharaNa dedication.
"""
import re

from aksharamukha import transliterate

ITX_PATH = "stavamala.itx"
START_MARKER = "shrIshrIkR^iShNachaitanyachandrAya namaH |"
END_MARKER = "Source documents used for this electronic edition were :"

_CHAPTER_RE = re.compile(r"^\\chapter\{##(.+?)##\s*\.\.\s*(.+?)\s*\.\.\}$")
_SECTION_RE = re.compile(r"^\\section\{(\d+)\}$")
# One-off glitch in the source itself, in Gitavali: item 39's proper
# "\section{39}" command is missing, replaced by a malformed "(39]"
# text line (leading space and all) immediately followed by a stray
# "@1" artifact line with no content meaning -- both handled here the
# same way generate_stavamala.py's PDF-era pipeline had to.
_MALFORMED_SECTION_RE = re.compile(r"^\s*[(\[](\d+)[)\]]\s*$")
_STRAY_ARTIFACT_RE = re.compile(r"^@\d+$")
# Colophon start/end: kept as an italicized closing line at the end of
# each poem's body (not dropped) -- this is ITRANS (not IAST), so long
# vowels are capital letters (A/I/U), not macrons -- samAptam/samAptA/
# samAptaH/sampUrNam/sampUrNaH are the actual forms used (verified
# against every one of the 44 occurrences in the source). Also unlike a
# single fixed line, the colophon sometimes wraps across two physical
# lines (e.g. "...shrIku~njavihAriNaH\nprathamAShTakaM samAptam |"), so
# this is handled as a stateful start..end span in main(), not a single
# regex, and the wrapped lines are rejoined with a space (prose, not
# verse -- not a pada line-wrap like "\\-").
_COLOPHON_START_RE = re.compile(r"^iti\s+shrIrUpagosvAmivirachitastavamAlAyAM")
_COLOPHON_END_RE = re.compile(r"(samAptam|samAptA|samAptaH|sampUrNam|sampUrNaH)\s*\|?\s*$")
_TRAILING_NUM_RE = re.compile(r"^(.*?)\s+(\d+)$")

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


_VERSE_END_RE = re.compile(r"\|\|\s*\d+\|\|\s*$")
_STANDALONE_MARKER_RE = re.compile(r"^(\|\|.*\|\||\(.*\))$")


def add_verse_breaks(lines):
    """Inserts a blank-line paragraph break after every numbered
    verse-end marker ("...padam || 1||") and after every standalone
    metre-name/date caption line ("|| sragviNI ||", "(dodhakam)",
    "(1471 shakAbde, 1550 khR^iShTAbde)") -- the ITX source runs an
    entire poem's verses together with no blank lines between them at
    all, but the site's established convention (see
    srikrishna-lilastava.md) is one verse per paragraph, blank-line
    separated, for a chantable reading rhythm."""
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
    """Groups lines into paragraphs on blank-line boundaries, same
    convention as generate_stavamala.py: each paragraph's lines get
    joined with a markdown hard-break ("  \\n"), paragraphs themselves
    separated by a blank line."""
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
    line, e.g. "chaitanyAShTakam 1" or "Chando.aShTAdashakam". Splits off
    a trailing bare number (poem-set index, e.g. "Shri Kunjaviharyashtakam
    1" / "2") from the base title, since the number itself isn't ITRANS
    text -- it's converted to a Devanagari numeral directly, not
    transliterated as a word."""
    m = _TRAILING_NUM_RE.match(raw_title)
    if m:
        return convert(m.group(1)), int(m.group(2))
    return convert(raw_title), None


def main():
    with open(ITX_PATH, encoding="utf-8") as f:
        raw_lines = f.read().split("\n")

    start = next(i for i, l in enumerate(raw_lines) if l.strip() == START_MARKER)
    end = next(i for i, l in enumerate(raw_lines) if l.strip() == END_MARKER)
    lines = add_verse_breaks(dehyphenate(raw_lines[start:end]))

    sections = []  # (heading, body_lines)
    heading = "मङ्गलाचरणम्"
    chapter_base = None  # current chapter's converted title (sans trailing number)
    # Item numbers within a multi-item chapter (Chando'shtadashakam /
    # Gitavali / Shri Govindavirudavali) are assigned by POSITION in
    # sequence, not the literal \section{N} value -- Govindavirudavali's
    # source has a genuine duplicate ("16" used for two consecutive
    # items), and renumbering by position is this site's established
    # fix for it (matches generate_stavamala.py's PDF-era convention;
    # trusting the literal value would print two identical headings).
    item_counter = 0
    body = []

    def flush():
        text = render_body(body)
        if text.strip():
            sections.append((heading, text))

    in_colophon = False
    colophon_buf = []
    for line in lines:
        stripped = line.strip()
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
        m_sec = None if m_chap else (_SECTION_RE.match(stripped) or _MALFORMED_SECTION_RE.match(stripped))
        if m_chap:
            flush()
            body = []
            chapter_base, chapter_num = parse_chapter_title(m_chap.group(2).strip())
            item_counter = 0
            heading = chapter_base if chapter_num is None else f"{chapter_base} {to_dev(chapter_num)}"
            continue
        if m_sec:
            flush()
            body = []
            item_counter += 1
            heading = f"{chapter_base} {to_dev(item_counter)}"
            continue
        if _STRAY_ARTIFACT_RE.match(stripped):
            continue
        body.append(line)
    flush()

    body_parts = [f"## {heading}\n\n{text}" for heading, text in sections]
    with open("/tmp/stavamala_body.md", "w", encoding="utf-8") as f:
        f.write("\n\n".join(body_parts))
    print(f"wrote /tmp/stavamala_body.md, {len(body_parts)} sections")


if __name__ == "__main__":
    main()
