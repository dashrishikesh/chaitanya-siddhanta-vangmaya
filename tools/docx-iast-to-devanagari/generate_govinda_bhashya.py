#!/usr/bin/env python3
"""Segments the full Govinda-bhāṣya docx into adhyāya -> pāda -> adhikaraṇa
and generates site markdown files (one per adhyāya), using the docx's own
'—o)0(o—' separators as adhikaraṇa boundaries and its 'N. name-adhikaraṇam'
labels where present.

This is a first-pass automated generation, not manually verified boundary
by boundary the way tattva-sandarbha was (that took many correction rounds
for 64 sections; this text has ~240 adhikaraṇas across 8333 paragraphs, so
the same per-boundary manual pass isn't practical in one go). Boundary
errors on the same pattern found in tattva-sandarbha (a trailing sentence
of one adhikaraṇa's bhāṣya stranded at the top of the next) are expected
and should be spot-checked and reported back the same way.
"""
import re
import sys

from docx import Document

sys.path.insert(0, ".")
from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text
from engines import transliterate_aksharamukha, normalize_avagraha_quotes, looks_like_sanskrit, has_mixed_language_run

_CONVERT_CACHE = {}


def convert_text(iast_text: str) -> str:
    """Direct aksharamukha conversion, hyphens preserved (this work's site
    convention, matching tattva-sandarbha's dense-prose style, unlike
    convert.py's default join_compound_hyphens used for lila-stava)."""
    if iast_text in _CONVERT_CACHE:
        return _CONVERT_CACHE[iast_text]
    if not looks_like_sanskrit(iast_text) or has_mixed_language_run(iast_text):
        _CONVERT_CACHE[iast_text] = None
        return None
    # Source docx has 3 stray circumflex-a typos (should be macron ā).
    iast_text = iast_text.replace("â", "ā").replace("Â", "Ā")
    # "hds" is the source's citation abbreviation for the Vedānta-darśanam
    # edition (ed. Haridāsa Śāstrī) -- expand it before transliteration so
    # it doesn't get mangled into the meaningless letter-run "ह्द्स्".
    iast_text = re.sub(
        r"\bhds\b\s*[:.]",
        "bhāgavata-bhāṣyam (haridāsa śāstrī):",
        iast_text,
        flags=re.IGNORECASE,
    )
    # "rc"/"rpc" are the source's (inconsistently used) citation abbreviations
    # for Ramapada Chattopadhyaya (Brahma-sūtra o śrīmad-bhāgavata) -- same
    # fix, expand the bare word before transliteration (leaves any trailing
    # ":"/"." /")" punctuation untouched).
    iast_text = re.sub(r"\brpc\b", "rāmapada caṭṭopādhyāya", iast_text, flags=re.IGNORECASE)
    iast_text = re.sub(r"\brc\b", "rāmapada caṭṭopādhyāya", iast_text, flags=re.IGNORECASE)
    out = transliterate_aksharamukha(normalize_avagraha_quotes(iast_text))
    _CONVERT_CACHE[iast_text] = out
    return out

DEVNUMS = "०१२३४५६७८९"


def to_dev(n: int) -> str:
    return "".join(DEVNUMS[int(d)] for d in str(n))


def find_pada_boundaries(paras):
    bounds = []
    for i, t in enumerate(paras):
        tl = t.lower().strip()
        if not tl or "pādaḥ" not in tl or len(t) > 70:
            continue
        if tl.startswith("||") or "iti govinda" in tl:
            continue
        m_adhy = re.search(r"(prathamo|dvitīyo|tṛtīyo|caturtho)['’]?dhyāy", tl)
        m_pada = re.search(r"(prathamaḥ|dvitīyaḥ|tṛtīyaḥ|caturthaḥ)\s*pādaḥ", tl)
        if not m_pada:
            continue
        pada_idx = ["prathamaḥ", "dvitīyaḥ", "tṛtīyaḥ", "caturthaḥ"].index(m_pada.group(1))
        if m_adhy:
            adhy_idx = ["prathamo", "dvitīyo", "tṛtīyo", "caturtho"].index(m_adhy.group(1))
            bounds.append([adhy_idx, pada_idx, i])
        elif bounds:
            bounds.append([bounds[-1][0], pada_idx, i])
    deduped = []
    for b in bounds:
        if deduped and deduped[-1][:2] == b[:2]:
            continue
        deduped.append(b)
    return deduped


def para_dominant_color(orig_para):
    from collections import Counter

    counts = Counter()
    for r in orig_para.runs:
        t = r.text
        if not t.strip():
            continue
        c = r.font.color
        key = str(c.rgb) if (c is not None and c.rgb is not None) else "DEFAULT"
        counts[key] += len(t)
    if not counts:
        return "DEFAULT"
    return counts.most_common(1)[0][0]


def para_is_fully_bold(orig_para) -> bool:
    """The docx bolds three distinct things: '||N.N.N||' markers, the
    numbered adhikaraṇa labels, and -- reliably, verified against the
    first four sūtras of 1.1 -- the sūtra text itself. Markers and labels
    are filtered out separately by their own regexes before this is
    checked, so a fully-bold paragraph reaching this check is the sūtra.
    """
    runs_with_text = [r for r in orig_para.runs if r.text.strip()]
    return bool(runs_with_text) and all(r.bold for r in runs_with_text)


def render_adhikarana(texts):
    """texts: list of (devanagari_text, is_quoted, is_sutra). Groups
    consecutive quoted lines into one blockquote (markdown hard-break
    style), plain lines into paragraphs, and gives sūtra lines (detected
    by the docx's own bold formatting, see para_is_fully_bold) the
    centered/bold .sutra treatment.
    """
    out = []
    i = 0
    n = len(texts)
    while i < n:
        text, quoted, is_sutra = texts[i]
        if is_sutra:
            out.append(f'<p class="sutra">{text.strip().strip("॥ ")}</p>')
            i += 1
            continue
        if quoted:
            block = [text]
            i += 1
            while i < n and texts[i][1]:
                block.append(texts[i][0])
                i += 1
            out.append("> " + "  \n> ".join(block))
        else:
            out.append(text)
            i += 1
    return "\n\n".join(out)


_MARKER_RE = re.compile(r"^\|\|\s*[\d.]+\s*\|\|$")
_LABEL_RE = re.compile(r"^\d+\.\s*(.+)$")
_SECTION_NUM_RE = re.compile(r"^\(\s*[\d.]+\s*\)$")
_PADA_TITLE_RE = re.compile(
    r"^(prathamo|dvitīyo|tṛtīyo|caturtho)['’]?dhyāy|^(prathamaḥ|dvitīyaḥ|tṛtīyaḥ|caturthaḥ)\s*pādaḥ",
    re.IGNORECASE,
)


def main():
    original_doc = Document("govinda-bhashya_-_baladeva_vidyabhushana.docx")
    orig_para_objs = list(iter_all_paragraphs(original_doc))
    orig_paras = [paragraph_full_text(p).strip() for p in orig_para_objs]

    pada_bounds = find_pada_boundaries(orig_paras)
    pada_bounds.append([None, None, len(orig_paras)])

    seps = set(i for i, t in enumerate(orig_paras) if "o)0(o" in t)

    # Global adhikaraṇa counter per adhyāya (site-facing numbering, not the
    # docx's own restart-per-pāda numbering).
    adhyaya_content = {0: [], 1: [], 2: [], 3: []}
    adhyaya_counters = {0: 0, 1: 0, 2: 0, 3: 0}

    for pi in range(len(pada_bounds) - 1):
        adhy, pada, start = pada_bounds[pi]
        _, _, end = pada_bounds[pi + 1]
        seps_in = sorted(s for s in seps if start <= s < end)
        chunk_bounds = [start] + [s + 1 for s in seps_in] + [end]

        for ci in range(len(chunk_bounds) - 1):
            cstart, cend = chunk_bounds[ci], chunk_bounds[ci + 1]
            texts = []
            label = None
            for idx in range(cstart, cend):
                orig_t = orig_paras[idx].strip()
                if not orig_t or "o)0(o" in orig_t:
                    continue
                if _SECTION_NUM_RE.match(orig_t) or (_PADA_TITLE_RE.search(orig_t) and len(orig_t) < 70):
                    continue

                m_label = _LABEL_RE.match(orig_t)
                if m_label and not label:
                    label = convert_text(m_label.group(1))
                    continue

                if _MARKER_RE.match(orig_t):
                    continue

                conv_t = convert_text(orig_t)
                if not conv_t:
                    continue

                color = para_dominant_color(orig_para_objs[idx])
                quoted = color in ("0000FF", "3366FF")
                is_sutra = para_is_fully_bold(orig_para_objs[idx])
                texts.append((conv_t, quoted, is_sutra))

            if not texts:
                continue

            adhyaya_counters[adhy] += 1
            num = to_dev(adhyaya_counters[adhy])
            heading = f"## अधिकरणम् {num}"
            tags = []
            if ci == 0:
                tags.append(f"पादः {to_dev(pada + 1)}")
            if label:
                tags.append(label.strip())
            if tags:
                heading += " (" + ", ".join(tags) + ")"
            adhyaya_content[adhy].append(heading)
            adhyaya_content[adhy].append("")
            adhyaya_content[adhy].append(render_adhikarana(texts))

    for adhy_idx in range(4):
        out_path = f"/tmp/govinda_bhashya_adhyaya_{adhy_idx+1}.md"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(adhyaya_content[adhy_idx]))
        print(f"adhyāya {adhy_idx+1}: {adhyaya_counters[adhy_idx]} adhikaraṇas -> {out_path}")


if __name__ == "__main__":
    main()
