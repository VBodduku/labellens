"""Deterministic keyword intent router, used when no tool-calling LLM is available (Ollama-only / none).

Understands English, Hindi, Telugu and code-mixed phrasing for the common questions: suitability
("is this okay for Aarav?") and why ("why is it a conflict for Thatha?"), diets nobody's profile asked
about ("is it vegan?"), contains ("does it have peanuts?"), the allergen statements, the ingredient list,
what an ingredient is ("what is INS 471?") and nutrient amounts ("how much sugar per serving?"). Every
answer restates engine verdicts or label text; medical questions are refused.
"""
from __future__ import annotations

import re

from backend.app.agent import guard, templates, tools
from backend.app.agent.tools import AgentContext, ToolOutput
from backend.app.wording import STATE_WORDS, has_banned_word
from shared.contract import AskResponse, Evidence, ToolCallTrace, VerdictRef

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
_BASES: list[tuple[str, str]] = [   # (pattern, basis); per 100 g otherwise
    (r"per serv|a serving|one serving|serving|प्रति सर्विंग|एक सर्विंग|సర్వింగ్", "per_serving"),
    (r"per pack|whole pack|full pack|whole packet|पूरे पैक|पूरा पैक|మొత్తం ప్యాక్", "per_pack"),
]
_DIETS: list[tuple[str, str]] = [     # (pattern, catalog key); adjectives only: "does it have gluten" is a contains question
    (r"\bvegan\b|वीगन|వీగన్", "vegan"),
    (r"\bjain\b|जैन|జైన", "jain"),
    (r"vegetarian|\bveg\b|शाकाहारी|శాకాహార", "vegetarian"),
    (r"gluten[ -]?free|ग्लूटेन[ -]?फ्री|గ్లూటెన్[ -]?ఫ్రీ", "gluten"),
    (r"eggless|egg[ -]?free|अंडा रहित|బిగుడు లేని|గుడ్డు లేని", "egg"),
    (r"dairy[ -]?free|milk[ -]?free", "milk"),
]
_WHY = re.compile(r"\bwhy\b|\bkyon\b|\bkyun\b|क्यों|ఎందుకు", re.IGNORECASE)
_ALLERGENS = re.compile(r"allerg|एलर्जी|ఎలర్జీ|అలెర్జీ", re.IGNORECASE)
_INGREDIENT_LIST = re.compile(r"ingredients|what(?:'s| is) in (?:it|this)|सामग्री|पदार्थ|పదార్థాలు", re.IGNORECASE)
_EXPLAIN = re.compile(r"what is|what's|what are|what does .+ mean|meaning of|\bmeans?\b|kya hai|kya hota|"
                      r"क्या है|क्या होता|అంటే ఏమిటి|అంటే ఏంటి|ఏమిటి", re.IGNORECASE)
_EXPLAIN_WORDS = re.compile(r"what is|what's|what are|what does|mean|meaning of|\bmeans?\b|kya hai|kya hota|"
                            r"क्या है|क्या होता|అంటే ఏమిటి|అంటే ఏంటి|ఏమిటి|అంటే", re.IGNORECASE)
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


def _amount(ctx: AgentContext, question: str, traces: list[ToolCallTrace]) -> AskResponse | None:
    key = next((k for pattern, k in _NUTRIENTS if re.search(pattern, question, re.IGNORECASE)), None)
    if key is None:
        return None
    basis = next((b for pattern, b in _BASES if re.search(pattern, question, re.IGNORECASE)), "per_100g")
    out = _trace("get_nutrition", {"key": key, "basis": basis}, tools.get_nutrition(ctx, key, basis), traces)
    r = out.result
    if not r.get("printed", True) or r.get("amount") is None:
        text = templates.message("nutrient_unreadable", ctx.lang, label=r.get("label", key))
    elif r.get("computed"):     # per pack, worked out by the engine from the printed values
        rows = ctx.scan.extraction.nutrition.rows if ctx.scan.extraction.nutrition else []
        label = next((row.raw_label for row in rows if row.key == key), key)
        unit = "kcal" if key == "energy_kcal" else key.rsplit("_", 1)[-1]
        text = templates.message("nutrient_computed", ctx.lang, label=label, amount=f"{r['amount']:.3g}", unit=unit)
    else:
        text = templates.message("nutrient", ctx.lang, label=r["label"], amount=f"{r['amount']:g}",
                                 unit=r["unit"], basis=r["basis"].replace("_", " "))
    evidence = [ctx.evidence[r["ref"]]] if "ref" in r else []
    return AskResponse(answer=" ".join(text.split()), lang=ctx.lang, grounded=True, tool_calls=traces,
                       evidence=evidence)


def _why(ctx: AgentContext, profile_ids: list[str], traces: list[ToolCallTrace]) -> AskResponse:
    """Every result that is not "not listed", with the label words it rests on."""
    lines: list[str] = []
    evidence: list[Evidence] = []
    for pid in profile_ids:
        out = _trace("get_verdict", {"profile_id": pid}, tools.get_verdict(ctx, pid), traces)
        r = out.result
        if "error" in r:
            continue
        reasons = [x for x in r["results"] if x["state"] != "not_listed"]
        if not reasons:
            lines.append(templates.suitability(ctx.lang, r["name"], r["overall"]))
            continue
        lines.append(templates.verdict_line(ctx.lang, r["name"], r["overall"]))
        for x in reasons:
            shown = x["evidence"][0] if x["evidence"] and x["evidence"][0]["text"] else None
            state = STATE_WORDS[ctx.lang][x["state"]]
            if shown:
                evidence.append(ctx.evidence[shown["ref"]])
            if ctx.lang == "en":            # the engine's own English sentence names the value and the limit
                lines.append(f"{x['restriction']}: {state}. {x['explanation']}")
            elif shown:
                lines.append(templates.message("reason", ctx.lang, restriction=x["restriction"], state=state,
                                               evidence=shown["text"]))
            else:
                lines.append(templates.message("reason_bare", ctx.lang, restriction=x["restriction"], state=state))
    return AskResponse(answer=" ".join(lines), lang=ctx.lang, grounded=True, tool_calls=traces, evidence=evidence,
                       verdict_refs=[VerdictRef(profile_id=pid) for pid in profile_ids])


def _diet(ctx: AgentContext, key: str, traces: list[ToolCallTrace]) -> AskResponse:
    r = _trace("check_restriction", {"key": key}, tools.check_restriction(ctx, key), traces).result
    shown = r["evidence"][0] if r["evidence"] else None
    text = templates.diet(ctx.lang, r["label"], r["state"], shown["text"] if shown else "")
    evidence = [ctx.evidence[e["ref"]] for e in r["evidence"]]
    return AskResponse(answer=text, lang=ctx.lang, grounded=True, tool_calls=traces, evidence=evidence)


def _allergens(ctx: AgentContext) -> AskResponse:
    statements = ctx.scan.extraction.allergen_statements
    if not statements:
        return AskResponse(answer=templates.message("no_allergens", ctx.lang), lang=ctx.lang, grounded=True)
    listed = "; ".join(f"“{templates.quoted(s.raw_text)}”" for s in statements)
    evidence = [e for s in statements for e in s.evidence[:1]]
    return AskResponse(answer=templates.message("allergens", ctx.lang, statements=listed), lang=ctx.lang,
                       grounded=True, evidence=evidence)


def _ingredient_list(ctx: AgentContext) -> AskResponse:
    extraction = ctx.scan.extraction
    if not extraction.ingredients:
        return AskResponse(answer=templates.message("no_ingredients", ctx.lang), lang=ctx.lang, grounded=True)
    text = templates.message("ingredients", ctx.lang,
                             items=", ".join(templates.quoted(i.raw_text) for i in extraction.ingredients))
    if not extraction.ingredients_section.complete:
        text += " " + templates.message("ingredients_incomplete", ctx.lang)
    return AskResponse(answer=text, lang=ctx.lang, grounded=True)


def _explain(ctx: AgentContext, term: str, traces: list[ToolCallTrace]) -> AskResponse:
    r = _trace("explain_ingredient", {"term": term}, tools.explain_ingredient(ctx, term), traces).result
    if r["found"] and not has_banned_word(r["description"]):
        text = templates.message("explained", ctx.lang, name=r["display_name"], description=r["description"])
    else:
        text = templates.message("not_explained", ctx.lang, term=term)
    return AskResponse(answer=text, lang=ctx.lang, grounded=True, tool_calls=traces)


def answer(ctx: AgentContext, question: str) -> AskResponse:
    if guard.is_medical(question):
        return guard.refusal(ctx.lang)
    traces: list[ToolCallTrace] = []

    if _AMOUNT.search(question) and (amount := _amount(ctx, question, traces)) is not None:
        return amount

    named = _named_profiles(ctx, question)
    if _WHY.search(question):
        return _why(ctx, named or [p.profile_id for p in ctx.profiles], traces)
    diet = next((k for pattern, k in _DIETS if re.search(pattern, question, re.IGNORECASE)), None)
    if diet is not None and not named:
        return _diet(ctx, diet, traces)
    if named or _SUITABLE.search(question):
        for pid in named or [p.profile_id for p in ctx.profiles]:
            _trace("get_verdict", {"profile_id": pid}, tools.get_verdict(ctx, pid), traces)
        result = guard.suitability_answer(ctx, named)
        return result.model_copy(update={"tool_calls": traces})
    if _ALLERGENS.search(question):
        return _allergens(ctx)
    if _INGREDIENT_LIST.search(question):
        return _ingredient_list(ctx)
    if _EXPLAIN.search(question):
        term = " ".join(_FILLER.sub(" ", _EXPLAIN_WORDS.sub(" ", question)).split())
        if term:
            return _explain(ctx, term, traces)

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
