"""GET /api/health, GET /api/catalog, POST /api/profile/parse, POST /api/explain."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app import engine_adapter
from backend.app.config import get_settings
from backend.app.llm.router import LLMRouter, get_router
from backend.app.logging_setup import stage
from backend.app.pipeline.explain import explain as explain_term
from backend.app.pipeline.profile_parse import parse_profiles
from backend.app.provider_probe import probe_providers
from shared.contract import (
    ExplainRequest,
    ExplainResponse,
    HealthResponse,
    ProfileParseRequest,
    ProfileParseResponse,
    RestrictionCatalogItem,
)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health(router: LLMRouter = Depends(get_router)) -> HealthResponse:
    reachable = await probe_providers(get_settings())
    usable = router.provider_status()
    providers = {name: reachable.get(name, False) and usable.get(name, False) for name in ("gemini", "ollama")}
    return HealthResponse(
        status="ok" if any(providers.values()) else "degraded",
        providers=providers,
        engine_mode=engine_adapter.engine_mode(),
    )


@router.get("/catalog", response_model=list[RestrictionCatalogItem])
def catalog() -> list[RestrictionCatalogItem]:
    return engine_adapter.restriction_catalog()


@router.post("/profile/parse", response_model=ProfileParseResponse)
async def parse_profile(body: ProfileParseRequest, router: LLMRouter = Depends(get_router)) -> ProfileParseResponse:
    with stage("parse"):
        return await parse_profiles(body.text, body.lang, router)


@router.post("/explain", response_model=ExplainResponse)
async def explain(body: ExplainRequest, router: LLMRouter = Depends(get_router)) -> ExplainResponse:
    with stage("explain"):
        return await explain_term(body.term, body.lang, router)
