"""Paragraph-level read/rewrite: concatenate run text safely (diacritics
can split across run boundaries), and write converted text back while
preserving the first run's formatting.
"""


def paragraph_full_text(paragraph) -> str:
    """Full paragraph text, run-boundary-agnostic (this is why we never
    transliterate run-by-run: a diacritic can be split across two runs).
    """
    return "".join(run.text for run in paragraph.runs)


def _run_format_signature(run):
    f = run.font
    return (
        f.bold,
        f.italic,
        f.underline,
        f.size,
        f.name,
        f.color.rgb if f.color and f.color.type is not None else None,
    )


def has_mixed_formatting(paragraph) -> bool:
    """True if this paragraph had more than one run AND those runs don't
    all share identical formatting -- i.e. rewriting into a single run
    will flatten something (e.g. a bolded word inside a verse).
    """
    runs = paragraph.runs
    if len(runs) <= 1:
        return False
    signatures = {_run_format_signature(r) for r in runs}
    return len(signatures) > 1


def rewrite_paragraph_text(paragraph, new_text: str):
    """Replace the paragraph's whole text with new_text, keeping the
    first run (and therefore its formatting) and deleting the rest.
    If the paragraph has no runs at all, add one.
    """
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(new_text)
        return
    runs[0].text = new_text
    for run in runs[1:]:
        run._element.getparent().remove(run._element)
