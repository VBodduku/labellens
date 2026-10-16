"""Safety checks around the agent: medical refusal, stance vs engine verdict, banned words."""
from __future__ import annotations

import re
from collections.abc import Sequence

from backend.app.agent import templates
from backend.app.agent.tools import AgentContext
from shared.contract import AskResponse, Evidence, Lang, VerdictRef, VerdictState

_MEDICAL = re.compile(
    r"\b(doses?|dosage|insulin|medicines?|medications?|tablets?|pills?|cure|treat|treatment|prescri\w*|"
    r"metformin|drugs?)\b|दवा|दवाई|खुराक|इलाज|इंसुलिन|गोली|మందు|మోతాదు|ఇన్సులిన్|చికిత్స|టాబ్లెట్",
    re.IGNORECASE,
)
_SEVERITY: list[VerdictState] = ["conflict", "possible", "unknown", "not_listed"]


def is_medical(question: str) -> bool:
    return bool(_MEDICAL.search(question))


def refusal(lang: Lang) -> AskResponse:
    return AskResponse(answer=templates.message("medical", lang), lang=lang, grounded=False, refusal="medical_advice")


def expected_stance(ctx: AgentContext, profile_ids: Sequence[str]) -> VerdictState | None:
    states = [r.overall for pid in profile_ids if (r := ctx.report(pid)) is not None]
    return min(states, key=_SEVERITY.index) if states else None


def stance_matches(ctx: AgentContext, stance: str, profile_ids: Sequence[str]) -> bool:
    expected = expected_stance(ctx, profile_ids)
    return expected is not None and stance == expected


def suitability_answer(ctx: AgentContext, profile_ids: Sequence[str]) -> AskResponse:
    """Template answer straight from the engine verdicts (one sentence per profile)."""
    ids = [pid for pid in profile_ids if ctx.report(pid)] or [p.profile_id for p in ctx.profiles]
    sentences: list[str] = []
    evidence: list[Evidence] = []
    for pid in ids:
        report = ctx.report(pid)
        profile = ctx.profile(pid)
        if report is None or profile is None:
            continue
        worst = next((r for r in report.results if r.state == report.overall), None)
        first = worst.evidence[0] if worst and worst.evidence else None
        sentences.append(templates.suitability(ctx.lang, profile.name, report.overall, first.text if first else ""))
        if first is not None:
            evidence.append(first)
    return AskResponse(answer=" ".join(sentences), lang=ctx.lang, grounded=True, evidence=evidence,
                       verdict_refs=[VerdictRef(profile_id=pid) for pid in ids])
