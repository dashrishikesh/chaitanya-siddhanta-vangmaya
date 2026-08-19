#!/usr/bin/env python3
"""Turns the scraped Chaitanya Bhagavata CSV (original-language text only
-- see scrape_chaitanya_bhagavata.py) into site grantha markdown, one file
per chapter, matching the govinda-bhashya-adhyaya-N.md convention (shared
workSlug, per-file sequence, listed together on the work's index page).

Per verse, each scraped row's original_text is (in order): a label line,
the Bengali-script block, the site's own Devanagari transliteration block,
an IAST block, and a simplified-ASCII block -- confirmed by inspecting
actual scraped rows, not assumed. Per the user's explicit instruction,
this script does NOT use the site's own Devanagari block at all -- it
takes only the Bengali-script block (kept as-is) and the IAST block, and
regenerates Devanagari independently via aksharamukha, the same pipeline
used for every other grantha in this project.

Block splitting is positional, not purely classification-based: lines are
classified by Unicode script (bengali / devanagari / latin), consecutive
same-type lines are grouped, and a marker-only line (just digits/bars/
parens, e.g. "|| 1 ||") is folded into whichever block precedes it. Within
the "everything after the devanagari block" remainder, all but the last
latin sub-block are merged as IAST (a short pada with no diacritic
characters is still IAST, just merged with its neighbor rather than
mis-split by classification alone); the last sub-block is always the
redundant simplified-ASCII rendering and is discarded. Verified against
every one of book 1's 2940 rows: 2938 match the standard 5-block pattern
exactly, 2 are logged to review_needed_build.csv instead of guessing
(one has no distinguishable IAST/plain boundary at all).
"""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

from aksharamukha import transliterate

BENGALI_RE = re.compile(r"[ঀ-৿]")
DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
LATIN_RE = re.compile(r"[A-Za-z]")
IAST_DIACRITIC_RE = re.compile(r"[āīūṛṝḷḹṃḥśṣñṅṭḍṇĀĪŪṚṜḶḸṂḤŚṢÑṄṬḌṆ]")

# Sanskrit ordinal stems (masculine), 1-20 -- combined with "adhyayah" via
# the standard -ah + a -> o' sandhi (e.g. prathama + adhyayah -> prathamo'dhyayah).
ORDINAL_STEMS = {
    1: "prathama", 2: "dvitIya", 3: "tRRitIya", 4: "chaturtha", 5: "pa~nchama",
    6: "ShaShTha", 7: "saptama", 8: "aShTama", 9: "navama", 10: "dashama",
    11: "ekAdasha", 12: "dvAdasha", 13: "trayodasha", 14: "chaturdasha",
    15: "pa~nchadasha", 16: "ShoDasha", 17: "saptadasha", 18: "aShTAdasha",
    19: "ekonaviMsha", 20: "viMsha",
}

BOOK_NAMES_ITRANS = {1: "AdikhaNDa", 2: "madhyakhaNDa", 3: "antyakhaNDa"}

DEVNUMS = "०१२३४५६७८९"


def to_dev(n) -> str:
    return "".join(DEVNUMS[int(d)] for d in str(n))


def convert_itrans(text: str) -> str:
    return transliterate.process("ITRANS", "Devanagari", text)


def convert_iast(text: str) -> str:
    return transliterate.process("IAST", "Devanagari", text)


def classify_line(line: str) -> str:
    if BENGALI_RE.search(line):
        return "bengali"
    if DEVANAGARI_RE.search(line):
        return "devanagari"
    if LATIN_RE.search(line):
        return "iast" if IAST_DIACRITIC_RE.search(line) else "plain"
    return "other"


def group_blocks(text: str):
    lines = [l for l in text.split("\n") if l.strip()]
    blocks = []  # [type, [lines]]
    for l in lines:
        t = classify_line(l)
        if t == "other" and blocks:
            blocks[-1][1].append(l)
        elif blocks and blocks[-1][0] == t:
            blocks[-1][1].append(l)
        else:
            blocks.append([t, [l]])
    return blocks


def extract_bengali_and_iast(original_text: str):
    """Returns (bengali_text, iast_text) or (None, None) with a reason
    string if the row doesn't match a recognizable structure."""
    blocks = group_blocks(original_text)
    types = [b[0] for b in blocks]

    try:
        bengali_idx = types.index("bengali")
        devanagari_idx = types.index("devanagari", bengali_idx + 1)
    except ValueError:
        return None, None, "missing bengali or devanagari block"

    bengali_text = "\n".join(blocks[bengali_idx][1])

    # Everything after the site's own devanagari block, up to (but not
    # including) the final block, which is always the redundant
    # simplified-ASCII rendering.
    latin_blocks = blocks[devanagari_idx + 1 :]
    latin_blocks = [b for b in latin_blocks if b[0] in ("iast", "plain")]
    if len(latin_blocks) == 0:
        return None, None, "no latin (IAST) block found after devanagari"
    if len(latin_blocks) == 1:
        return None, None, "only one latin block -- can't distinguish IAST from plain transliteration"

    iast_lines = []
    for b in latin_blocks[:-1]:
        iast_lines.extend(b[1])
    iast_text = "\n".join(iast_lines)
    return bengali_text, iast_text, None


def strip_marker_lines(text: str) -> str:
    """Drops pure marker lines (|| N ||, (N), etc.) -- the verse number is
    already tracked separately via the CSV's verse_number column, and the
    site's own convention (see stavamala/stavamritalahari) renders the
    verse-end danda inline at the end of the last pada, not as its own line."""
    out = []
    for line in text.split("\n"):
        if re.fullmatch(r"[|()0-9\s]+", line):
            continue
        out.append(line)
    return out


def chapter_title(book_num: int, chapter_num: int) -> str:
    stem = ORDINAL_STEMS.get(chapter_num, str(chapter_num))
    itrans = f"{stem}o'dhyAyaH"
    return convert_itrans(itrans)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="output/chaitanya_bhagavata.csv")
    ap.add_argument("--book", type=int, choices=[1, 2, 3], required=True)
    ap.add_argument("--out-dir", default="../../src/content/granthas")
    ap.add_argument("--review-log", default="output/review_needed_build.csv")
    ap.add_argument("--sequence-offset", type=int, default=0, help="global chapter sequence offset for this book")
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if int(r["book"]) == args.book]

    by_chapter = defaultdict(list)
    for r in rows:
        by_chapter[int(r["chapter"])].append(r)

    review = []
    out_dir = Path(args.out_dir)
    book_name_dev = convert_itrans(BOOK_NAMES_ITRANS[args.book])

    for chapter_num in sorted(by_chapter):
        verses = sorted(by_chapter[chapter_num], key=lambda r: int(r["verse_number"]))
        sections = []
        for r in verses:
            bengali, iast, reason = extract_bengali_and_iast(r["original_text"])
            if reason:
                review.append({"url": r["source_url"], "reason": reason})
                continue
            bengali_clean = "\n".join(strip_marker_lines(bengali))
            iast_clean = "\n".join(strip_marker_lines(iast))
            if not bengali_clean.strip() or not iast_clean.strip():
                review.append({"url": r["source_url"], "reason": "empty bengali or iast after marker-stripping"})
                continue
            devanagari = convert_iast(iast_clean)
            verse_dev = to_dev(r["verse_number"])
            heading = f"श्लोकः {verse_dev}"
            bengali_lines = "  \n".join(l.strip() for l in bengali_clean.split("\n") if l.strip())
            devanagari_lines = "  \n".join(l.strip() for l in devanagari.split("\n") if l.strip())
            body = f"{bengali_lines}\n\n{devanagari_lines}"
            sections.append(f"## {heading}\n\n{body}")

        if not sections:
            continue

        seq = args.sequence_offset + chapter_num
        title_dev = chapter_title(args.book, chapter_num)
        frontmatter = f"""---
title:
  devanagari: "{to_dev(chapter_num).zfill(2) if False else to_dev(chapter_num)} {title_dev}"
  iast: "Chapter {chapter_num}"
work:
  devanagari: "श्रीचैतन्यभागवतम्"
  iast: "Śrī Caitanya-bhāgavata"
  english: "The Life and Teachings of Sri Chaitanya"
corpusName:
  devanagari: "{book_name_dev}"
  iast: "Book {args.book}"
workSlug: "chaitanya-bhagavata"
partOf: "chaitanya-bhagavata"
sequence: {seq}
author: "श्री वृन्दावन दास ठाकुर"
authorGroup: "acharya"
goswami: "vrindavanadasa"
category: "carita"
commentaries: []
availableScripts: ["devanagari", "bengali"]
---

# {book_name_dev} {to_dev(chapter_num)}

"""
        content = frontmatter + "\n\n".join(sections) + "\n"
        out_path = out_dir / f"chaitanya-bhagavata-{args.book}-{chapter_num:02d}.md"
        out_path.write_text(content, encoding="utf-8")
        print(f"wrote {out_path} ({len(sections)} verses)")

    if review:
        review_path = Path(args.review_log)
        with review_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["url", "reason"])
            writer.writeheader()
            writer.writerows(review)
        print(f"{len(review)} verse(s) need manual review -- see {review_path}")


if __name__ == "__main__":
    main()
