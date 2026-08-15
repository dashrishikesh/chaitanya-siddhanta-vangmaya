#!/usr/bin/env python3
"""Assembles the final site markdown body from the converted Devanagari
docx files (produced by split_paramatma_sandarbha.py + convert_no_hyphen_
join.py):

  paramatma_sandarbha_anucchedas_output.docx      -- mangalacharanam +
    110 anuccheda mula chunks, each preceded by a synthetic "[N]" marker.
  paramatma_sandarbha_sarva_samvadini_output.docx -- her voice, per
    anuccheda, preceded by a matching synthetic "[N]" marker wherever
    that anuccheda has any of her content (8 of 110 do).
  paramatma_sandarbha_sarva_samvadini_anuvyakhya_output.docx -- her
    further excerpt after mula's own closing colophon, rendered as a
    standalone trailing "## श्री-सर्व-संवादिनी" section.

Every anuccheda's content comes strictly from its own [N]..[N+1] marker
range -- her voice within that range is rendered as a "### सर्व-संवादिनी"
subsection inside that same anuccheda's section, not pulled to a
separate trailing block (same convention as Bhagavat-sandarbha's site
content, applied per explicit prior correction on that pipeline).

Output: /tmp/paramatma_sandarbha_body.md
"""
import re
import sys
from collections import Counter

from docx import Document

sys.path.insert(0, ".")
from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text

ANUCCHEDAS_DOCX = "paramatma_sandarbha_anucchedas_output.docx"
SARVA_SAMVADINI_DOCX = "paramatma_sandarbha_sarva_samvadini_output.docx"
SARVA_SAMVADINI_ANUVYAKHYA_DOCX = "paramatma_sandarbha_sarva_samvadini_anuvyakhya_output.docx"
SARVA_SAMVADINI_ANUVYAKHYA_HEADING = "श्री-सर्व-संवादिनी"
SARVA_SAMVADINI_ANUVYAKHYA_SUBTITLE = "परमात्म-सन्दर्भानुव्याख्या"

N_ANUCCHEDA = 110

COLOR_MAP = {
    "DEFAULT": "mula",
    "000000": "mula",
    "0000FF": "quoted",
    "3366FF": "quoted",
    "008000": "quoted",
    "009900": "quoted",
    "339933": "quoted",
    "800080": "quoted",
    "FF0000": "mula",
}

_MARKER_RE = re.compile(r"^\[(\d+)\]$")

DEVNUMS = "०१२३४५६७८९"


def to_dev(n) -> str:
    return "".join(DEVNUMS[int(d)] for d in str(n))


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


def load_by_anuccheda(path):
    """Splits a converted docx on its synthetic "[N]" markers. Returns
    (leading_parts, {N: [(text, is_quoted), ...]}) -- leading_parts is
    whatever comes before the first marker (mangalacharanam's own
    content)."""
    doc = Document(path)
    paras = list(iter_all_paragraphs(doc))

    leading = []
    by_n = {}
    current_n = None
    current = []
    for p in paras:
        t = paragraph_full_text(p).strip()
        if not t:
            continue
        m = _MARKER_RE.match(t)
        if m:
            if current_n is None:
                leading = current
            else:
                by_n[current_n] = current
            current_n = int(m.group(1))
            current = []
            continue
        color = para_dominant_color(p)
        is_quoted = COLOR_MAP.get(color, "mula") == "quoted"
        current.append((t, is_quoted))
    if current_n is None:
        leading = current
    else:
        by_n[current_n] = current
    return leading, by_n


def load_flat(path):
    """Loads a converted docx with no "[N]" markers as one flat list of
    (text, is_quoted)."""
    doc = Document(path)
    paras = list(iter_all_paragraphs(doc))
    out = []
    for p in paras:
        t = paragraph_full_text(p).strip()
        if not t:
            continue
        color = para_dominant_color(p)
        is_quoted = COLOR_MAP.get(color, "mula") == "quoted"
        out.append((t, is_quoted))
    return out


def main():
    mula_leading, mula_by_n = load_by_anuccheda(ANUCCHEDAS_DOCX)
    sarva_leading, sarva_by_n = load_by_anuccheda(SARVA_SAMVADINI_DOCX)
    anuvyakhya_parts = load_flat(SARVA_SAMVADINI_ANUVYAKHYA_DOCX)

    out_lines = []

    if mula_leading or sarva_leading:
        out_lines.append("## मङ्गलाचरणम्")
        out_lines.append("")
        if mula_leading:
            out_lines.append(render_parts(mula_leading))
            out_lines.append("")
        if sarva_leading:
            out_lines.append("### सर्व-संवादिनी")
            out_lines.append("")
            out_lines.append(render_parts(sarva_leading))
            out_lines.append("")

    for n in range(1, N_ANUCCHEDA + 1):
        out_lines.append(f"## अनुच्छेदः {to_dev(n)}")
        out_lines.append("")
        mula_parts = mula_by_n.get(n, [])
        sarva_parts = sarva_by_n.get(n, [])
        if mula_parts:
            out_lines.append(render_parts(mula_parts))
            out_lines.append("")
        if sarva_parts:
            out_lines.append("### सर्व-संवादिनी")
            out_lines.append("")
            out_lines.append(render_parts(sarva_parts))
            out_lines.append("")

    if anuvyakhya_parts:
        out_lines.append(f"## {SARVA_SAMVADINI_ANUVYAKHYA_HEADING}")
        out_lines.append("")
        out_lines.append(f"*{SARVA_SAMVADINI_ANUVYAKHYA_SUBTITLE}*")
        out_lines.append("")
        out_lines.append(render_parts(anuvyakhya_parts))
        out_lines.append("")

    body = "\n".join(out_lines)
    body = re.sub(r"\n{3,}", "\n\n", body)
    with open("/tmp/paramatma_sandarbha_body.md", "w", encoding="utf-8") as f:
        f.write(body)

    n_h2 = sum(1 for l in out_lines if l.startswith("## "))
    n_h3 = sum(1 for l in out_lines if l.startswith("### "))
    print(f"wrote /tmp/paramatma_sandarbha_body.md, {n_h2} top sections, "
          f"{n_h3} sarva-samvadini subsections", file=sys.stderr)


if __name__ == "__main__":
    main()
