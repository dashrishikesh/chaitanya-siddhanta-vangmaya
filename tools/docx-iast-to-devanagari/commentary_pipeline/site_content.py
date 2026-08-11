"""Parses the site's existing hand-maintained .md grantha files into a
per-anuccheda structure, for content-matching against a docx source.

The heading conventions vary across files (some historical, not worth
normalizing away since they're cosmetic on the site):
  - "## अनुच्छेदः N"       (mangalacharanam, pramana-prakaranam)
  - "## मूल-अनुच्छेदः N"   (prameya-prakaranam)
  - "## प्रमेयम् N"         (prameya-prakaranam, a handful of sections --
                             same structural role, different label; the
                             N here is NOT the running anuccheda number,
                             it's a separate topic-index)
So the running anuccheda number (1..63) is assigned purely by *position*
across the ordered file list, not parsed from the heading text. Where a
heading does carry an explicit "अनुच्छेदः N"/"मूल-अनुच्छेदः N" number,
that's cross-checked against the positional count and a mismatch is
reported rather than silently trusted either way.
"""

import re
from dataclasses import dataclass, field

_DEVANAGARI_DIGITS = "०१२३४५६७८९"


def devanagari_to_int(s: str) -> int:
    return int("".join(str(_DEVANAGARI_DIGITS.index(c)) for c in s))


_HEADING_NUMBER_RE = re.compile(r"^(?:मूल-)?अनुच्छेदः\s+([०-९]+)$")


@dataclass
class AnucchedaSection:
    anuccheda_num: int  # positional, authoritative
    heading_text: str
    heading_declared_num: int | None  # parsed from heading text, if any
    source_file: str
    root_quote: str
    commentaries: dict = field(default_factory=dict)  # label -> text


def _strip_frontmatter(md_text: str) -> str:
    parts = md_text.split("---\n", 2)
    return parts[2] if len(parts) >= 3 else md_text


def parse_file(path: str):
    """Yields (heading_text, heading_declared_num, root_quote, commentaries)
    for every '## ' section in the file, in document order.
    """
    with open(path, encoding="utf-8") as f:
        body = _strip_frontmatter(f.read())

    # Split on '## ' headings (top-level anuccheda sections).
    section_re = re.compile(r"^## (.+)$", re.MULTILINE)
    matches = list(section_re.finditer(body))
    for i, m in enumerate(matches):
        heading_text = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_body = body[start:end]

        num_match = _HEADING_NUMBER_RE.match(heading_text)
        declared_num = devanagari_to_int(num_match.group(1)) if num_match else None

        # Split section_body on '### ' commentary subheadings.
        sub_re = re.compile(r"^### (.+)$", re.MULTILINE)
        sub_matches = list(sub_re.finditer(section_body))
        root_quote = section_body[: sub_matches[0].start()].strip() if sub_matches else section_body.strip()

        commentaries = {}
        for j, sm in enumerate(sub_matches):
            label_raw = sm.group(1).strip()
            # strip leading emoji markers (🔷/🔶) and trailing "*(...)*" notes
            label = re.sub(r"^[^\wऀ-෿]+", "", label_raw)
            label = re.sub(r"\s*\*.*\*\s*$", "", label).strip()
            sub_start = sm.end()
            sub_end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(section_body)
            commentaries[label] = section_body[sub_start:sub_end].strip()

        yield heading_text, declared_num, root_quote, commentaries


def build_anuccheda_index(file_paths_in_order):
    """Returns (list[AnucchedaSection], list[str] warnings)."""
    sections = []
    warnings = []
    running_num = 0
    for path in file_paths_in_order:
        for heading_text, declared_num, root_quote, commentaries in parse_file(path):
            running_num += 1
            if declared_num is not None and declared_num != running_num:
                warnings.append(
                    f"{path}: heading '{heading_text}' declares अनुच्छेदः "
                    f"{declared_num} but positional count is {running_num}"
                )
            sections.append(
                AnucchedaSection(
                    anuccheda_num=running_num,
                    heading_text=heading_text,
                    heading_declared_num=declared_num,
                    source_file=path,
                    root_quote=root_quote,
                    commentaries=commentaries,
                )
            )
    return sections, warnings
