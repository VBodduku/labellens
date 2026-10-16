"""Ask-the-label agent: tool loop, guard, templates and the keyword fallback."""
from __future__ import annotations

import asyncio
import json

import pytest

from backend.app import engine_adapter
from backend.tests import fixture_data as fixtures
from backend.app.agent import agent, fallback, guard
from backend.app.agent.tools import AgentContext, find_evidence, get_nutrition, get_verdict
from backend.app.llm.base import ChatMessage, RateLimitedError, ToolCall
from backend.app.llm.router import LLMRouter
from backend.app.pipeline.assemble import build_scan_result
from backend.tests.fakes import FakeLLM, FakeToolClient
from shared.contract import AskRequest, Lang, Profile, ScanResult

PROFILES = [Profile.model_validate(p)
            for p in json.loads((fixtures.FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8"))]


def scan() -> ScanResult:
    extraction = fixtures.scan_result().extraction
    return build_scan_result(extraction, engine_adapter.evaluate(extraction, PROFILES), "en")


SCAN = scan()


def ctx(lang: Lang = "en") -> AgentContext:
    return AgentContext(scan=SCAN, profiles=PROFILES, lang=lang)


def request(question: str, lang: Lang = "en") -> AskRequest:
    return AskRequest(question=question, lang=lang, scan=SCAN, profiles=PROFILES)


def final(**fields: object) -> ChatMessage:
    return ChatMessage(role="model", text="```json\n" + json.dumps(fields) + "\n```")


def calls(*pairs: tuple[str, dict]) -> ChatMessage:
    return ChatMessage(role="model", calls=[ToolCall(name, args) for name, args in pairs])


def ask(client: FakeToolClient | FakeLLM, question: str, lang: Lang = "en"):  # type: ignore[no-untyped-def]
    router = LLMRouter([client], 5)
    return asyncio.run(agent.ask(request(question, lang), router)), router


def test_fixture_verdicts() -> None:
    assert {r.profile_id: r.overall for r in SCAN.reports} == {
        "p_aarav": "conflict", "p_thatha": "conflict", "p_lakshmi": "possible"}


# ---------------------------------------------------------------- tool loop
def test_agent_answers_from_tools_and_records_traces() -> None:
    client = FakeToolClient([
        calls(("get_verdict", {"profile_id": "Aarav"})),
        final(answer="For Aarav: Conflict. The label lists “Peanuts (22%)”.", stance="conflict",
              intent="suitability", profile_ids=["p_aarav"], evidence_refs=["e0"]),
    ])
    response, _ = ask(client, "Is this okay for Aarav?")
    assert response.answer.startswith("For Aarav: Conflict") and response.grounded
    assert [(t.tool, t.args) for t in response.tool_calls] == [("get_verdict", {"profile_id": "Aarav"})]
    assert "overall conflict" in response.tool_calls[0].result_summary
    assert response.evidence[0].text.startswith("Peanuts")
    assert [r.profile_id for r in response.verdict_refs] == ["p_aarav"]
    tool_turn = client.seen[1][-1]
    assert tool_turn.role == "tool" and tool_turn.results[0][1]["overall"] == "conflict"
    assert "Conflict" in client.systems[0] and "English" in client.systems[0]


def test_wrong_stance_is_corrected_once() -> None:
    client = FakeToolClient([
        final(answer="Lakshmi can have it.", stance="not_listed", intent="suitability", profile_ids=["p_lakshmi"]),
        final(answer="For Lakshmi: Check this. “Natural Flavours” may come from onion or garlic.",
              stance="possible", intent="suitability", profile_ids=["p_lakshmi"]),
    ])
    response, _ = ask(client, "Is this fine for Lakshmi?")
    assert response.answer.startswith("For Lakshmi: Check this")
    assert "Correction" in (client.seen[1][-1].text or "") and '"possible"' in (client.seen[1][-1].text or "")


def test_stance_still_wrong_falls_back_to_template() -> None:
    wrong = final(answer="Thatha can have it.", stance="not_listed", intent="suitability", profile_ids=["p_thatha"])
    response, _ = ask(FakeToolClient([wrong, wrong]), "Can Thatha eat this?")
    assert response.answer.startswith("For Thatha: Conflict.")
    assert [r.profile_id for r in response.verdict_refs] == ["p_thatha"]


def test_banned_word_answer_is_replaced() -> None:
    bad = final(answer="This is safe for Aarav.", stance="conflict", intent="suitability", profile_ids=["p_aarav"])
    response, _ = ask(FakeToolClient([bad]), "Is this okay for Aarav?")
    assert "safe" not in response.answer and response.answer.startswith("For Aarav: Conflict")


def test_too_many_tool_rounds_or_bad_json_falls_back() -> None:
    looping = FakeToolClient([calls(("get_profiles", {}))])
    response, _ = ask(looping, "Does it have milk?")
    assert len(looping.seen) == 5 and response.answer.startswith("Yes, the label shows")
    garbage = FakeToolClient([ChatMessage(role="model", text="I think it's fine!")])
    assert ask(garbage, "Does it have milk?")[0].answer.startswith("Yes, the label shows")


def test_rate_limit_cools_down_the_client_and_falls_back() -> None:
    client = FakeToolClient([RateLimitedError(30)])
    response, router = ask(client, "Is this okay for Aarav?")
    assert response.answer.startswith("For Aarav: Conflict")
    assert router.tool_client() is None


def test_medical_questions_are_refused_without_llm() -> None:
    client = FakeToolClient([final(answer="x")])
    for question, lang in [("What insulin dose should Thatha take?", "en"), ("क्या मैं यह दवा के साथ खा सकता हूँ?", "hi"),
                           ("ఇన్సులిన్ ఎంత వేసుకోవాలి?", "te")]:
        response, _ = ask(client, question, lang)  # type: ignore[arg-type]
        assert response.refusal == "medical_advice" and response.grounded is False and response.lang == lang
    assert client.seen == []


def test_model_flagging_medical_intent_is_refused() -> None:
    response, _ = ask(FakeToolClient([final(answer="Take less sugar pills.", intent="medical")]), "Should he cut sweets?")
    assert response.refusal == "medical_advice"


def test_without_tool_model_uses_keyword_router() -> None:
    response, _ = ask(FakeLLM(), "Is this okay for Aarav?")
    assert response.answer.startswith("For Aarav: Conflict") and response.tool_calls[0].tool == "get_verdict"


# ---------------------------------------------------------------- guard and tools
def test_guard_stance_uses_worst_overall_of_profiles() -> None:
    assert guard.expected_stance(ctx(), ["p_lakshmi", "p_aarav"]) == "conflict"
    assert guard.stance_matches(ctx(), "possible", ["p_lakshmi"])
    assert not guard.stance_matches(ctx(), "possible", ["p_ghost"])


def test_tools_ground_answers() -> None:
    c = ctx()
    assert get_verdict(c, "thatha").result["overall"] == "conflict"
    assert get_verdict(c, "nobody").result == {"error": "no profile 'nobody'"}
    milk = find_evidence(c, "milk").result
    assert any("Milk Solids" in m["text"] for m in milk["matches"]) and milk["ingredient_list_read_completely"]
    assert find_evidence(c, "दूध").result["matches"]
    sodium = get_nutrition(c, "sodium_mg").result
    assert sodium["amount"] is None and sodium["readability"] == "unreadable"
    assert get_nutrition(c, "cholesterol_mg").result == {"key": "cholesterol_mg", "printed": False}


# ---------------------------------------------------------------- keyword fallback
@pytest.mark.parametrize("question, lang, expected", [
    ("Is this okay for Aarav?", "en", "For Aarav: Conflict. The label shows “Peanuts (22%)”."),
    ("mera beta Aarav ke liye chalega?", "en", "For Aarav: Conflict."),
    ("Does it have milk?", "en", "Yes, the label shows “Milk Solids (12%)”."),
    ("क्या इसमें दूध है?", "hi", "हाँ, लेबल पर लिखा है: “Milk Solids (12%)”।"),
    ("ఇందులో వేరుశెనగ ఉందా?", "te", "అవును, లేబుల్‌పై ఇలా ఉంది: “Peanuts (22%)”."),
    ("Does it have tree nuts?", "en", "The label says “MAY CONTAIN TRACES OF TREE NUTS”."),
    ("Does it contain sesame?", "en", "“sesame” is not listed on the label; the ingredient list was read completely."),
    ("How much sugar is in it?", "en", "Total Sugars: 38 g (per 100g), as printed on the label."),
    ("how much sodium?", "en", "The Sodium value could not be read on the photo."),
    ("hello", "en", "I can tell you whether this suits"),
    ("Why is it a conflict for Thatha?", "en",
     "For Thatha: Conflict. Diabetic: limit sugar: Conflict. Total sugars is 38.0 g per 100 g, above your limit of 22.5 g."),
    ("Lakshmi కి ఎందుకు?", "te", "Lakshmi కోసం: ఇది తనిఖీ చేయండి. Jain: ఇది తనిఖీ చేయండి (“Natural”)."),
    ("Is this vegan?", "en", "Vegan: Conflict. The label shows “Milk Solids (12%)”."),
    ("Is it gluten free?", "en", "Gluten-free (coeliac): Conflict. The label shows “Refined Wheat”."),
    ("Is it okay for a vegan?", "en", "Vegan: Conflict."),
    ("ఇది శాకాహారమా?", "te", "Vegetarian (no egg): జాబితాలో లేదు."),
    ("What allergens does it have?", "en",
     "The label's allergen information: “CONTAINS: PEANUT, MILK, WHEAT, SOY”; “MAY CONTAIN TRACES OF TREE NUTS”."),
    ("What are the ingredients?", "en", "Ingredients read from the label: Sugar, Peanuts (22%), Milk Solids (12%),"),
    ("What is INS 471?", "en", "mono and diglycerides: Fatty acid feedstock can be vegetable or animal"),
    ("What is zorbex?", "en", "“zorbex” is not in our ingredient database."),
    ("How much sugar per serving?", "en", "Total Sugars: 15.2 g (per serving), as printed on the label."),
    ("How much sugar in the whole pack?", "en", "Total Sugars: about 45.6 g for the whole pack, worked out"),
])
def test_keyword_router(question: str, lang: Lang, expected: str) -> None:
    assert fallback.answer(ctx(lang), question).answer.startswith(expected)


def test_telugu_question_for_me_answers_for_every_profile() -> None:
    response = fallback.answer(ctx("te"), "ఇది నాకు సరిపోతుందా?")
    assert response.answer.count("కోసం") == 3 and "విరుద్ధం" in response.answer
    assert [t.tool for t in response.tool_calls] == ["get_verdict"] * 3


def test_contains_with_incomplete_list_cannot_confirm_absence() -> None:
    c = ctx()
    section = c.scan.extraction.ingredients_section.model_copy(update={"complete": False})
    extraction = c.scan.extraction.model_copy(update={"ingredients_section": section})
    c = AgentContext(scan=c.scan.model_copy(update={"extraction": extraction}), profiles=PROFILES, lang="en")
    assert "can't confirm it is absent" in fallback.answer(c, "Does it contain sesame?").answer


def test_overloaded_model_falls_through_to_the_next_gemini_client() -> None:
    from backend.app.llm.base import ProviderUnavailableError

    busy = FakeToolClient([ProviderUnavailableError("gemini HTTP 503 UNAVAILABLE")], label="gemini:primary:main")
    lite = FakeToolClient([final(answer="For Aarav: Conflict. \u201cPeanuts (22%)\u201d is listed.", stance="conflict",
                                 intent="suitability", profile_ids=["p_aarav"])], label="gemini:primary:lite")
    response = asyncio.run(agent.ask(request("Is this okay for Aarav?"), LLMRouter([busy, lite], 5)))
    assert response.answer.startswith("For Aarav: Conflict. \u201cPeanuts") and len(lite.seen) == 1


def test_a_diet_question_is_the_engine_verdict_with_its_trace_and_evidence() -> None:
    response = fallback.answer(ctx(), "Is this vegan?")
    assert [t.tool for t in response.tool_calls] == ["check_restriction"]
    assert any(e.text.startswith("Milk Solids") for e in response.evidence)
    assert not any(word in response.answer.casefold() for word in ("yes", "safe", "suitable"))


def test_an_ingredient_list_read_partly_says_there_may_be_more() -> None:
    c = ctx()
    section = c.scan.extraction.ingredients_section.model_copy(update={"complete": False})
    extraction = c.scan.extraction.model_copy(update={"ingredients_section": section})
    c = AgentContext(scan=c.scan.model_copy(update={"extraction": extraction}), profiles=PROFILES, lang="en")
    assert fallback.answer(c, "What are the ingredients?").answer.endswith("so there may be more.")
