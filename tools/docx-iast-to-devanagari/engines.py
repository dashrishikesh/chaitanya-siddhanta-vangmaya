"""Wraps both transliteration engines, the language-detection gate, and
the cross-validation logic.
"""

import os
import re
import unicodedata

from aksharamukha import transliterate as aksharamukha_transliterate
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate as sanscript_transliterate
import sentencepiece as spm

# IAST diacritics: precomposed Latin-Extended-A/B + combining marks used by IAST.
_IAST_DIACRITIC_RE = re.compile(
    "[Ā-ſḀ-ỿ̀-ͯ]"  # Latin Extended-A/B, combining diacriticals
)

# --- language-detection gate (dharmamitra/detect-language) ---------------
#
# Loaded once at import time -- model loading is the expensive part;
# encoding a paragraph afterwards is cheap even at thousands-of-
# paragraphs scale. Models are vendored into ./models/ so this tool
# doesn't depend on the separately-cloned detect-language repo sticking
# around at a particular relative path.
_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_eng_sp = spm.SentencePieceProcessor()
_eng_sp.load(os.path.join(_MODELS_DIR, "eng.model"))
_skt_sp = spm.SentencePieceProcessor()
_skt_sp.load(os.path.join(_MODELS_DIR, "skt.model"))


def classify_language(text: str) -> str:
    """'en' or 'sa' -- whichever SentencePiece model's vocabulary
    compresses the text into fewer subword pieces is the better fit.
    NOTE: this reports the *dominant* language of the whole string, not
    "does this string contain any of language X" -- a short English
    label glued onto a longer Sanskrit sentence will still read as 'sa'
    overall (verified: "footnote body: nandīśvareśvara iti smṛtaḥ" ->
    'sa'). That's exactly what has_mixed_language_run() below exists to
    catch; the two checks are deliberately independent, not redundant.
    """
    len_eng = len(_eng_sp.encode_as_pieces(text))
    len_skt = len(_skt_sp.encode_as_pieces(text))
    return "en" if len_eng < len_skt else "sa"


def looks_like_sanskrit(text: str) -> bool:
    """Primary gate: is this paragraph worth sending to the
    transliteration engines at all?

    Combines two independent signals with OR, since each one misses
    things the other catches and a missed conversion (silently skipping
    real Sanskrit) is worse than a redundant check:

    - The SentencePiece classifier catches diacritic-free Sanskrit
      (nimittam, api, uddhava, tatra, sarva, iti...) that a pure
      diacritic check structurally can't see.
    - The diacritic check catches short single-line verses with
      unusual compound proper nouns that throw the classifier off --
      verified on this project's own data: "vana-dhātu-vicitrāṅga-
      barhi-barhāvataṁsaka ||128||", "advaitācārya-saṁślāghin
      sārvabhaumābhinandaka |" and similar short lines are unambiguously
      real Sanskrit (real IAST diacritics present) but the classifier
      alone called them 'en'.

    Already-Devanagari text is excluded either way -- nothing left to
    convert.
    """
    if not text or not text.strip():
        return False
    if has_devanagari(text):
        return False
    if looks_like_iast(text):
        return True
    if not re.search("[A-Za-z]", text):
        return False  # nothing for the classifier to work with either
    return classify_language(text) == "sa"


def looks_like_iast(text: str) -> bool:
    """Superseded by looks_like_sanskrit() as the pipeline's gate --
    kept because it's a useful, dependency-free cheap check (e.g. for
    quick scripts/tests that don't want to load the SentencePiece
    models) and because has_mixed_language_run() still special-cases on
    "does this look like it has IAST in it at all".
    """
    if not text or not text.strip():
        return False
    return bool(_IAST_DIACRITIC_RE.search(unicodedata.normalize("NFC", text)))


# IMPORTANT CAVEAT: plenty of genuine Sanskrit words are diacritic-free
# in IAST (nimittam, api, uddhava, tatra, sarva, iti ...) since they
# contain none of the sounds IAST marks specially (ā ī ū ṛ ṝ ḷ ṃ ḥ ś ṣ ṇ ṭ
# ḍ ñ ṅ). So "N consecutive ASCII words" is NOT a safe signal of English
# prose on its own -- it false-positives on ordinary Sanskrit phrases.
# We only flag two much more specific, lower-false-positive patterns:
#
#  1. A short ASCII-only run immediately followed by ':' at or near the
#     start of the paragraph -- the "Note:" / "Editor's note:" / label
#     pattern that's how English asides actually show up inside these
#     documents (this is the exact shape of the footnote test failure).
#  2. A long run of ASCII words containing at least one common English
#     function word (the/of/and/is/this/that/with/...) -- function
#     words essentially never appear in IAST Sanskrit transliteration,
#     so their presence is a strong, low-false-positive English signal
#     even without a colon.
# Split into two confidence tiers. Real Sanskrit/Vedic vocabulary
# collides with common short English words often enough in commentarial
# prose (are <- Bṛ.U. 2.4.5 "ātmā vā are draṣṭavyaḥ", cit <- चित्
# "consciousness", no <- Vedic enclitic "naḥ") that a single hit on one
# of those is not reliable signal by itself -- verified against this
# project's actual data, where "no"/"cit"/"are" each produced false
# positives on pure-Sanskrit philosophical text quoting the Upaniṣads.
# Most citation-apparatus words (chapter/editor/translator/...) still
# never coincide with genuine Sanskrit tokens, so one hit on those is
# trusted on its own. "ibid"/"page"/"pages" turned out NOT to belong
# here though -- confirmed against this project's data: "[page 6]" and
# "[ibid.]" are single-word bracketed citation markers that this
# document's editor drops inline inside otherwise pure-Sanskrit
# commentary paragraphs (a normal convention in this text), not
# standalone English prose -- a whole paragraph shouldn't be withheld
# from conversion just because it contains one such marker.
_HIGH_CONFIDENCE_ENGLISH_WORDS = {
    "see", "cf", "editor", "translator", "translation",
    "chapter", "footnote", "endnote", "op", "trans", "vol",
    "manuscript", "variant", "note",
}
_LOW_CONFIDENCE_ENGLISH_WORDS = {
    "the", "of", "and", "is", "are", "was", "were", "this", "that", "these",
    "those", "with", "from", "into", "onto", "for", "not", "but", "or",
    "as", "by", "on", "in", "at", "to", "be", "been", "has", "have", "had",
    "will", "would", "should", "could", "can", "may", "might",
    "cit", "ed", "no", "text", "reading", "source", "ibid", "page", "pages",
}
_ENGLISH_FUNCTION_WORDS = _HIGH_CONFIDENCE_ENGLISH_WORDS | _LOW_CONFIDENCE_ENGLISH_WORDS
_ASCII_WORD_RE = re.compile(r"[A-Za-z]+")


def has_mixed_language_run(text: str) -> bool:
    """True if the paragraph contains IAST *and* a strong signal of
    genuine English prose mixed in (not just diacritic-free Sanskrit) --
    converting the whole paragraph blindly in that case corrupts the
    English portion (see footnote test case / README).
    """
    if not looks_like_iast(text):
        return False

    # Pattern 1: "Word word:" (1-4 ASCII words then a colon) near the start.
    label_match = re.match(r"^\s*((?:[A-Za-z]+[\s]*){1,4}):", text)
    if label_match and not _IAST_DIACRITIC_RE.search(label_match.group(1)):
        return True

    # Pattern 2: whole whitespace-delimited tokens that are entirely ASCII
    # and exactly match a recognized English function word. This checks
    # *whole tokens*, not regex-found ASCII substrings within a larger
    # word -- an earlier version used _ASCII_WORD_RE.findall(text) directly
    # on the paragraph, which finds ASCII runs *inside* IAST words that an
    # interior diacritic happens to split (e.g. "yogeśas" -> "yoge" + "as",
    # "prakaṭin" -> "praka" + "in", "he'no" -> "he" + "no"), each of which
    # can coincidentally spell an English stopword. That produced 23/23
    # false positives on real, pure-Sanskrit verse lines in this project's
    # data. Stripping surrounding punctuation and internal hyphens/
    # apostrophes (compound joiners / sandhi elision marks in this corpus)
    # before checking whole-token ASCII-ness avoids that.
    #
    # A single high-confidence hit (citation-apparatus vocabulary) is
    # trusted on its own. Low-confidence hits (short words that collide
    # with real Sanskrit/Vedic vocabulary) need at least 2 *distinct*
    # matches -- one stray "cit"/"are"/"no" is exactly as likely to be
    # real Sanskrit as English, but genuine English prose reliably uses
    # more than one such word.
    low_confidence_hits = set()
    for raw_tok in text.split():
        tok = raw_tok.strip("|()[]{}.,;:!?\"'’‘").replace("-", "").replace("'", "").replace("’", "")
        if not (tok and tok.isascii() and tok.isalpha()):
            continue
        tok_lower = tok.lower()
        if tok_lower in _HIGH_CONFIDENCE_ENGLISH_WORDS:
            return True
        if tok_lower in _LOW_CONFIDENCE_ENGLISH_WORDS:
            low_confidence_hits.add(tok_lower)

    return len(low_confidence_hits) >= 2


def has_devanagari(text: str) -> bool:
    return bool(re.search("[ऀ-ॿ]", text))


def has_latin_letters(text: str) -> bool:
    return bool(re.search("[a-zA-Z]", text))


_IAST_CHARS = r"a-zA-Zāīūṛṝḷḹṅñṭḍṇśṣṁṃḥ'"
_COMPOUND_HYPHEN_RE = re.compile(rf"(?<=[{_IAST_CHARS}])-(?=[{_IAST_CHARS}])")


def join_compound_hyphens(text: str) -> str:
    """śrī-kṛṣṇa -> śrīkṛṣṇa

    Devanagari has no hyphen convention for compounds -- the source IAST
    hyphenates compound elements for readability (śrī-kṛṣṇa), but the
    printed Devanagari should join them (श्रीकृष्ण). Only hyphens directly
    between two IAST letters are stripped, so a hyphen at an actual word
    boundary (adjacent to punctuation/space, none found in this corpus)
    would be left untouched.
    """
    return _COMPOUND_HYPHEN_RE.sub("", text)


def normalize_avagraha_quotes(text: str) -> str:
    """te’tisudhā -> te'tisudhā

    Word's autocorrect turns a typed straight apostrophe (the IAST
    avagraha marker) into a curly right single quotation mark (U+2019).
    aksharamukha only recognizes the straight apostrophe as avagraha and
    passes U+2019 through untransliterated (verified: transliterating
    "te'tisudhā" -> "तेऽतिसुधा" but "te’tisudhā" -> "ते’तिसुधा",
    leaving the raw curly quote sitting inside otherwise-Devanagari text).
    Found in 11 paragraphs of this project's source document.
    """
    return text.replace("’", "'").replace("‘", "'")


def transliterate_aksharamukha(text: str) -> str:
    return aksharamukha_transliterate.process("IAST", "Devanagari", text)


def transliterate_sanscript(text: str) -> str:
    return sanscript_transliterate(text, sanscript.IAST, sanscript.DEVANAGARI)


def transliterate_with_cross_check(text: str):
    """Returns (chosen_output, agree: bool, aksharamukha_out, sanscript_out)."""
    text = normalize_avagraha_quotes(join_compound_hyphens(text))
    out_a = transliterate_aksharamukha(text)
    out_b = transliterate_sanscript(text)
    agree = out_a.strip() == out_b.strip()
    # aksharamukha is the documented primary choice; used as the
    # written-back value even on disagreement (paragraph is still
    # logged to the review CSV so a human checks it).
    return out_a, agree, out_a, out_b
