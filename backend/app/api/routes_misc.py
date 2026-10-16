"""GET /api/health, GET /api/catalog, POST /api/profile/parse, POST /api/explain."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app import engine_adapter, fixtures
from backend.app.config import get_settings
from backend.app.llm.router import LLMRouter, get_router
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
def parse_profile(body: ProfileParseRequest) -> ProfileParseResponse:
    return fixtures.profile_parse()


@router.post("/explain", response_model=ExplainResponse)
def explain(body: ExplainRequest) -> ExplainResponse:
    return fixtures.explain()
