"""Natural-language profile setup ("My son is allergic to peanuts and I'm Jain") -> Profiles.

The LLM proposes people and restriction keys; everything is then validated deterministically
against the engine catalog (unknown keys -> unparsed, severity from wording, kind/label/threshold
from the catalog). Without an LLM, a keyword matcher builds a single "Me" profile.
needs_confirmation is always True: the user confirms before anything is saved.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from backend.app import engine_adapter
from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from shared.contract import Lang, Profile, ProfileParseResponse, Restriction, RestrictionCatalogItem, Severity

PROMPT = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "parse_profile.md"
BASIC_PARSING_WARNING = "basic_parsing"

_STRICT = re.compile(r"allerg|anaphyla|celiac|coeliac|एलर्जी|ఎలర్జీ|అలెర్జీ|అలర్జీ", re.IGNORECASE)
_PREFERENCE = re.compile(r"\bavoid|prefer not|prefers not|trying to (cut|reduce)|cut down|\bless\b|\breduce|"
                         r"कम|परहेज|తగ్గించ|తక్కువ", re.IGNORECASE)

# Keyword fallback, most specific first: (pattern, catalog key).
_KEYWORDS: list[tuple[str, str]] = [
    (r"eggetarian", "eggetarian"),
    (r"\bvegan\b|वीगन|వీగన్", "vegan"),
    (r"\bjain\b|जैन|జైన", "jain"),
    (r"onion|garlic|प्याज|लहसुन|ఉల్లి|వెల్లుల్లి", "no_onion_garlic"),
    (r"vegetarian|शाकाहारी|శాకాహార", "vegetarian"),
    (r"peanut|groundnut|मूंगफली|वेरुशेनगा|వేరుశెనగ|పల్లీ", "peanut"),
    (r"tree ?nut|cashew|almond|walnut|pistachio|काजू|बादाम|జీడిపప్పు|బాదం", "tree_nut"),
    (r"lactose", "lactose"),
    (r"\bmilk\b|dairy|दूध|పాలు", "milk"),
    (r"\beggs?\b|अंडा|अंडे|గుడ్డు", "egg"),
    (r"gluten|celiac|coeliac", "gluten"),
    (r"wheat|गेहूं|గోధుమ", "wheat"),
    (r"\bsoy|सोया", "soy"),
    (r"sesame|\btil\b|तिल|నువ్వు", "sesame"),
    (r"shellfish|prawn|shrimp|crab|झींगा|రొయ్య", "crustacean"),
    (r"\bfish\b|मछली|చేప", "fish"),
    (r"mustard|सरसों|ఆవాలు", "mustard"),
    (r"diabet|sugar|शुगर|मधुमेह|డయాబెటి|షుగర్|చక్కెర", "diabetes_sugar"),
    (r"\bb\.?p\b|blood pressure|hypertension|sodium|\bsalt\b|नमक|बीपी|రక్తపోటు|బీపీ|ఉప్పు", "low_sodium"),
    (r"cholesterol|saturated fat|कोलेस्ट्रॉल|కొలెస్ట్రాల్", "low_sat_fat"),
    (r"palm oil", "palm_oil"),
    (r"caffeine|कैफीन", "caffeine"),
    (r"alcohol|शराब", "alcohol"),
    (r"\bmsg\b|ajinomoto", "added_msg"),
    (r"sweetener|aspartame|sucralose", "artificial_sweetener"),
]


class LLMRestriction(BaseModel):
    key: str
    severity: Optional[Literal["strict", "preference"]] = None
    source_text: str


class LLMPerson(BaseModel):
    name: str
    restrictions: list[LLMRestriction]


class LLMProfileParse(BaseModel):
    people: list[LLMPerson]
    unparsed: list[str]


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def severity_for(text: str, proposed: Optional[Severity], item: RestrictionCatalogItem) -> Severity:
    if _STRICT.search(text):
        return "strict"
    if _PREFERENCE.search(text):
        return "preference"
    return proposed or item.default_severity


def restriction(item: RestrictionCatalogItem, severity: Severity, source_text: str) -> Restriction:
    return Restriction(
        id=_id("r"), kind=item.kind, key=item.key, label=item.label_en, severity=severity,
        threshold=item.default_threshold if item.needs_threshold else None, source_text=source_text or None,
    )


def build_response(parsed: LLMProfileParse, catalog: dict[str, RestrictionCatalogItem]) -> ProfileParseResponse:
    unparsed = [u.strip() for u in parsed.unparsed if u.strip()]
    profiles: list[Profile] = []
    for person in parsed.people:
        restrictions: list[Restriction] = []
        for r in person.restrictions:
            item = catalog.get(r.key.strip())
            if item is None:
                unparsed.append(r.source_text.strip() or r.key)
            elif item.key not in {x.key for x in restrictions}:
                restrictions.append(restriction(item, severity_for(r.source_text, r.severity, item), r.source_text))
        if restrictions:
            profiles.append(Profile(profile_id=_id("p"), name=person.name.strip() or "Me", restrictions=restrictions))
    return ProfileParseResponse(profiles=profiles, unparsed=list(dict.fromkeys(unparsed)), needs_confirmation=True)


def keyword_keys(text: str, catalog: dict[str, RestrictionCatalogItem]) -> list[str]:
    """Catalog keys whose keywords appear in the text, in order of first mention."""
    found: dict[str, int] = {}                  # key -> position of its first mention
    for pattern, key in _KEYWORDS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and key in catalog and key not in found:
            if key == "vegetarian" and {"vegan", "eggetarian", "jain"} & set(found):
                continue
            found[key] = match.start()
    return sorted(found, key=found.__getitem__)


def missed_warnings(response: ProfileParseResponse, text: str, catalog: dict[str, RestrictionCatalogItem]) -> list[str]:
    """Needs the keyword matcher sees but the model dropped: ask the user to add them when confirming."""
    parsed = {r.key for p in response.profiles for r in p.restrictions}
    return [f"Also mentioned: {catalog[k].label_en}. Add it to the right person if it applies."
            for k in keyword_keys(text, catalog) if k not in parsed]


def keyword_parse(text: str, catalog: dict[str, RestrictionCatalogItem]) -> ProfileParseResponse:
    keys = keyword_keys(text, catalog)
    restrictions = [restriction(catalog[k], severity_for(text, None, catalog[k]), text.strip()) for k in keys]
    profiles = [Profile(profile_id=_id("p"), name="Me", restrictions=restrictions)] if restrictions else []
    return ProfileParseResponse(profiles=profiles, unparsed=[] if profiles else [text.strip()],
                                warnings=[BASIC_PARSING_WARNING], needs_confirmation=True)


async def parse_profiles(text: str, lang: Lang, router: LLMRouter, timeout_s: float = 15.0) -> ProfileParseResponse:
    catalog = {c.key: c for c in engine_adapter.restriction_catalog()}
    listing = "\n".join(f"- {c.key}: {c.label_en}" for c in catalog.values())
    prompt = PROMPT.read_text(encoding="utf-8").replace("{catalog}", listing).replace("{text}", text.strip())
    try:
        result = await router.generate(lambda _: prompt, [], LLMProfileParse, timeout_s=timeout_s)
    except AllProvidersFailedError:
        return keyword_parse(text, catalog)
    response = build_response(result.value, catalog)
    return response.model_copy(update={"warnings": [*response.warnings, *missed_warnings(response, text, catalog)]})
