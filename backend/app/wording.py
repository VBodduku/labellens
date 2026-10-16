"""Fixed user-facing wording shared by summaries, the agent and its templates.

Verdict states always use these words; "safe", "healthy", "guaranteed" (and their Hindi/Telugu
equivalents) are never shown. Hindi and Telugu strings need native-speaker review.
"""
from __future__ import annotations

import re

from shared.contract import Lang, VerdictState

LANGUAGE_NAMES: dict[Lang, str] = {"en": "English", "hi": "Hindi", "te": "Telugu"}

# REVIEW: native speaker (hi, te)
STATE_WORDS: dict[Lang, dict[VerdictState, str]] = {
    "en": {"conflict": "Conflict", "possible": "Check this", "not_listed": "Not listed", "unknown": "Can't determine"},
    "hi": {"conflict": "टकराव", "possible": "इसे जाँचें", "not_listed": "सूची में नहीं", "unknown": "तय नहीं हो सका"},
    "te": {"conflict": "విరుద్ధం", "possible": "దీన్ని తనిఖీ చేయండి", "not_listed": "జాబితాలో లేదు",
           "unknown": "నిర్ణయించలేము"},
}

# REVIEW: native speaker (hi, te)
BANNED: dict[Lang, list[str]] = {
    "en": ["safe", "safely", "healthy", "guaranteed", "guarantee", "risk-free", "no risk", "probably fine",
           "harmless"],
    "hi": ["सुरक्षित", "स्वस्थ", "सेहतमंद", "गारंटी", "कोई खतरा नहीं", "हानिरहित"],
    "te": ["సురక్షితం", "సురక్షితమైన", "ఆరోగ్యకరం", "ఆరోగ్యకరమైన", "హామీ", "ప్రమాదం లేదు"],
}
ALL_BANNED = [w for words in BANNED.values() for w in words]


def has_banned_word(text: str) -> bool:
    lowered = text.casefold()
    for word in ALL_BANNED:
        if word.isascii():
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                return True
        elif word in text:
            return True
    return False
