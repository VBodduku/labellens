"""Per-profile one-sentence summaries in the scan language, generated only from engine results (§4.7).

A summary that is too long, names an unknown profile or uses a banned word in any language is
dropped; the frontend then shows its own template.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from backend.app.wording import ALL_BANNED, LANGUAGE_NAMES, STATE_WORDS, has_banned_word
from shared.contract import Lang, Profile, ProfileReport, Restriction

logger = logging.getLogger("labellens.summarize")

MAX_WORDS = 25
PROMPT = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "summarize.md"
class LLMSummary(BaseModel):
    profile_id: str
    summary: str


class LLMSummaries(BaseModel):
    summaries: list[LLMSummary]


def valid_summary(text: str) -> bool:
    return bool(text.strip()) and len(text.split()) <= MAX_WORDS and not has_banned_word(text)


def _label(restrictions: dict[str, Restriction], restriction_id: str) -> str:
    restriction = restrictions.get(restriction_id)
    return restriction.label if restriction else restriction_id


def describe(reports: list[ProfileReport], profiles: list[Profile]) -> str:
    by_id = {p.profile_id: p for p in profiles}
    blocks: list[str] = []
    for report in reports:
        profile = by_id.get(report.profile_id)
        if profile is None:
            continue
        restrictions = {r.id: r for r in profile.restrictions}
        lines = [f"- {_label(restrictions, r.restriction_id)}: {r.state}"
                 f"{f' ({r.unknown_kind})' if r.unknown_kind else ''} - {r.explanation}" for r in report.results]
        blocks.append(f"profile_id {report.profile_id} ({profile.name}), overall {report.overall}:\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def build_prompt(reports: list[ProfileReport], profiles: list[Profile], lang: Lang) -> str:
    words = STATE_WORDS[lang]
    return (PROMPT.read_text(encoding="utf-8")
            .replace("{language}", LANGUAGE_NAMES[lang])
            .replace("{word_conflict}", words["conflict"]).replace("{word_possible}", words["possible"])
            .replace("{word_not_listed}", words["not_listed"]).replace("{word_unknown}", words["unknown"])
            .replace("{banned}", ", ".join(ALL_BANNED))
            .replace("{results}", describe(reports, profiles)))


async def summarize(
    reports: list[ProfileReport], profiles: list[Profile], lang: Lang, router: LLMRouter,
    timeout_s: Optional[float] = None,
) -> dict[str, str]:
    """profile_id -> summary, only for summaries that pass every rule."""
    if not reports:
        return {}
    prompt = build_prompt(reports, profiles, lang)
    try:
        result = await router.generate(lambda _: prompt, [], LLMSummaries, timeout_s=timeout_s)
    except AllProvidersFailedError:
        logger.warning("summaries skipped: no LLM available")
        return {}
    wanted = {r.profile_id for r in reports}
    accepted = {s.profile_id: s.summary.strip() for s in result.value.summaries
                if s.profile_id in wanted and valid_summary(s.summary)}
    dropped = len(result.value.summaries) - len(accepted)
    if dropped:
        logger.warning("summaries dropped", extra={"fields": {"count": dropped}})
    return accepted


def apply(reports: list[ProfileReport], summaries: dict[str, str], lang: Lang) -> list[ProfileReport]:
    return [
        r.model_copy(update={"summary": summaries[r.profile_id], "summary_lang": lang}) if r.profile_id in summaries
        else r.model_copy(update={"summary": None, "summary_lang": None})
        for r in reports
    ]
