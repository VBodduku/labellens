"""POST /api/ask (ask-the-label agent)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.agent import agent
from backend.app.llm.router import LLMRouter, get_router
from backend.app.logging_setup import stage
from shared.contract import AskRequest, AskResponse

router = APIRouter(prefix="/api")


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, router: LLMRouter = Depends(get_router)) -> AskResponse:
    with stage("agent"):
        return await agent.ask(body, router)
