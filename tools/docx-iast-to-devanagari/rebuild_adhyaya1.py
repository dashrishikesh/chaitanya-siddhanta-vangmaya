#!/usr/bin/env python3
"""Rebuilds Govinda-bhashya adhyaya 1's adhikarana boundaries against a
reference table of authoritative sutra-per-adhikarana counts (provided by
the user, transcribed from a printed edition). The original bold-run-based
auto-segmentation (generate_govinda_bhashya.py) mis-split several
adhikaranas because its '-o)0(o-' separator / numbered-label heuristics
don't reliably mark every traditional adhikarana boundary in adhyaya 1;
this script instead cuts the sutra stream at exact sutra-count boundaries
taken from that reference table, after merging a handful of compound
sutras that the source docx's bold-run formatting split across two (or
three) paragraphs.
"""
import sys

from docx import Document

sys.path.insert(0, ".")
from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text
from generate_govinda_bhashya import (
    convert_text, para_dominant_color,
    _MARKER_RE, _LABEL_RE, _SECTION_NUM_RE, render_adhikarana, to_dev,
)

# Raw docx paragraph indices (fully-bold sutra candidates) that are actually
# one compound sutra split across adjacent/near-adjacent paragraphs by a
# mid-sentence paragraph break in the source. Verified against the docx's
# own embedded "||N||" sutra-number markers and grammatical completeness
# (a paragraph ending "... iti cet" awaits a SEPARATE reply-sutra and is
# NOT merged; a paragraph already containing the refutation particle "na"
# with the next paragraph as its dependent reason-clause IS merged).
MERGE_GROUPS = [
    (434, 435),
    (510, 511),
    (855, 856, 857),
    (981, 983),
    (1491, 1492),
]

# Reference table (adhikarana name, sutra count), in order, one list per
# pada. Names kept close to the user-provided table; a couple of obvious
# spelling normalizations applied (ghṛva -> dhruva, jagadācittva ->
# jagad-vācitva, matching the sutra "jagad-vācitvāt").
PADA_ADHIKARANAS = [
    [  # pada 1 (11 adhikarana, 32 sutras)
        ("जिज्ञासाधिकरणम्", 1), ("जन्माद्यधिकरणम्", 1), ("शास्त्रयोनित्वाधिकरणम्", 1),
        ("समन्वयाधिकरणम्", 1), ("ईक्षत्यधिकरणम्", 7), ("आनन्दमयाधिकरणम्", 8),
        ("अन्तराधिकरणम्", 2), ("आकाशाधिकरणम्", 1), ("प्राणाधिकरणम्", 1),
        ("ज्योतिरधिकरणम्", 4), ("इन्द्र-प्राणाधिकरणम्", 5),
    ],
    [  # pada 2 (7 adhikarana, 33 sutras)
        ("सर्वत्र-प्रसिद्ध्यधिकरणम्", 8), ("अन्तराधिकरणम्", 2), ("गुहाधिकरणम्", 2),
        ("अन्तराधिकरणम्", 7), ("अन्तर्व्याप्यधिकरणम्", 1), ("अदृश्यत्वाधिकरणम्", 4),
        ("वैश्वानराधिकरणम्", 9),
    ],
    [  # pada 3 (12 adhikarana, 43 sutras)
        ("ध्रुवाधिकरणम्", 7), ("भूमाधिकरणम्", 2), ("अक्षराधिकरणम्", 3),
        ("ईक्षति-कर्माधिकरणम्", 1), ("दहराधिकरणम्", 10), ("प्रतिमाधिकरणम्", 2),
        ("देवताधिकरणम्", 5), ("भावाधिकरणम्", 3), ("अपशूद्राधिकरणम्", 5),
        ("कम्पनाधिकरणम्", 2), ("आकाशाधिकरणम्", 1), ("उत्क्रान्त्यधिकरणम्", 2),
    ],
    [  # pada 4 (8 adhikarana, 28 sutras)
        ("आनुमानिकाधिकरणम्", 7), ("चमसाधिकरणम्", 3), ("सङ्ख्योपसङ्ग्रहाधिकरणम्", 3),
        ("कारणत्वाधिकरणम्", 2), ("जगद्-वाचित्वाधिकरणम्", 3), ("वाक्यान्वयाधिकरणम्", 4),
        ("प्रकृत्य्-अधिकरणम्", 5), ("सर्व-व्याख्याता-अधिकरणम्", 1),
    ],
]

ADHYAYA1_START, ADHYAYA1_END = 17, 1903
PADA_STARTS = [17, 529, 927, 1473, 1903]


def pada_of(idx):
    for p in range(4):
        if PADA_STARTS[p] <= idx < PADA_STARTS[p + 1]:
            return p
    raise ValueError(idx)


def build_sutra_units(orig_paras):
    """Ordered list of sutra units; each unit is a tuple of raw docx
    paragraph indices (len 1 unless merged per MERGE_GROUPS)."""
    candidates = []
    for idx in range(ADHYAYA1_START, ADHYAYA1_END):
        t = orig_paras[idx].strip()
        if not t or "o)0(o" in t:
            continue
        if _SECTION_NUM_RE.match(t) or _LABEL_RE.match(t) or _MARKER_RE.match(t):
            continue
        from generate_govinda_bhashya import para_is_fully_bold
        # re-imported locally to avoid unused-import lint noise at module load
        candidates.append(idx)
    return candidates


def main():
    doc = Document("govinda-bhashya_-_baladeva_vidyabhushana.docx")
    orig_para_objs = list(iter_all_paragraphs(doc))
    orig_paras = [paragraph_full_text(p).strip() for p in orig_para_objs]

    from generate_govinda_bhashya import para_is_fully_bold
    candidates = [i for i in build_sutra_units(orig_paras) if para_is_fully_bold(orig_para_objs[i])]

    merge_map = {}
    for group in MERGE_GROUPS:
        for i in group:
            merge_map[i] = group
    sutra_units = []
    consumed = set()
    for idx in candidates:
        if idx in consumed:
            continue
        group = merge_map.get(idx, (idx,))
        sutra_units.append(group)
        consumed.update(group)

    units_by_pada = [[], [], [], []]
    for u in sutra_units:
        units_by_pada[pada_of(u[0])].append(u)

    for p in range(4):
        expected = sum(c for _, c in PADA_ADHIKARANAS[p])
        actual = len(units_by_pada[p])
        assert actual == expected, f"pada {p+1}: expected {expected} sutra units, got {actual}"

    # Precompute, for every sutra unit's first paragraph index, exactly
    # which (pada, adhikarana_index_within_pada) it belongs to. This is a
    # direct lookup (not a stateful running counter), so pada transitions
    # can't desync it.
    unit_assignment = {}  # first_idx -> (pada, a_idx)
    for p in range(4):
        pos = 0
        for a_idx, (name, count) in enumerate(PADA_ADHIKARANAS[p]):
            for _ in range(count):
                unit_assignment[units_by_pada[p][pos][0]] = (p, a_idx)
                pos += 1

    unit_start_idx = {u[0]: u for u in sutra_units}
    first_unit_first_idx = sutra_units[0][0]  # adhikaranam 1's own sutra (hand-built already)

    import re as _re
    _TRAILING_SUTRA_MARKER_RE = _re.compile(r"\s*\|\|\s*\d+\s*\|\|?\s*$")

    def render_unit_text(group):
        parts = [orig_paras[i].strip() for i in group]
        # Strip the source's own embedded sutra-number marker (e.g. "||5||")
        # from a merged unit's trailing text -- it's Baladeva's own running
        # count annotation, not part of the sutra itself.
        parts = [_TRAILING_SUTRA_MARKER_RE.sub("", p) for p in parts]
        return convert_text(" ".join(parts))

    out_lines = []
    current_texts = []
    current_key = None  # (pada, a_idx) currently being accumulated
    adhy_counter = [2]  # adhikaranam 1 already hand-built on the site

    def flush():
        nonlocal current_texts, current_key
        if current_key is None or not current_texts:
            current_texts = []
            return
        p, a_idx = current_key
        name, _ = PADA_ADHIKARANAS[p][a_idx]
        num = to_dev(adhy_counter[0])
        heading = f"## अधिकरणम् {num}"
        tags = []
        if a_idx == 0:
            tags.append(f"पादः {to_dev(p + 1)}")
        tags.append(name)
        heading += " (" + ", ".join(tags) + ")"
        out_lines.append(heading)
        out_lines.append("")
        out_lines.append(render_adhikarana(current_texts))
        current_texts = []
        adhy_counter[0] += 1

    # Start right after adhikaranam 1's own sutra paragraph (its trailing
    # explanation, up to sutra-unit 2's start, is already on the site).
    idx = first_unit_first_idx + 1
    # skip straight to sutra unit index 1 (the second sutra overall)
    idx = sutra_units[1][0]

    while idx < ADHYAYA1_END:
        if idx in unit_start_idx:
            group = unit_start_idx[idx]
            key = unit_assignment[idx]
            if key != current_key:
                flush()
                current_key = key
            text = render_unit_text(group)
            if text:
                current_texts.append((text, False, True))
            idx = group[-1] + 1
            continue

        t = orig_paras[idx].strip()
        if not t or "o)0(o" in t or _SECTION_NUM_RE.match(t) or _LABEL_RE.match(t) or _MARKER_RE.match(t):
            idx += 1
            continue
        conv_t = convert_text(t)
        if conv_t:
            color = para_dominant_color(orig_para_objs[idx])
            quoted = color in ("0000FF", "3366FF")
            current_texts.append((conv_t, quoted, False))
        idx += 1

    flush()

    with open("/tmp/adhyaya1_rebuilt.md", "w", encoding="utf-8") as f:
        f.write("\n\n".join(out_lines))
    print(f"wrote /tmp/adhyaya1_rebuilt.md, adhikaranas 2..{adhy_counter[0]-1}")


if __name__ == "__main__":
    main()
