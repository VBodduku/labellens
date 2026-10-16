"""One JSON log line per request, with per-stage timings collected through a context variable."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("labellens")


@dataclass
class RequestLog:
    request_id: str
    stages: dict[str, int] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)


_current: ContextVar[RequestLog | None] = ContextVar("labellens_request_log", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "msg": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers[:] = [handler]
    logger.setLevel(level)
    logger.propagate = False


def start_request(request_id: str) -> RequestLog:
    log = RequestLog(request_id=request_id)
    _current.set(log)
    return log


def current_request() -> RequestLog | None:
    return _current.get()


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Time a pipeline stage and record it on the current request's log line."""
    started = time.perf_counter()
    try:
        yield
    finally:
        log = _current.get()
        if log is not None:
            elapsed = int((time.perf_counter() - started) * 1000)
            log.stages[name] = log.stages.get(name, 0) + elapsed
