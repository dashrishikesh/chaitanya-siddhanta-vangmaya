#!/usr/bin/env python3
"""Maps every Brahma-sutra number (adhyaya.pada.sutra) to the Govinda-
bhashya adhikarana (site section) that comments on it.

Govinda-bhashya IS Baladeva Vidyabhushana's own sutra-by-sutra commentary
on the Brahma-sutra -- each sutra's own text is quoted inline (rendered
site-side as `<p class="sutra">...</p>`) rather than cited by
"[ब्र.सू. N.N.N]" bracket notation the way the Sandarbhas cite it. The
source docx carries an explicit "|| N.N.N ||" marker at the START of
each sutra's discussion (opponent's-view prose usually comes first, the
sutra's own bold text -- para_is_fully_bold, same predicate
generate_govinda_bhashya.py's site pipeline uses -- follows later within
that same discussion), but generate_govinda_bhashya.py's own site
generation discards these markers (not needed for on-page readability).

Rather than re-deriving adhikarana chunk boundaries independently (risky
-- adhyaya-1 was manually reconciled after the first automatic pass per
project history, so a fresh re-walk with the base algorithm doesn't
reliably reproduce the CURRENT site file's exact boundaries -- confirmed
by a section-count mismatch on adhyaya 2-4 too), this script grounds
truth directly in the actual site markdown: for each "|| N.N.N ||"
marker, find the next fully-bold paragraph after it (the sutra's own
text), convert it to Devanagari, and locate that exact string as a
`<p class="sutra">...</p>` line in the real
src/content/granthas/govinda-bhashya-adhyaya-{1..4}.md file -- then the
nearest preceding "## " heading is the sutra's true site section.

Output: govinda_bhashya_sutra_map.json
  { "1.1.1": {"workSlug": "govinda-bhashya", "file": "govinda-bhashya-adhyaya-1",
              "sectionIndex": 1, "heading": "अधिकरणम् १ (...)"}, ... }
"""
import json
import re

from docx import Document

from docx_walk import iter_all_paragraphs
from paragraph_rewrite import paragraph_full_text
from generate_govinda_bhashya import convert_text, para_is_fully_bold

REPO = "/Users/hrishikeshagarwal/Projects/chaitanya-siddhanta-vangmaya"
_MARKER_RE = re.compile(r"^\|\|\s*(\d+)\.(\d+)\.(\d+)\s*\|\|$")
_PADA_HEADER_RE = re.compile(
    r"(prathamo|dvitīyo|tṛtīyo|caturtho)['’]?dhyāy|(prathamaḥ|dvitīyaḥ|tṛtīyaḥ|caturthaḥ)\s*pādaḥ",
    re.IGNORECASE,
)
ADHYAYA_WORDS = ["prathamo", "dvitīyo", "tṛtīyo", "caturtho"]

OUT_PATH = "govinda_bhashya_sutra_map.json"


def find_adhyaya_for_index(paras, idx):
    """Scans backward from idx for the most recent 'N-adhyāyaḥ' heading to
    determine which of the 4 adhyaya files this index belongs to."""
    for i in range(idx, -1, -1):
        t = paras[i].lower().strip()
        if len(t) > 70 or not _PADA_HEADER_RE.search(t):
            continue
        for adhy_i, word in enumerate(ADHYAYA_WORDS):
            if word in t:
                return adhy_i
    return 0


def main():
    doc = Document("govinda-bhashya_-_baladeva_vidyabhushana.docx")
    orig_para_objs = list(iter_all_paragraphs(doc))
    orig_paras = [paragraph_full_text(p).strip() for p in orig_para_objs]

    markers = []
    for i, t in enumerate(orig_paras):
        m = _MARKER_RE.match(t)
        if m:
            markers.append((i, int(m.group(1)), int(m.group(2)), int(m.group(3))))
    print(f"found {len(markers)} sutra markers in docx")

    # For each marker, find the run of fully-bold paragraphs after it (the
    # sutra's own text) and convert it to Devanagari. A sutra sometimes
    # spans more than one docx paragraph (e.g. 1.4.1's two bold lines,
    # "ānumānikam apy ekeṣām iti cen, na," + "śarīra-rūpa-kavi-nyasta-
    # gṛhīter darśayati ca" -- consecutive bold paragraphs, no blank
    # paragraph between them, that the site renders as one combined
    # `<p class="sutra">` line). Keep every prefix-concatenation (first
    # bold paragraph alone, first+second, first+second+third, ...) as a
    # separate candidate, since the site's own text isn't known yet at
    # this point -- whichever prefix length matches wins in the lookup
    # below.
    sutra_candidates = {}  # (a,p,s) -> [candidate devanagari text, longest first]
    for i, a, p, s in markers:
        bold_runs = []
        started = False
        for j in range(i + 1, min(i + 400, len(orig_paras))):
            t = orig_paras[j].strip()
            if not t:
                continue  # blank lines don't end the run -- only a non-bold paragraph does
            if not para_is_fully_bold(orig_para_objs[j]):
                if started:
                    break
                continue
            started = True
            conv = convert_text(t)
            if conv:
                bold_runs.append(conv.strip().strip("॥ "))
            if len(bold_runs) >= 6:
                break
        if bold_runs:
            candidates = [" ".join(bold_runs[:n]) for n in range(len(bold_runs), 0, -1)]
            sutra_candidates[(a, p, s)] = candidates

    print(f"resolved sutra text for {len(sutra_candidates)}/{len(markers)} markers")

    # Load each adhyaya's site markdown, split into (heading, section_index)
    # spans by "## " position, and index every `<p class="sutra">...</p>`
    # line's containing span.
    adhyaya_sutra_index = {}  # adhy_num(1-4) -> [(sutra_text, section_index, heading), ...]
    for adhy_num in range(1, 5):
        path = f"{REPO}/src/content/granthas/govinda-bhashya-adhyaya-{adhy_num}.md"
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        entries = []
        section_index = -1
        heading = None
        for line in lines:
            h2 = re.match(r"^##\s+(.*)$", line)
            if h2:
                section_index += 1
                heading = h2.group(1).strip()
                continue
            m = re.search(r'<p class="sutra">(.*?)</p>', line)
            if m:
                entries.append((m.group(1).strip(), section_index, heading))
        adhyaya_sutra_index[adhy_num] = entries
        print(f"adhyaya {adhy_num}: {len(entries)} <p class=\"sutra\"> lines indexed")

    sutra_map = {}
    unresolved = []
    for (a, p, s), candidates in sutra_candidates.items():
        found = False
        for candidate in candidates:
            for adhy_num, entries in adhyaya_sutra_index.items():
                for sutra_text, section_index, heading in entries:
                    if sutra_text == candidate:
                        key = f"{a}.{p}.{s}"
                        sutra_map[key] = {
                            "workSlug": "govinda-bhashya",
                            "file": f"govinda-bhashya-adhyaya-{adhy_num}",
                            "sectionIndex": section_index,
                            "heading": heading,
                        }
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:
            unresolved.append((a, p, s, candidates[0]))

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sutra_map, f, ensure_ascii=False, indent=1)
    print(f"{OUT_PATH}: {len(sutra_map)} sutra numbers mapped, {len(unresolved)} unresolved")
    for a, p, s, text in unresolved[:20]:
        print(f"  unresolved {a}.{p}.{s}: {text[:50]}")


if __name__ == "__main__":
    main()
