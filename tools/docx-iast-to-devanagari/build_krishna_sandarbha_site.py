#!/usr/bin/env python3
"""Assembles the final site markdown body from the converted Devanagari
docx files (produced by split_krishna_sandarbha.py + convert_no_hyphen_
join.py):

  krishna_sandarbha_anucchedas_output.docx      -- mangalacharanam +
    181 anuccheda mula chunks (numbered 1-145, 153-185, 187-189 -- the
    source itself has no [146]-[152] or [186], see generate_krishna_
    sandarbha.py), each preceded by a synthetic "[N]" boundary marker.
  krishna_sandarbha_sarva_samvadini_output.docx -- her voice, per
    anuccheda, preceded by a matching synthetic "[N]" marker wherever
    that anuccheda has any of her content (22 of 181 do).

Every anuccheda's content comes strictly from its own [N]..[N+1] marker
range -- her voice within that range is rendered as a "### सर्व-संवादिनी"
subsection inside that same anuccheda's section, not pulled to a
separate trailing block. Unlike Bhagavat-sandarbha/Paramatma-sandarbha,
this edition has no separate sāra-niṣkarṣa, Appendix, or trailing
sarva-saṁvādinī excerpt -- her commentary is fully integrated inline
throughout (see generate_krishna_sandarbha.py's module docstring).

Output: /tmp/krishna_sandarbha_body.md
"""
import re
import sys
from collections import Counter

from docx import Document

sys.path.insert(0, ".")
from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text
from generate_krishna_sandarbha import COLOR_MAP

ANUCCHEDAS_DOCX = "krishna_sandarbha_anucchedas_output.docx"
SARVA_SAMVADINI_DOCX = "krishna_sandarbha_sarva_samvadini_output.docx"

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


def is_quoted(color: str) -> bool:
    return COLOR_MAP.get(color, "quoted") == "quoted"


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
        current.append((t, is_quoted(color)))
    if current_n is None:
        leading = current
    else:
        by_n[current_n] = current
    return leading, by_n


def main():
    mula_leading, mula_by_n = load_by_anuccheda(ANUCCHEDAS_DOCX)
    sarva_leading, sarva_by_n = load_by_anuccheda(SARVA_SAMVADINI_DOCX)

    anuccheda_numbers = sorted(set(mula_by_n) | set(sarva_by_n))

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

    for n in anuccheda_numbers:
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

    body = "\n".join(out_lines)
    body = re.sub(r"\n{3,}", "\n\n", body)
    with open("/tmp/krishna_sandarbha_body.md", "w", encoding="utf-8") as f:
        f.write(body)

    n_h2 = sum(1 for l in out_lines if l.startswith("## "))
    n_h3 = sum(1 for l in out_lines if l.startswith("### "))
    print(f"wrote /tmp/krishna_sandarbha_body.md, {n_h2} top sections ({len(anuccheda_numbers)} anuccheda), "
          f"{n_h3} sarva-samvadini subsections", file=sys.stderr)


if __name__ == "__main__":
    main()
