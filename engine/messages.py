"""English fallback rendering; wire parameters remain canonical and label text is verbatim."""
from __future__ import annotations

import json
from types import MappingProxyType
from typing import Mapping
from engine.kb_loader import DISPLAY_NAMES, ROOT

TEMPLATES: Mapping[str, str] = MappingProxyType(json.loads((ROOT.parent / "shared/messages.en.json").read_text(encoding="utf-8")))


def render(key: str, params: dict[str, str | float]) -> str:
    display: dict[str, str | float] = dict(params)
    for field, names in (("category", DISPLAY_NAMES.categories), ("nutrient", DISPLAY_NAMES.nutrients),
                         ("basis", DISPLAY_NAMES.bases)):
        if field in display:
            display[field] = " or ".join(names.get(part, part) for part in str(display[field]).split("|"))
    return TEMPLATES[key].format_map(display)
