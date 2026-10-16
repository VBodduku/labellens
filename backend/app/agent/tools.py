"""Agent tools: read-only views of the engine results and label evidence for one scan."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from backend.app import engine_adapter
from backend.app.llm.base import ToolSpec
from backend.app.pipeline.textnorm import norm
from shared.contract import (
    CATEGORIES,
    Evidence,
    Ingredient,
    Lang,
    NUTRIENT_KEYS,
    Profile,
    ProfileReport,
    ScanResult,
)

MATCH_MIN_SCORE = 85
SUMMARY_MAX = 120


@dataclass(frozen=True)
class ToolOutput:
    result: dict[str, Any]
    summary: str                                # short, human-readable (ToolCallTrace.result_summary)


@dataclass
class AgentContext:
    scan: ScanResult
    profiles: list[Profile]
    lang: Lang
    evidence: dict[str, Evidence] = field(default_factory=dict)     # "e3" -> Evidence shown to the model

    def ref(self, evidence: Evidence) -> str:
        key = f"e{len(self.evidence)}"
        self.evidence[key] = evidence
        return key

    def profile(self, profile_id_or_name: str) -> Profile | None:
        wanted = profile_id_or_name.strip().casefold()
        return next((p for p in self.profiles if wanted in (p.profile_id.casefold(), p.name.casefold())), None)

    def report(self, profile_id: str) -> ProfileReport | None:
        return next((r for r in self.scan.reports if r.profile_id == profile_id), None)


def _flatten(items: list[Ingredient]) -> list[Ingredient]:
    return [x for i in items for x in (i, *_flatten(i.sub_ingredients))]


def _short(text: str) -> str:
    return text if len(text) <= SUMMARY_MAX else text[: SUMMARY_MAX - 1] + "…"


def get_profiles(ctx: AgentContext) -> ToolOutput:
    people = [{"profile_id": p.profile_id, "name": p.name, "restrictions": [r.label for r in p.restrictions]}
              for p in ctx.profiles]
    return ToolOutput({"profiles": people}, _short(", ".join(f"{p.name} ({p.profile_id})" for p in ctx.profiles)))


def get_verdict(ctx: AgentContext, profile_id: str) -> ToolOutput:
    profile = ctx.profile(profile_id)
    report = ctx.report(profile.profile_id) if profile else None
    if profile is None or report is None:
        return ToolOutput({"error": f"no profile {profile_id!r}"}, f"no profile {profile_id}")
    labels = {r.id: r.label for r in profile.restrictions}
    results = [{
        "restriction": labels.get(r.restriction_id, r.restriction_id),
        "state": r.state,
        "unknown_kind": r.unknown_kind,
        "explanation": r.explanation,
        "evidence": [{"ref": ctx.ref(e), "text": e.text, "status": e.status} for e in r.evidence[:3]],
    } for r in report.results]
    result = {"profile_id": profile.profile_id, "name": profile.name, "overall": report.overall, "results": results}
    return ToolOutput(result, _short(f"{profile.name}: overall {report.overall}; "
                                     + "; ".join(f"{r['restriction']} {r['state']}" for r in results)))


def _category_of(query: str) -> str | None:
    """A category id ("tree nuts" -> tree_nut), or the KB's primary category for the term in any
    language ("दूध", "పాలు" -> milk), so questions match ingredients printed in English."""
    q = norm(query).replace(" ", "_")
    for candidate in (q, q.rstrip("s"), q.removesuffix("es")):
        if candidate in CATEGORIES:
            return candidate
    explained = engine_adapter.explain_term(query)
    return explained.categories[0] if explained and explained.categories else None


def find_evidence(ctx: AgentContext, query: str) -> ToolOutput:
    """Ingredients and statements matching the words, or (for a category such as "milk") by KB category."""
    extraction = ctx.scan.extraction
    q = norm(query)
    category = _category_of(query)
    by_category = {a.ingredient_id for a in ctx.scan.annotations if category and category in a.categories}
    matches: list[dict[str, Any]] = []
    for item in _flatten(extraction.ingredients):
        name = norm(item.name)
        if item.id in by_category or (q and max(fuzz.token_set_ratio(q, name),
                                                fuzz.partial_ratio(q, name) if len(q) >= 5 else 0) >= MATCH_MIN_SCORE):
            evidence = item.evidence[0] if item.evidence else None
            matches.append({"where": "ingredient", "text": item.raw_text,
                            "ref": ctx.ref(evidence) if evidence else None})
    for statement in extraction.allergen_statements:
        items = [norm(i) for i in statement.items]
        if any(fuzz.token_set_ratio(q, i) >= MATCH_MIN_SCORE for i in items) or (category and category in items):
            evidence = statement.evidence[0] if statement.evidence else None
            matches.append({"where": f"statement:{statement.type}", "text": statement.raw_text,
                            "ref": ctx.ref(evidence) if evidence else None})
    complete = extraction.ingredients_section.complete
    result = {"query": query, "matches": matches, "ingredient_list_read_completely": complete}
    found = ", ".join(m["text"] for m in matches) or "none"
    return ToolOutput(result, _short(f"{query}: {found}; list complete: {complete}"))


def explain_ingredient(ctx: AgentContext, term: str) -> ToolOutput:
    explained = engine_adapter.explain_term(term, ctx.lang)
    if explained is None:
        return ToolOutput({"term": term, "found": False, "note": "not in our database"}, f"{term}: not in database")
    return ToolOutput({"found": True, **explained.model_dump(exclude={"source"})},
                      _short(f"{explained.display_name}: {explained.description}"))


def get_nutrition(ctx: AgentContext, key: str, basis: str = "per_100g") -> ToolOutput:
    extraction = ctx.scan.extraction
    analysis = ctx.scan.nutrition_analysis
    if basis == "per_pack" and analysis and key in analysis.per_pack:
        return ToolOutput({"key": key, "basis": basis, "amount": analysis.per_pack[key], "computed": True},
                          f"{key} per pack: {analysis.per_pack[key]}")
    rows = [r for r in (extraction.nutrition.rows if extraction.nutrition else []) if r.key == key]
    values = [v for r in rows for v in r.values if v.basis == basis] or [v for r in rows for v in r.values]
    if not values:
        return ToolOutput({"key": key, "printed": False}, f"{key}: not on the label")
    value = values[0]
    result: dict[str, Any] = {"key": key, "label": rows[0].raw_label, "basis": value.basis, "amount": value.amount,
                              "unit": value.unit, "readability": value.readability}
    if value.evidence is not None:
        result["ref"] = ctx.ref(value.evidence)
    shown = "unreadable" if value.amount is None else f"{value.amount:g} {value.unit}"
    return ToolOutput(result, f"{rows[0].raw_label} {value.basis}: {shown}")


STRING = {"type": "string"}
SPECS = [
    ToolSpec("get_profiles", "List the family profiles checked against this label.", {"type": "object", "properties": {}}),
    ToolSpec("get_verdict", "The rules engine's verdict for one profile (by profile_id or name), with reasons "
             "and label evidence.", {"type": "object", "properties": {"profile_id": STRING}, "required": ["profile_id"]}),
    ToolSpec("find_evidence", "Search the label for an ingredient, allergen or word; also finds ingredients of a "
             "category such as milk, peanut or gluten.",
             {"type": "object", "properties": {"query": STRING}, "required": ["query"]}),
    ToolSpec("explain_ingredient", "What an ingredient or additive is, from our checked database.",
             {"type": "object", "properties": {"term": STRING}, "required": ["term"]}),
    ToolSpec("get_nutrition", "A nutrient value as printed on the label.",
             {"type": "object", "properties": {
                 "key": {"type": "string", "enum": NUTRIENT_KEYS},
                 "basis": {"type": "string", "enum": ["per_100g", "per_100ml", "per_serving", "per_pack"]}},
              "required": ["key"]}),
]

TOOLS: dict[str, Callable[..., ToolOutput]] = {
    "get_profiles": get_profiles,
    "get_verdict": get_verdict,
    "find_evidence": find_evidence,
    "explain_ingredient": explain_ingredient,
    "get_nutrition": get_nutrition,
}


def call(ctx: AgentContext, name: str, args: dict[str, Any]) -> ToolOutput:
    tool = TOOLS.get(name)
    if tool is None:
        return ToolOutput({"error": f"unknown tool {name}"}, f"unknown tool {name}")
    try:
        return tool(ctx, **{k: str(v) for k, v in args.items()})
    except TypeError:
        return ToolOutput({"error": f"bad arguments for {name}"}, f"bad arguments for {name}")
