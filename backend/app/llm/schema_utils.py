"""Turn a Pydantic model into a self-contained JSON schema both Gemini and Ollama accept."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_DROP_KEYS = {"title", "default"}


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            return _inline(defs[ref.rsplit("/", 1)[-1]], defs)
        result = {k: _inline(v, defs) for k, v in node.items() if k not in _DROP_KEYS and k != "$defs"}
        if isinstance(result.get("properties"), dict):
            # Every field required: constrained decoders otherwise skip optional lists entirely.
            result["required"] = list(result["properties"])
        return result
    if isinstance(node, list):
        return [_inline(item, defs) for item in node]
    return node


def inline_schema(model: type[BaseModel]) -> dict[str, Any]:
    """model_json_schema() with every $ref expanded, titles/defaults removed, all fields required."""
    schema = model.model_json_schema()
    result: dict[str, Any] = _inline(schema, schema.get("$defs", {}))
    return result
