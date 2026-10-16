"""KB-only explanations; uncertainty is explicit, with no network fallback."""

from shared.contract import ExplainResponse, Lang
from engine.matcher import match_text
from engine.kb_loader import DISPLAY_NAMES


def explain_term(term: str, lang: Lang = "en") -> ExplainResponse | None:
    result = match_text(term)
    if len(result.matches) != 1 or result.unresolved:
        return None
    hit = result.matches[0]
    localized = getattr(hit.entry.names, lang)
    caution = (
        hit.entry.notes
        if hit.possible_categories or hit.entry.confidence == "medium"
        else None
    )
    if hit.possible_categories:
        possible = ", ".join(
            DISPLAY_NAMES.categories[category] for category in hit.possible_categories
        )
        caution = f"{hit.entry.notes} Possible categories: {possible}."
    if hit.note:
        caution = f"{caution} {hit.note}" if caution else hit.note
    if hit.entry.review_reason:
        caution = (
            f"{caution} {hit.entry.review_reason}"
            if caution
            else hit.entry.review_reason
        )
    return ExplainResponse(
        term=term,
        canonical_id=hit.entry.id,
        display_name=(localized or hit.entry.names.en)[0],
        description=hit.entry.notes,
        origin=hit.origin,
        categories=list(hit.categories),
        source="kb",
        caution=caution,
    )
