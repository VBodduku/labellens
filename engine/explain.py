"""KB-only explanations; uncertainty is explicit, with no network fallback."""
from shared.contract import ExplainResponse, Lang
from engine.matcher import match_text


def explain_term(term: str, lang: Lang = "en") -> ExplainResponse | None:
    result = match_text(term)
    if len(result.matches) != 1 or result.unresolved:
        return None
    hit = result.matches[0]
    localized = getattr(hit.entry.names, lang)
    return ExplainResponse(
        term=term, canonical_id=hit.entry.id,
        display_name=(localized or hit.entry.names.en)[0],
        description=hit.entry.notes, origin=hit.origin,
        categories=list(hit.categories), source="kb",
        caution=hit.entry.notes if hit.possible_categories or hit.entry.confidence == "medium" else None,
    )
