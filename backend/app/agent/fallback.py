"""Deterministic keyword intent router, used when no tool-calling LLM is available (Ollama-only / none).

Understands English, Hindi, Telugu and code-mixed phrasing for the common questions:
suitability ("is this okay for Aarav?"), contains ("does it have peanuts?"), nutrient amounts
("how much sugar?"); medical questions are refused.
"""
from __future__ import annotations

import re

from backend.app.agent import guard, templates, tools
from backend.app.agent.tools import AgentContext, ToolOutput
from shared.contract import AskResponse, Evidence, ToolCallTrace

_NUTRIENTS: list[tuple[str, str]] = [   # (pattern, nutrient key)
    (r"added sugar", "added_sugars_g"),
    (r"sugar|चीनी|शक्कर|शुगर|చక్కెర|షుగర్", "total_sugars_g"),
    (r"sodium|salt|नमक|सोडियम|ఉప్పు|సోడియం", "sodium_mg"),
    (r"saturated", "saturated_fat_g"),
    (r"trans fat", "trans_fat_g"),
    (r"\bfat\b|वसा|फैट|కొవ్వు", "total_fat_g"),
    (r"protein|प्रोटीन|ప్రోటీన్", "protein_g"),
    (r"calorie|energy|kcal|कैलोरी|ऊर्जा|కేలరీ|శక్తి", "energy_kcal"),
    (r"carb", "carbohydrate_g"),
    (r"fib(re|er)|फाइबर|ఫైబర్", "fibre_g"),
]
_AMOUNT = re.compile(r"how much|how many|kitna|kitni|कितना|कितनी|ఎంత", re.IGNORECASE)
_SUITABLE = re.compile(
    r"\b(ok|okay|fine|suitable|safe|allowed|eat|have it)\b|can .+ (eat|have)|ठीक|सही|खा सक|chalega|"
    r"సరిపోతుంద|తినవచ్చ|తినొచ్చ|పర్వాలేదా", re.IGNORECASE)
_CONTAINS = re.compile(
    r"\b(contain|contains|have|has|is there|are there|any|with)\b|है क्या|क्या .+ है|hai kya|मौजूद|ఉందా|ఉన్నాయా|కలిగి",
    re.IGNORECASE)
_FILLER = re.compile(
    r"\b(does|do|did|it|this|that|these|the|a|an|is|are|there|any|have|has|contain|contains|with|in|of|"
    r"product|packet|item|food|please|tell|me|hai|kya|isme|ismein|mein)\b|"
    r"है|क्या|इसमें|इस|में|ఇందులో|ఇది|ఉందా|ఉన్నాయా|లో|[?.!,।]", re.IGNORECASE)


def _trace(name: str, args: dict[str, str], out: ToolOutput, traces: list[ToolCallTrace]) -> ToolOutput:
    traces.append(ToolCallTrace(tool=name, args=args, result_summary=out.summary))
    return out


def _named_profiles(ctx: AgentContext, question: str) -> list[str]:
    lowered = question.casefold()
    return [p.profile_id for p in ctx.profiles if p.name.casefold() in lowered]


def answer(ctx: AgentContext, question: str) -> AskResponse:
    if guard.is_medical(question):
        return guard.refusal(ctx.lang)
    traces: list[ToolCallTrace] = []

    if _AMOUNT.search(question):
        key = next((k for pattern, k in _NUTRIENTS if re.search(pattern, question, re.IGNORECASE)), None)
        if key is not None:
            out = _trace("get_nutrition", {"key": key}, tools.get_nutrition(ctx, key), traces)
            r = out.result
            if not r.get("printed", True) or r.get("amount") is None:
                text = templates.message("nutrient_unreadable", ctx.lang, label=r.get("label", key))
            else:
                text = templates.message("nutrient", ctx.lang, label=r["label"], amount=f"{r['amount']:g}",
                                         unit=r["unit"], basis=r["basis"].replace("_", " "))
            evidence = [ctx.evidence[r["ref"]]] if "ref" in r else []
            return AskResponse(answer=text, lang=ctx.lang, grounded=True, tool_calls=traces, evidence=evidence)

    named = _named_profiles(ctx, question)
    if named or _SUITABLE.search(question):
        for pid in named or [p.profile_id for p in ctx.profiles]:
            _trace("get_verdict", {"profile_id": pid}, tools.get_verdict(ctx, pid), traces)
        result = guard.suitability_answer(ctx, named)
        return result.model_copy(update={"tool_calls": traces})

    term = " ".join(_FILLER.sub(" ", question).split())
    if _CONTAINS.search(question) and term:
        out = _trace("find_evidence", {"query": term}, tools.find_evidence(ctx, term), traces)
        matches = out.result["matches"]
        if matches:
            evidence: list[Evidence] = [ctx.evidence[m["ref"]] for m in matches if m.get("ref")]
            listed = [m for m in matches if m["where"] in ("ingredient", "statement:contains")]
            # Only a "may contain"/facility statement: quote it, don't turn it into a yes.
            key, shown = ("contains_found", listed[0]) if listed else ("statement_found", matches[0])
            text = templates.message(key, ctx.lang, evidence=shown["text"])
            return AskResponse(answer=text, lang=ctx.lang, grounded=True, tool_calls=traces, evidence=evidence)
        key = "contains_not_listed" if out.result["ingredient_list_read_completely"] else "contains_unknown"
        return AskResponse(answer=templates.message(key, ctx.lang, term=term), lang=ctx.lang, grounded=True,
                           tool_calls=traces)

    return AskResponse(answer=templates.message("help", ctx.lang), lang=ctx.lang, grounded=True)
