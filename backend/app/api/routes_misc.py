"""GET /api/health, GET /api/catalog, POST /api/profile/parse, POST /api/explain."""
from __future__ import annotations

from fastapi import APIRouter

from backend.app import engine_adapter, fixtures
from backend.app.config import get_settings
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
async def health() -> HealthResponse:
    providers = await probe_providers(get_settings())
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
