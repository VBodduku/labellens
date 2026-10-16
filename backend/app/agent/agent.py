"""Ask-the-label agent: Gemini function calling over read-only tools, checked by the guard.

Falls back to the deterministic keyword router when no tool-calling model is available or the
model misbehaves. Max 4 tool rounds; every tool call is recorded as a ToolCallTrace.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from backend.app.agent import fallback, guard, tools
from backend.app.agent.tools import AgentContext
from backend.app.llm.base import (
    AccessDeniedError,
    ChatMessage,
    LLMError,
    ModelOverloadedError,
    RateLimitedError,
    ToolChatClient,
)
from backend.app.llm.router import LLMRouter
from backend.app.wording import LANGUAGE_NAMES, STATE_WORDS, has_banned_word
from shared.contract import AskRequest, AskResponse, ToolCallTrace, VerdictRef

logger = logging.getLogger("labellens.agent")

MAX_TOOL_ROUNDS = 4
BUDGET_S = 20.0
SYSTEM_PROMPT = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "agent_system.md"
CORRECTION = ("Correction: the engine's overall verdict for {names} is \"{state}\". Report exactly that state "
              "and its reason, then reply with the JSON again.")


class AgentFinal(BaseModel):
    answer: str
    stance: Literal["conflict", "possible", "not_listed", "unknown", "none"] = "none"
    intent: Literal["suitability", "contains", "nutrition", "explain", "medical", "other"] = "other"
    profile_ids: list[str] = []
    evidence_refs: list[str] = []


class AgentGaveUp(Exception):
    """The model did not produce a usable final answer."""


def system_prompt(ctx: AgentContext) -> str:
    words = STATE_WORDS[ctx.lang]
    return (SYSTEM_PROMPT.read_text(encoding="utf-8")
            .replace("{language}", LANGUAGE_NAMES[ctx.lang])
            .replace("{conflict}", words["conflict"]).replace("{possible}", words["possible"])
            .replace("{not_listed}", words["not_listed"]).replace("{unknown}", words["unknown"]))


def parse_final(text: str) -> AgentFinal:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        raise AgentGaveUp("final answer is not JSON")
    try:
        return AgentFinal.model_validate(json.loads(match.group(0)))
    except (ValueError, ValidationError) as exc:
        raise AgentGaveUp("final answer does not match the format") from exc


class _Conversation:
    def __init__(self, client: ToolChatClient, ctx: AgentContext, question: str, deadline: float) -> None:
        self.client = client
        self.ctx = ctx
        self.deadline = deadline
        self.system = system_prompt(ctx)
        self.messages = [ChatMessage(role="user", text=question)]
        self.traces: list[ToolCallTrace] = []
        self.tool_rounds = 0

    async def final(self) -> AgentFinal:
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise AgentGaveUp("time budget used up")
            turn = await asyncio.wait_for(
                self.client.chat_with_tools(self.messages, tools.SPECS, self.system, remaining), remaining)
            self.messages.append(turn)
            if not turn.calls:
                return parse_final(turn.text or "")
            self.tool_rounds += 1
            if self.tool_rounds > MAX_TOOL_ROUNDS:
                raise AgentGaveUp("too many tool rounds")
            results = []
            for call in turn.calls:
                out = tools.call(self.ctx, call.name, call.args)
                self.traces.append(ToolCallTrace(tool=call.name, args=call.args, result_summary=out.summary))
                results.append((call.name, out.result))
            self.messages.append(ChatMessage(role="tool", results=results))

    def correct(self, profile_ids: list[str]) -> None:
        names = ", ".join(p.name for pid in profile_ids if (p := self.ctx.profile(pid))) or "the family"
        state = guard.expected_stance(self.ctx, profile_ids) or "unknown"
        self.messages.append(ChatMessage(role="user", text=CORRECTION.format(names=names, state=state)))


def _response(ctx: AgentContext, final: AgentFinal, traces: list[ToolCallTrace]) -> AskResponse:
    valid_ids = [pid for pid in final.profile_ids if ctx.report(pid)]
    return AskResponse(
        answer=final.answer.strip(), lang=ctx.lang, grounded=True, tool_calls=traces,
        evidence=[ctx.evidence[r] for r in final.evidence_refs if r in ctx.evidence],
        verdict_refs=[VerdictRef(profile_id=pid) for pid in valid_ids],
    )


async def _with_tools(client: ToolChatClient, ctx: AgentContext, question: str, budget_s: float) -> AskResponse:
    talk = _Conversation(client, ctx, question, time.monotonic() + budget_s)
    final = await talk.final()
    if final.intent == "medical":
        return guard.refusal(ctx.lang)
    if final.intent == "suitability":
        ids = final.profile_ids or [p.profile_id for p in ctx.profiles]
        if not guard.stance_matches(ctx, final.stance, ids):
            talk.correct(ids)
            final = await talk.final()
            if final.intent == "suitability" and not guard.stance_matches(ctx, final.stance, final.profile_ids or ids):
                logger.warning("agent stance still wrong; answering from templates")
                return guard.suitability_answer(ctx, ids).model_copy(update={"tool_calls": talk.traces})
    if has_banned_word(final.answer):
        if final.intent == "suitability":
            ids = final.profile_ids or [p.profile_id for p in ctx.profiles]
            return guard.suitability_answer(ctx, ids).model_copy(update={"tool_calls": talk.traces})
        raise AgentGaveUp("banned word in answer")
    return _response(ctx, final, talk.traces)


async def ask(request: AskRequest, router: LLMRouter, budget_s: float = BUDGET_S) -> AskResponse:
    ctx = AgentContext(scan=request.scan, profiles=request.profiles, lang=request.lang)
    if guard.is_medical(request.question):
        return guard.refusal(request.lang)
    deadline = time.monotonic() + budget_s
    reason = "no tool-calling model available"
    for client in router.tool_clients():            # main model, fallback model, backup key ...
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            break
        try:
            return await _with_tools(client, AgentContext(scan=request.scan, profiles=request.profiles,
                                                          lang=request.lang), request.question, remaining)
        except RateLimitedError as exc:
            router.report_rate_limit(client.label, exc.retry_after_s)
            reason = "rate limited"
        except ModelOverloadedError as exc:
            router.report_rate_limit(client.label, exc.retry_after_s)
            reason = "overloaded"
        except AccessDeniedError as exc:
            router.report_access_denied(client.label, exc.retry_after_s)
            reason = "access denied"
        except (LLMError, TimeoutError) as exc:
            reason = str(exc) or type(exc).__name__
        except AgentGaveUp as exc:                  # the model answered badly: another model won't be safer
            reason = str(exc)
            break
    logger.warning("agent fell back to keyword router", extra={"fields": {"reason": reason}})
    return fallback.answer(ctx, request.question)
