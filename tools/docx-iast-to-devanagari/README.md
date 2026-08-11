# docx IAST -> Devanagari batch converter

Offline batch converter for large `.docx` files: transliterates IAST
(romanized Sanskrit) paragraphs to Devanagari, cross-checking two
independent engines and flagging anything uncertain for human review
instead of guessing.

No network calls at runtime -- both transliteration engines are pure
Python libraries that ship their own rule tables.

## Setup

```bash
cd tools/docx-iast-to-devanagari
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python convert.py input.docx output.docx
```

Options:

- `--checkpoint-every N` (default 200) -- save an intermediate `.docx` +
  progress file every N **paragraphs** processed. python-docx has no
  concept of a rendered "page", so this counts paragraphs, not pages;
  pick N based on how many paragraphs are typically on a page in your
  document if you want checkpoints to land roughly every ~25 pages.

If `output.docx` (and its `.progress.json`) already exist from a
previous run -- e.g. the process crashed or was killed partway through
a 500-page run -- running the same command again **resumes** from the
last checkpoint instead of starting over. Re-running after a run has
already finished is a safe no-op.

## What it does

For every paragraph in the document (body text, tables -- including
nested tables, headers/footers, footnotes, and endnotes):

1. Concatenates all of that paragraph's run text into one string before
   doing anything else. **Never transliterate run-by-run** -- Word
   splits paragraph text across multiple `<w:r>` runs on every
   formatting change or spell-check boundary, so a single diacritic can
   land split across two runs and get corrupted if you convert runs in
   isolation.
2. Skips the paragraph untouched if it doesn't look like it contains
   IAST (no diacritics present) -- this is how plain English headers,
   page numbers, and non-Sanskrit content pass through unmodified.
3. If it looks like a *mix* of English prose and IAST (e.g. an editorial
   aside like "Note: this reading is uncertain, kṛṣṇaḥ ..."), the whole
   paragraph is left **unconverted** and logged to
   `*.review_mixed_language.csv` instead of being auto-converted -- see
   "Known limitation" below for why this is deliberately conservative.
4. Otherwise, transliterates the paragraph with both `aksharamukha` and
   `indic_transliteration` (sanscript module, IAST -> Devanagari). If
   they agree, uses that output. If they disagree, still writes
   aksharamukha's output (the more actively maintained, broader-coverage
   engine of the two) but logs both outputs to `*.review_diffs.csv` so a
   human can check which one is actually correct.
5. Writes the converted text back into the paragraph's **first** run
   (keeping that run's font/bold/italic/size), and deletes the rest of
   the runs. If the paragraph had more than one run with *different*
   formatting from each other before this (e.g. one word was bolded
   mid-verse), that gets flattened -- these paragraphs are logged to
   `*.review_formatting.csv` so a human can decide whether the lost
   formatting mattered.

## Outputs

Given `output.docx`, you'll also get:

- `output.review_diffs.csv` -- paragraphs where the two engines disagreed.
- `output.review_formatting.csv` -- paragraphs that had multiple
  differently-formatted runs before conversion (formatting was flattened).
- `output.review_mixed_language.csv` -- paragraphs left unconverted
  because they looked like a mix of English and Sanskrit.
- `output.sanity_report.txt` -- paragraph-count comparison (input vs.
  output -- should always match; if not, something was silently
  dropped, investigate immediately), conversion/skip/flag counts, and a
  count of paragraphs containing both Devanagari and stray Latin
  letters after conversion (worth spot-checking -- can be legitimate
  citations, or a sign something didn't convert cleanly).
- `output.progress.json` -- resume checkpoint state. Safe to delete
  once you're happy with a completed run.

## Recommended validation pass (do this before trusting the output)

1. Check `sanity_report.txt`: paragraph counts must match, and look at
   the mixed-language/diff/formatting flag counts to gauge how much
   manual review is actually needed.
2. Read through `review_diffs.csv` -- for a 500-page corpus expect
   dozens to hundreds of rows; these are exactly the "subtle error"
   class (avagraha placement, sandhi joins, anusvāra vs. anunāsika)
   that's genuinely ambiguous even for a single well-tested engine.
3. Sample ~20 pages spread across the document and eyeball them,
   ideally rendered side by side with the original (e.g.
   `soffice --headless --convert-to pdf output.docx`).
4. Spot-check that Devanagari verse numbers converted correctly if the
   source used Devanagari numerals for them.

## Known limitation: mixed English/Sanskrit paragraphs

Distinguishing "genuine English prose" from "Sanskrit that happens to
have no IAST diacritics in this particular sentence" is genuinely hard
from surface text alone -- ordinary Sanskrit words like `nimittam`,
`api`, `uddhava`, `tatra`, `sarva`, `iti` contain none of the sounds
IAST marks specially, so a naive "N consecutive plain-ASCII words means
English" rule false-positives constantly on real Sanskrit text (this
tripped up an early version of this tool during testing -- see
`engines.py` for the two much narrower heuristics that replaced it: a
short ASCII run immediately before a colon, like `"Note: ..."`, and the
presence of an actual English function word like `the`/`of`/`and`/
`this`). These heuristics are deliberately conservative in the direction
of **flagging for review rather than guessing** -- expect
`review_mixed_language.csv` to need a real read-through, and expect it
to occasionally under-flag a genuinely mixed paragraph that doesn't
match either pattern (e.g. a label with no colon and no function word).
If you find a systematic pattern of missed cases in your document, add
it as a third pattern in `has_mixed_language_run()`.

## Known limitation: footnotes/endnotes support is hand-built

python-docx (as of 1.2.0) has no API for footnotes or endnotes at all.
`docx_walk.py` reaches into the underlying OOXML relationship graph
directly to find, read, and -- critically -- make **editable in place**
the footnotes/endnotes part (a part loaded from disk is a generic
read-only blob unless it's promoted to an `XmlPart`; see the comments
in `docx_walk._get_notes_part` for why a naive "just parse the XML"
approach silently loses edits on save). This was tested against a
hand-built synthetic footnote and works, but hasn't been run against
footnotes from a real-world Word document produced by a different
version of Word/LibreOffice/etc. -- if footnotes silently don't show up
in the converted output, check `sanity_report.txt`'s paragraph count
first (if input/output counts match but a footnote's text looks
unconverted, the relationship-finding logic may need adjusting for
that specific document's structure).

## Files

- `convert.py` -- CLI entry point / main pipeline.
- `docx_walk.py` -- paragraph iteration (body, tables, headers/footers,
  footnotes, endnotes).
- `engines.py` -- wraps both transliteration engines, the IAST-detection
  heuristic, and the mixed-language heuristic.
- `paragraph_rewrite.py` -- safe run-concatenation and run-collapsing
  paragraph rewrite.
- `make_test_docx.py` / `make_big_test_docx.py` -- synthetic test
  fixtures exercising every code path (mixed formatting, split
  diacritics across runs, tables, footnotes, English skip, mixed
  English/Sanskrit).
