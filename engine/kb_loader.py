"""Fail-fast, typed KB loading. Public API callers receive copies, never cached objects."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import MappingProxyType
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from shared.contract import CATEGORIES, NUTRIENT_KEYS, Origin, RestrictionCatalogItem
from engine.normalize import normalize

ROOT = Path(__file__).resolve().parent
T = TypeVar("T", bound=BaseModel)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Names(FrozenModel):
    en: tuple[str, ...]
    hi: tuple[str, ...] = ()
    te: tuple[str, ...] = ()

    @field_validator("en")
    @classmethod
    def nonempty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not name.strip() for name in value):
            raise ValueError("Every term needs a non-empty English alias")
        return value


def check_categories(value: tuple[str, ...]) -> tuple[str, ...]:
    if set(value) - set(CATEGORIES):
        raise ValueError(f"Unknown categories: {set(value) - set(CATEGORIES)}")
    return value


class Term(FrozenModel):
    id: str
    names: Names
    ins: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    possible_categories: tuple[str, ...] = ()
    origin: Origin
    notes: str
    confidence: Literal["high", "medium"]
    review_reason: str | None = None

    _categories = field_validator("categories", "possible_categories")(check_categories)

    @model_validator(mode="after")
    def consistent(self) -> Term:
        if self.possible_categories and self.origin != "varies":
            raise ValueError("Possible categories require varies origin")
        if not self.notes.strip():
            raise ValueError("Every entry needs notes")
        if self.review_reason is not None and not self.review_reason.strip():
            raise ValueError("Review reasons cannot be empty")
        if set(self.categories) & set(self.possible_categories):
            raise ValueError("Definite and possible categories overlap")
        if any(
            not re.fullmatch(r"\d{3,4}[a-f]?(?:\(i{1,3}v?\))?", code)
            for code in self.ins
        ):
            raise ValueError("Invalid INS code syntax")
        return self


class CatalogItem(RestrictionCatalogItem):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("categories")
    @classmethod
    def valid_categories(cls, value: list[str]) -> list[str]:
        check_categories(tuple(value))
        return value


class StatementItem(FrozenModel):
    names: tuple[str, ...]
    categories: tuple[str, ...]
    possible_categories: tuple[str, ...] = ()
    _categories = field_validator("categories", "possible_categories")(check_categories)


class ClaimRule(FrozenModel):
    """A front-of-pack claim and what on the back label would contradict it."""
    id: str
    phrases: tuple[str, ...]
    categories: tuple[str, ...]
    nutrient: str | None = None     # the claim also fails when this nutrient is above max_value
    max_value: float = 0.0
    _categories = field_validator("categories")(check_categories)

    @field_validator("nutrient")
    @classmethod
    def valid_nutrient(cls, value: str | None) -> str | None:
        if value is not None and value not in NUTRIENT_KEYS:
            raise ValueError("Unknown nutrient key")
        return value


class Qualifier(FrozenModel):
    phrases: tuple[str, ...]
    origin: Origin
    add_categories: tuple[str, ...] = ()
    remove_categories: tuple[str, ...] = ()
    term_ids: tuple[str, ...]
    _categories = field_validator("add_categories", "remove_categories")(
        check_categories
    )


class Nutrient(FrozenModel):
    key: str
    names: tuple[str, ...]
    unit: Literal["g", "mg", "kcal"]
    conversions: dict[str, float]

    @field_validator("key")
    @classmethod
    def valid_key(cls, value: str) -> str:
        if value not in NUTRIENT_KEYS:
            raise ValueError("Unknown nutrient key")
        return value


class DisplayNames(FrozenModel):
    categories: dict[str, str]
    nutrients: dict[str, str]
    bases: dict[str, str]

    @model_validator(mode="after")
    def complete(self) -> DisplayNames:
        if set(self.categories) != set(CATEGORIES):
            raise ValueError("Display names must cover exactly CATEGORIES")
        if set(self.nutrients) != set(NUTRIENT_KEYS):
            raise ValueError("Display names must cover exactly NUTRIENT_KEYS")
        if set(self.bases) != {"per_100g", "per_100ml", "per_serving", "per_pack"}:
            raise ValueError("Display names must cover all bases")
        return self


def load_list(name: str, model: type[T]) -> tuple[T, ...]:
    data = json.loads((ROOT / "kb" / name).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{name} must contain a JSON list")
    return tuple(model.model_validate(row) for row in data)


TERMS = load_list("terms.json", Term)
CATALOG = load_list("catalog.json", CatalogItem)
STATEMENTS = load_list("statement_items.json", StatementItem)
QUALIFIERS = load_list("qualifiers.json", Qualifier)
NUTRIENTS = load_list("nutrients.json", Nutrient)
CLAIMS = load_list("claims.json", ClaimRule)
DISPLAY_NAMES = DisplayNames.model_validate_json(
    (ROOT / "kb/names.json").read_text(encoding="utf-8")
)


def validate_indexes() -> None:
    for label, ids in (
        ("term", [t.id for t in TERMS]),
        ("catalog", [c.key for c in CATALOG]),
    ):
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate {label} ids")
    aliases: dict[str, str] = {}
    codes: set[str] = set()
    for term in TERMS:
        for names in (term.names.en, term.names.hi, term.names.te):
            for alias in names:
                key = normalize(alias)
                if key in aliases and aliases[key] != term.id:
                    raise ValueError(
                        f"Duplicate alias {alias}: {aliases[key]}, {term.id}"
                    )
                aliases[key] = term.id
        if codes.intersection(term.ins):
            raise ValueError(f"Duplicate INS code on {term.id}")
        codes.update(term.ins)
    fixtures = json.loads(
        (ROOT.parent / "shared/fixtures/catalog.json").read_text(encoding="utf-8")
    )
    if {row["key"] for row in fixtures} - {c.key for c in CATALOG}:
        raise ValueError("Catalog missing fixture keys")
    for qualifier in QUALIFIERS:
        if set(qualifier.term_ids) - {term.id for term in TERMS}:
            raise ValueError("Qualifier references unknown term")


validate_indexes()
BY_ID = MappingProxyType({term.id: term for term in TERMS})
BY_CODE = MappingProxyType({code: term for term in TERMS for code in term.ins})
BY_KEY = MappingProxyType({item.key: item for item in CATALOG})
ALIASES = tuple(
    sorted(
        {
            (normalize(alias), term.id)
            for term in TERMS
            for names in (term.names.en, term.names.hi, term.names.te)
            for alias in names
        },
        key=lambda pair: (-len(pair[0]), pair[0], pair[1]),
    )
)
