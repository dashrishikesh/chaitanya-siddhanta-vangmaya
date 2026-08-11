#!/usr/bin/env python3
"""Extracts Śrī Rūpa Gosvāmī's Stavamālā (a ~45-poem stotra anthology) from
the source PDF into a single site markdown file, one '## ' section per
titled poem (matching the site's srikrishna-lilastava.md convention).

Unlike the other tools in this directory, no IAST transliteration is
needed here -- the PDF's Devanagari text extracts cleanly via poppler's
pdftotext (unlike PyPDF2/pypdf, which mangles the embedded font's glyph
mapping). This is a pure-Devanagari source.

Most section boundaries come directly from the PDF's own bookmarks/outline,
each of which points at a page where a poem begins; consecutive top-level
bookmarks' start pages give exact page ranges. Three works --
Chando'shtadashakam (18 items), Gitavali (~42 songs), and
Shri-Govinda-virudavali (28 verses) -- have nested bookmarks whose per-item
page numbers are unreliable (several items share a start page, and the
bookmark list itself has gaps/duplicates), so for those the whole combined
range is extracted as one block and re-split on the source's own bare
Devanagari-numeral marker lines (e.g. a line containing only "३"), which is
the same content-level signal the PDF's layout uses to separate items.
"""
import re
import subprocess
import sys

import pypdf

PDF_PATH = "../../stavamAlAsangraha.pdf"

_MULTI_ITEM_PARENTS = {
    "Chando ashtadashakam  ॥ छन्दोऽष्टादशकम् ॥",
    "Gitavali  ॥ गीतावली ॥",
    "Shri Govindavirudavali  ॥ श्रीगोविन्दविरुदावली ॥",
}

_HEADER_LINES = {
    "Garland Of Devotional Prayers Stavamala By Shri Rupadeva",
    "Gosvami",
    "श्रीरूपगोस्वामिविरचिता स्तवमाला",
    "stavamAlAsangraha.pdf",
}
_COLOPHON_RE = re.compile(r"^इति\s+श्रीरूपगोस्वामिविरचितस्तवमालायां.*(समाप्तम्|सम्पूर्णम्)\s*।?\s*$")
_PAGE_NUM_RE = re.compile(r"^[0-9]+$")  # ASCII only -- \d also matches Devanagari digits
_BOOKMARK_TITLE_RE = re.compile(r"॥\s*(.+?)\s*॥")
_BARE_NUMERAL_RE = re.compile(r"^[(\[]?([०-९]+)[)\]]?$")
_LONE_DANDA_RE = re.compile(r"^॥+\s*$")
# One-off OCR/layout glitch on the page-129/130 boundary of Gitavali: a
# stray "@<digit>" line with no content meaning, sitting right after a
# malformed "(३९]" item marker.
_STRAY_ARTIFACT_RE = re.compile(r"^@[०-९]$")

_DEVNUMS = "०१२३४५६७८९"


def to_dev_num(n: int) -> str:
    return "".join(_DEVNUMS[int(c)] for c in str(n))


def get_top_level_sections():
    reader = pypdf.PdfReader(PDF_PATH)
    top = []

    def walk(outlines, depth=0):
        for item in outlines:
            if isinstance(item, list):
                continue  # nested lists are children of the preceding item; skip here
            if depth == 0:
                page = reader.get_destination_page_number(item)
                top.append({"title": item.title, "page": page})

    # pypdf yields a flat mixed list where a nested list follows its parent;
    # walking at depth 0 and skipping list items is enough for the top level.
    for item in reader.outline:
        if isinstance(item, list):
            continue
        page = reader.get_destination_page_number(item)
        top.append({"title": item.title, "page": page})

    top = [e for e in top if e["title"] not in ("Document Information", "Document Text", "Document Credits")]

    sections = []
    for i, e in enumerate(top):
        start = e["page"]
        end = top[i + 1]["page"] if i + 1 < len(top) else get_credits_page(reader)
        m = _BOOKMARK_TITLE_RE.search(e["title"])
        heading = m.group(1).strip() if m else e["title"].strip()
        # The English portion (before the first "॥") reliably opens the
        # printed title line in the PDF, even in the few cases where the
        # closing "॥" wraps onto its own following line -- use it to find
        # and drop that line rather than requiring two dandas on one line.
        english_prefix = e["title"].split("॥")[0].strip()
        sections.append({
            "heading": heading,
            "english_prefix": english_prefix,
            "start": start,
            "end": end,
            "multi_item": e["title"] in _MULTI_ITEM_PARENTS,
        })
    return sections


def get_credits_page(reader):
    for item in reader.outline:
        if not isinstance(item, list) and item.title == "Document Credits":
            return reader.get_destination_page_number(item)
    return len(reader.pages)


def extract_pages_text(start, end):
    out = subprocess.run(
        ["pdftotext", "-f", str(start + 1), "-l", str(end), PDF_PATH, "-"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def strip_boilerplate(raw):
    """Removes repeated header lines and bare page-number lines; keeps
    everything else (including blank lines, needed to detect paragraph
    breaks) in original order."""
    lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped in _HEADER_LINES or _PAGE_NUM_RE.match(stripped) or stripped == "sanskritdocuments.org":
            continue
        lines.append(stripped)
    return lines


def lines_to_markdown(lines):
    paragraphs = []
    current = []
    for line in lines:
        if line == "":
            if current:
                paragraphs.append(current)
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(current)
    return "\n\n".join("  \n".join(p) for p in paragraphs)


def _drop_title_and_colophon_lines(lines, english_prefix):
    """Drops the one printed title line (matched by its English prefix,
    since the closing danda sometimes wraps onto its own following line),
    any orphaned lone-danda line left behind by that wrap, and colophon
    lines. Keeps everything else, including blank lines."""
    cleaned = []
    dropped_title = False
    for line in lines:
        if line == "":
            cleaned.append(line)
            continue
        if _COLOPHON_RE.match(line) or _LONE_DANDA_RE.match(line):
            continue
        if not dropped_title and line.startswith(english_prefix):
            dropped_title = True
            continue
        cleaned.append(line)
    return cleaned


def build_simple_section(s):
    raw = extract_pages_text(s["start"], s["end"])
    lines = strip_boilerplate(raw)
    cleaned = _drop_title_and_colophon_lines(lines, s["english_prefix"])
    text = lines_to_markdown(cleaned)
    if not text.strip():
        return []
    return [(s["heading"], text)]


def build_multi_item_sections(s):
    raw = extract_pages_text(s["start"], s["end"])
    lines = strip_boilerplate(raw)
    cleaned = [l for l in _drop_title_and_colophon_lines(lines, s["english_prefix"]) if not _STRAY_ARTIFACT_RE.match(l)]

    # Split on numeral marker lines (usually bare "३९", occasionally
    # bracketed like "(३९]" due to a source layout glitch). The marker's
    # own printed numeral is NOT used for the heading -- Shri Govinda
    # virudavali has a genuine duplicate ("१६" printed twice in a row) in
    # the source itself, so items are numbered by their actual position in
    # sequence instead, which is robust to both duplicates and gaps.
    chunks = []  # (is_marked, list_of_lines)
    current_is_marked = False
    current_lines = []
    for line in cleaned:
        if _BARE_NUMERAL_RE.match(line):
            chunks.append((current_is_marked, current_lines))
            current_is_marked = True
            current_lines = []
        else:
            current_lines.append(line)
    chunks.append((current_is_marked, current_lines))

    out = []
    item_num = 0
    for is_marked, item_lines in chunks:
        text = lines_to_markdown(item_lines)
        if not text.strip():
            continue
        if is_marked:
            item_num += 1
            heading = f"{s['heading']} {to_dev_num(item_num)}"
        else:
            heading = s["heading"]
        out.append((heading, text))
    return out


def main():
    sections = get_top_level_sections()
    print(f"{len(sections)} top-level bookmarks", file=sys.stderr)

    body_parts = []
    for s in sections:
        if s["start"] >= s["end"]:
            print(f"WARNING: zero-length range skipped: {s['heading']!r}", file=sys.stderr)
            continue
        items = build_multi_item_sections(s) if s["multi_item"] else build_simple_section(s)
        for heading, text in items:
            body_parts.append(f"## {heading}\n\n{text}")

    with open("/tmp/stavamala_body.md", "w", encoding="utf-8") as f:
        f.write("\n\n".join(body_parts))
    print(f"wrote /tmp/stavamala_body.md, {len(body_parts)} sections", file=sys.stderr)


if __name__ == "__main__":
    main()
