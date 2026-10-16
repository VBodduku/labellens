from __future__ import annotations

from collections.abc import Callable
import pytest
from shared.contract import (
    Evidence, ExtractionMeta, Ingredient, LabelExtraction, Profile, Restriction,
    SectionStatus, VegMark,
)
from engine.kb_loader import BY_KEY


@pytest.fixture
def make_extraction() -> Callable[..., LabelExtraction]:
    def make(*names: str, complete: bool = True, presence: str = "found", mark: str = "not_found") -> LabelExtraction:
        return LabelExtraction(
            scan_id="test", images=[],
            ingredients=[Ingredient(id=f"ing_{index}", name=name, raw_text=name,
                                    evidence=[Evidence(image_id="img_0", text=name, status="verified")])
                         for index, name in enumerate(names)],
            ingredients_section=SectionStatus(presence=presence, complete=complete),
            nutrition_section=SectionStatus(presence="not_found", complete=False),
            allergen_section=SectionStatus(presence="not_found", complete=False),
            veg_mark=VegMark(value=mark), meta=ExtractionMeta(provider="ocr_only", model="test"),
        )
    return make


@pytest.fixture
def make_profile() -> Callable[..., Profile]:
    def make(key: str = "peanut", severity: str = "strict") -> Profile:
        entry = BY_KEY.get(key)
        restriction = Restriction(id="r", key=key, kind=entry.kind if entry else "avoid",
                                  label=key, severity=severity)
        return Profile(profile_id="p", name="Test", restrictions=[restriction])
    return make
