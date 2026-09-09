"""Stage 1: normalize. Everything downstream matches against this output,
never the raw text — the two hard cases a naive pattern match misses are both
fixed here: a zero-width character welded into the middle of a trigger word
(stripped before matching, not left for the pattern to work around), and
Arabic letter-shape variants and diacritics that read as the same word but
wouldn't string-match (folded to one canonical form).

Every non-ASCII code point below is written as an explicit ``\\uXXXX`` escape
rather than a literal invisible/combining character, so this file stays
reviewable in a plain diff instead of hiding the exact thing it's about.
"""

from __future__ import annotations

import re
import unicodedata

# Zero-width space, zero-width non-joiner, zero-width joiner, BOM / zero-width
# no-break space, word joiner — the usual toolkit for splicing a character
# into the middle of a word while it still *looks* intact.
_ZERO_WIDTH = re.compile("[​‌‍﻿⁠]")

# Arabic kashida/tatweel — stretches a word visually, carries no letter value.
_TATWEEL = re.compile("ـ")

# Arabic diacritics (tashkeel + Quranic annotation marks) — optional marks a
# word means the same without.
_ARABIC_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")

# Alef variants -> bare alef, alef maksura -> yaa, taa marbuta -> haa. Two
# spellings of the same word shouldn't need two entries in a pattern list.
_ARABIC_LETTER_VARIANTS = str.maketrans(
    {
        "أ": "ا",  # أ -> ا
        "إ": "ا",  # إ -> ا
        "آ": "ا",  # آ -> ا
        "ٱ": "ا",  # ٱ -> ا
        "ى": "ي",  # ى -> ي
        "ة": "ه",  # ة -> ه
    }
)

_WHITESPACE = re.compile(r"\s+")

# Basic Arabic Unicode block, used only to guess a language tag for choosing
# a bilingual refusal — not a translation or script-detection tool.
ARABIC_RANGE = re.compile("[؀-ۿ]")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    text = _TATWEEL.sub("", text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(_ARABIC_LETTER_VARIANTS)
    text = _WHITESPACE.sub(" ", text).strip()
    return text.casefold()


def detect_language(text: str) -> str:
    return "ar" if ARABIC_RANGE.search(text) else "en"
