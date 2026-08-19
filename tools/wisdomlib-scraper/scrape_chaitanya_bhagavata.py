#!/usr/bin/env python3
"""Scrapes ONLY the original-language verse text (Bengali script /
Devanagari-Unicode transliteration / IAST) of Chaitanya Bhagavata from
wisdomlib.org, explicitly skipping the English translation and the
Gaudiya-bhasya purport/commentary -- the modern portions are not public
domain, only Vrindavana Dasa Thakura's original ~16th-century verses are.

How the exclusion actually works (verified against live pages before
writing this, not guessed): each verse page's content div contains a
single <blockquote> holding the original-language block (a label like
"Bengali text, Devanagari and Unicode transliteration of verse B.C.V:",
the transliteration, and a <p lang="bn"> paragraph in Bengali script).
The blockquote closes BEFORE a <strong>English translation:</strong>
paragraph and, further down, an <h2>Commentary: ...</h2> section. So
"take the blockquote, stop there" is a structural boundary, not a
label-text guess -- translation and commentary are siblings AFTER the
blockquote, never inside it.

TOC discovery: the site's hub page (BASE_URL) links to 3 "Book N" pages
(Adi/Madhya/Antya-khanda) and, separately, to each of the ~55 individual
chapter pages -- but each "Book N" page already lists every single verse
link for that entire book directly (no need to crawl all 55 chapter
pages first), so that's what this script uses. This is a deliberate
simplification verified against the live site, not a guess.

Usage:
    python3 scrape_chaitanya_bhagavata.py [--book 1] [--limit 20]
                                           [--out chaitanya_bhagavata.csv]
                                           [--format csv|json]
                                           [--delay-min 1.0] [--delay-max 2.0]
                                           [--resume]

Respects robots.txt via urllib.robotparser before every fetch, and
sleeps a randomized delay between requests.
"""
import argparse
import csv
import json
import logging
import random
import re
import sys
import time
import urllib.robotparser
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.wisdomlib.org"
HUB_URL = f"{BASE_URL}/hinduism/book/chaitanya-bhagavata"
USER_AGENT = (
    "chaitanya-siddhanta-vangmaya-archive-bot/1.0 "
    "(personal research archive; respects robots.txt; low request rate)"
)

VERSE_LABEL_RE = re.compile(r"^Verse\s+(\d+)\.(\d+)\.(\d+)$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cb-scraper")


@dataclass
class VerseRecord:
    book: int
    chapter: int
    verse_number: int
    original_text: str
    source_url: str


class RobotsGate:
    """Wraps urllib.robotparser so every fetch is checked against the
    site's actual robots.txt, not just an assumption made once.

    Fetches robots.txt with `requests` and our real User-Agent instead of
    calling RobotFileParser.read() directly: that method fetches via
    urllib.request with a bare default UA, which wisdomlib.org 403s --
    and robotparser treats a 401/403 on robots.txt itself as "disallow
    everything," which would silently block every URL even though the
    site's actual robots.txt (confirmed separately) is permissive here."""

    def __init__(self, base_url: str, user_agent: str):
        self.user_agent = user_agent
        self.rp = urllib.robotparser.RobotFileParser()
        robots_url = urljoin(base_url, "/robots.txt")
        try:
            resp = requests.get(robots_url, headers={"User-Agent": user_agent}, timeout=10)
            resp.raise_for_status()
            self.rp.parse(resp.text.splitlines())
        except requests.RequestException as exc:
            log.warning("could not fetch robots.txt (%s) -- treating as fully disallowed to be safe", exc)
            self.rp.disallow_all = True

    def allowed(self, url: str) -> bool:
        return self.rp.can_fetch(self.user_agent, url)


class Scraper:
    def __init__(self, delay_range=(1.0, 2.0), timeout=20):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.robots = RobotsGate(BASE_URL, USER_AGENT)
        self.delay_range = delay_range
        self.timeout = timeout
        self.review_log: list[dict] = []

    def get(self, url: str) -> BeautifulSoup | None:
        if not self.robots.allowed(url):
            log.warning("robots.txt disallows %s -- skipping", url)
            self.review_log.append({"url": url, "reason": "disallowed by robots.txt"})
            return None
        time.sleep(random.uniform(*self.delay_range))
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            log.warning("fetch failed for %s: %s", url, exc)
            self.review_log.append({"url": url, "reason": f"fetch failed: {exc}"})
            return None
        return BeautifulSoup(resp.text, "html.parser")

    # -- TOC discovery --------------------------------------------------

    def discover_book_urls(self) -> list[tuple[int, str]]:
        """Returns [(book_number, book_toc_url), ...] from the hub page."""
        soup = self.get(HUB_URL)
        if soup is None:
            raise RuntimeError(f"could not fetch hub page {HUB_URL}")
        books = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            m = re.match(r"^Book\s+(\d+)\s*-", text)
            if m:
                books.append((int(m.group(1)), urljoin(BASE_URL, a["href"])))
        books.sort(key=lambda t: t[0])
        log.info("discovered %d book TOC pages", len(books))
        return books

    def discover_verse_urls(self, book_num: int, book_url: str) -> list[tuple[int, int, int, str]]:
        """Returns [(book, chapter, verse, verse_url), ...] listed on one
        book's TOC page. Only picks up links whose visible text is
        exactly "Verse B.C.V" -- chapter-introduction links and anything
        else on the page are deliberately not verses and are skipped."""
        soup = self.get(book_url)
        if soup is None:
            self.review_log.append({"url": book_url, "reason": "book TOC page fetch failed"})
            return []
        verses = []
        for a in soup.find_all("a", href=True):
            m = VERSE_LABEL_RE.match(a.get_text(strip=True))
            if not m:
                continue
            book, chapter, verse = (int(x) for x in m.groups())
            verses.append((book, chapter, verse, urljoin(BASE_URL, a["href"])))
        log.info("book %d: found %d verse links", book_num, len(verses))
        return verses

    # -- Verse extraction -------------------------------------------------

    def extract_original_text(self, soup: BeautifulSoup, url: str) -> str | None:
        """Returns the original-language block's text, or None (and logs
        to review_log) if the page doesn't match the expected structure.
        Deliberately does NOT fall back to guessing at other content --
        an unrecognized page is logged for manual review instead."""
        content = soup.find(id="scontent") or soup
        blockquote = content.find("blockquote")
        if blockquote is None:
            self.review_log.append({"url": url, "reason": "no <blockquote> found (structure mismatch)"})
            return None

        text = blockquote.get_text("\n", strip=True)
        if not text:
            self.review_log.append({"url": url, "reason": "blockquote present but empty"})
            return None

        # Sanity check: the page should also show the English-translation
        # label as a sibling AFTER the blockquote -- if it's missing
        # entirely the page may be some other kind of document (e.g. a
        # chapter-summary page that slipped through TOC discovery), so
        # flag it for a human to look at even though we still return the
        # blockquote text we found.
        if not content.find(string=re.compile(r"English translation", re.I)):
            self.review_log.append(
                {"url": url, "reason": "blockquote found but no 'English translation' label nearby -- verify structure"}
            )

        return text

    def scrape_verse(self, book: int, chapter: int, verse: int, url: str) -> VerseRecord | None:
        soup = self.get(url)
        if soup is None:
            return None
        text = self.extract_original_text(soup, url)
        if text is None:
            return None
        return VerseRecord(book=book, chapter=chapter, verse_number=verse, original_text=text, source_url=url)


# -- Output -----------------------------------------------------------------

def load_existing_urls(out_path: Path, fmt: str) -> set[str]:
    if not out_path.exists():
        return set()
    urls = set()
    if fmt == "csv":
        with out_path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                urls.add(row["source_url"])
    else:
        with out_path.open(encoding="utf-8") as f:
            for row in json.load(f):
                urls.add(row["source_url"])
    return urls


def append_record(out_path: Path, fmt: str, record: VerseRecord, write_header: bool):
    if fmt == "csv":
        with out_path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["book", "chapter", "verse_number", "original_text", "source_url"])
            if write_header:
                writer.writeheader()
            writer.writerow(asdict(record))
    else:
        # JSON output is accumulated in memory and written once at the end
        # by the caller (append_json_records), since JSON isn't line-
        # appendable the way CSV is.
        raise AssertionError("append_record should only be called for csv")


def write_json(out_path: Path, records: list[VerseRecord]):
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)


def write_review_log(path: Path, entries: list[dict]):
    if not entries:
        return
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "reason"])
        writer.writeheader()
        writer.writerows(entries)
    log.warning("%d page(s) need manual review -- see %s", len(entries), path)


# -- CLI ----------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--book", type=int, choices=[1, 2, 3], help="only scrape this book number (default: all 3)")
    ap.add_argument("--limit", type=int, help="stop after this many verses (for testing)")
    ap.add_argument("--out", default="chaitanya_bhagavata.csv", help="output file path")
    ap.add_argument("--format", choices=["csv", "json"], default="csv")
    ap.add_argument("--review-log", default="review_needed.csv", help="where to log pages needing manual review")
    ap.add_argument("--delay-min", type=float, default=1.0)
    ap.add_argument("--delay-max", type=float, default=2.0)
    ap.add_argument("--resume", action="store_true", help="skip verses already present in --out")
    args = ap.parse_args()

    out_path = Path(args.out)
    review_path = Path(args.review_log)

    scraper = Scraper(delay_range=(args.delay_min, args.delay_max))

    already_done = load_existing_urls(out_path, args.format) if args.resume else set()
    if already_done:
        log.info("resuming: %d verses already recorded, will skip those", len(already_done))

    books = scraper.discover_book_urls()
    if args.book:
        books = [b for b in books if b[0] == args.book]

    all_verse_links: list[tuple[int, int, int, str]] = []
    for book_num, book_url in books:
        all_verse_links.extend(scraper.discover_verse_urls(book_num, book_url))

    if args.limit:
        all_verse_links = all_verse_links[: args.limit]

    log.info("scraping %d verse pages", len(all_verse_links))

    json_records: list[VerseRecord] = []
    write_header = args.format == "csv" and not (args.resume and out_path.exists())
    scraped = 0
    for book, chapter, verse, url in all_verse_links:
        if url in already_done:
            continue
        record = scraper.scrape_verse(book, chapter, verse, url)
        if record is None:
            continue
        if args.format == "csv":
            append_record(out_path, "csv", record, write_header)
            write_header = False
        else:
            json_records.append(record)
        scraped += 1
        if scraped % 25 == 0:
            log.info("progress: %d verses scraped", scraped)

    if args.format == "json":
        # merge with any previously-existing records when resuming
        if args.resume and out_path.exists():
            with out_path.open(encoding="utf-8") as f:
                prior = [VerseRecord(**r) for r in json.load(f)]
            json_records = prior + json_records
        write_json(out_path, json_records)

    write_review_log(review_path, scraper.review_log)
    log.info("done: %d verses written to %s", scraped, out_path)


if __name__ == "__main__":
    main()
