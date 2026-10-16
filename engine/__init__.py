"""LabelLens public engine API; inputs and outputs use the frozen shared contract."""
from shared.contract import CATEGORIES, RestrictionCatalogItem
from engine.explain import explain_term
from engine.kb_loader import CATALOG
from engine.nutrition import analyze_nutrition
from engine.rules import evaluate

__all__ = ["evaluate", "analyze_nutrition", "explain_term", "restriction_catalog", "category_vocabulary"]


def restriction_catalog() -> list[RestrictionCatalogItem]:
    return [RestrictionCatalogItem.model_validate(item.model_dump()) for item in CATALOG]


def category_vocabulary() -> list[str]:
    return list(CATEGORIES)
