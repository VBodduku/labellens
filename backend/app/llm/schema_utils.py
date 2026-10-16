"""Turn a Pydantic model into a self-contained JSON schema both Gemini and Ollama accept."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_DROP_KEYS = {"title", "default"}


def _inline(node: Any, defs: dict[str, Any], require_all: bool) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            return _inline(defs[ref.rsplit("/", 1)[-1]], defs, require_all)
        result = {k: _inline(v, defs, require_all) for k, v in node.items() if k not in _DROP_KEYS and k != "$defs"}
        if require_all and isinstance(result.get("properties"), dict):
            result["required"] = list(result["properties"])
        return result
    if isinstance(node, list):
        return [_inline(item, defs, require_all) for item in node]
    return node


def inline_schema(model: type[BaseModel], require_all: bool = True) -> dict[str, Any]:
    """model_json_schema() with every $ref expanded and titles/defaults removed.

    require_all marks every field required: small local models (constrained decoding) otherwise skip
    optional lists entirely. Gemini fills optional fields reliably, and leaving out nulls and empty
    lists makes its answer shorter, which is most of its latency."""
    schema = model.model_json_schema()
    result: dict[str, Any] = _inline(schema, schema.get("$defs", {}), require_all)
    return result
