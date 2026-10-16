"""POST /api/ask (ask-the-label agent)."""
from __future__ import annotations

from fastapi import APIRouter

from backend.app import fixtures
from shared.contract import AskRequest, AskResponse

router = APIRouter(prefix="/api")


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    response = fixtures.ask_response()
    response.lang = body.lang
    return response
