"""Explicit evaluation-only HTTP transport; the engine's public API remains offline."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from shared.contract import HealthResponse, Profile, ScanResult


@dataclass(frozen=True)
class CaptureCase:
    folder: Path
    source: Literal["real", "synthetic"]


class CaptureError(RuntimeError):
    """A failed capture must not silently disappear from the measured dataset."""


def _request(request: Request, timeout: float) -> bytes:
    try:
        with urlopen(request, timeout=timeout) as response:
            return bytes(response.read())
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise CaptureError(f"{request.method} {request.full_url}: {error}") from error


def _base_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Backend must be an http(s) URL without credentials, query, or fragment"
        )
    return url.rstrip("/")


def images_for_case(folder: Path) -> list[Path]:
    images: list[Path] = []
    for index in range(3):
        candidates = [
            path
            for path in folder.iterdir()
            if path.is_file()
            and path.stem == f"img_{index}"
            and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        if len(candidates) > 1:
            raise ValueError(f"{folder.name}: duplicate img_{index} files")
        if candidates:
            if len(images) != index:
                raise ValueError(
                    f"{folder.name}: image numbers must be contiguous starting at img_0"
                )
            path = candidates[0]
            if not 0 < path.stat().st_size <= 400 * 1024:
                raise ValueError(
                    f"{folder.name}: {path.name} must be nonempty and at most 400 KB"
                )
            images.append(path)
    if not images:
        raise ValueError(f"{folder.name}: no img_0.jpg/jpeg/png found")
    if any(
        path.stem.startswith("img_") and path.stem not in {"img_0", "img_1", "img_2"}
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ):
        raise ValueError(f"{folder.name}: at most three numbered panels are supported")
    return images


def multipart(images: list[Path], profiles: list[Profile]) -> tuple[bytes, str]:
    profile_json = json.dumps(
        [profile.model_dump(mode="json") for profile in profiles], ensure_ascii=False
    ).encode("utf-8")
    files = [(path, path.read_bytes()) for path in images]
    digest = sha256(profile_json + b"".join(data for _, data in files)).hexdigest()
    boundary = "labellens-eval-" + digest
    chunks: list[bytes] = []
    for name, value in (("profiles", profile_json), ("lang", b"en")):
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            + value
            + b"\r\n"
        )
    for index, (path, data) in enumerate(files):
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        # Fixed filenames avoid injecting directory names into multipart headers.
        filename = f"img_{index}.png" if mime == "image/png" else f"img_{index}.jpg"
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
            + data
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def capture(
    backend: str,
    cases: list[CaptureCase],
    responses: Path,
    profiles: list[Profile],
    timeout: float = 60.0,
) -> None:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Request timeout must be finite and positive")
    if not cases:
        raise ValueError("No packet cases to capture")
    if not profiles or len({profile.profile_id for profile in profiles}) != len(
        profiles
    ):
        raise ValueError("Evaluation profiles must be nonempty with unique profile IDs")
    backend = _base_url(backend)
    # Validate the whole input batch before requesting any captures.
    inputs = [(case, images_for_case(case.folder)) for case in cases]
    health = HealthResponse.model_validate_json(
        _request(Request(backend + "/api/health"), min(timeout, 5.0))
    )
    if health.engine_mode != "real":
        raise CaptureError(
            "Backend engine_mode is stub. Ask the humans to restart with ENGINE_MODE=real"
        )
    responses.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    failures: list[str] = []
    for case, images in inputs:
        case_id = case.folder.name
        start = perf_counter()
        try:
            body, content_type = multipart(images, profiles)
            request = Request(
                backend + "/api/scan",
                data=body,
                headers={"Content-Type": content_type},
                method="POST",
            )
            scan = ScanResult.model_validate_json(_request(request, timeout))
            if case.source == "real" and scan.extraction.meta.provider == "fixture":
                raise CaptureError(
                    "Backend returned fixture extraction for a real packet; refusing a real accuracy claim"
                )
            (responses / f"{case_id}.json").write_text(
                scan.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            results.append(
                dict(
                    packet_id=case_id,
                    status="captured",
                    provider=scan.extraction.meta.provider,
                    cache_hit=scan.extraction.meta.cache_hit,
                    request_ms=round((perf_counter() - start) * 1000, 2),
                )
            )
        except (CaptureError, ValueError, OSError) as error:
            failures.append(case_id)
            results.append(dict(packet_id=case_id, status="failed", error=str(error)))
    (responses / "capture_manifest.json").write_text(
        json.dumps(
            dict(
                backend=backend,
                engine_mode=health.engine_mode,
                profiles=[profile.model_dump(mode="json") for profile in profiles],
                cases=results,
                failed=failures,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    if failures:
        raise CaptureError(
            f"Capture failed for {', '.join(failures)}. No accuracy report generated; inspect capture_manifest.json and retry the complete batch"
        )
