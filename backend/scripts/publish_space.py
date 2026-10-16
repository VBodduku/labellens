"""Publish the backend to a Hugging Face Docker Space and wait until /api/health answers.

Needs `pip install huggingface_hub` and `hf auth login` (a write token). Secrets are never handled
here: add GEMINI_API_KEY yourself in the Space settings (Settings -> Variables and secrets).
Usage (repo root): python -m backend.scripts.publish_space <user>/<space> [--cors https://app.vercel.app]
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import time
from pathlib import Path

import httpx
from huggingface_hub import HfApi

from backend.app.config import REPO_ROOT

HEALTH_TIMEOUT_S = 15 * 60
SPACE_README = """---
title: LabelLens API
emoji: 🔎
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

LabelLens backend (FastAPI). Endpoints under `/api` - see `/api/health`.
"""
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "eval", ".gitkeep")


def assemble(target: Path) -> None:
    """The Space repo: Dockerfile at its root plus exactly what the Dockerfile copies."""
    shutil.copy(REPO_ROOT / "backend" / "Dockerfile", target / "Dockerfile")
    (target / "README.md").write_text(SPACE_README, encoding="utf-8")
    shutil.copytree(REPO_ROOT / "shared", target / "shared", ignore=IGNORE)
    (target / "engine").mkdir()
    for module in (REPO_ROOT / "engine").glob("*.py"):
        shutil.copy(module, target / "engine" / module.name)
    shutil.copytree(REPO_ROOT / "engine" / "kb", target / "engine" / "kb", ignore=IGNORE)
    (target / "backend").mkdir()
    shutil.copy(REPO_ROOT / "backend" / "__init__.py", target / "backend" / "__init__.py")
    shutil.copy(REPO_ROOT / "backend" / "requirements.txt", target / "backend" / "requirements.txt")
    shutil.copytree(REPO_ROOT / "backend" / "app", target / "backend" / "app", ignore=IGNORE)


def space_url(repo_id: str) -> str:
    owner, name = repo_id.split("/", 1)
    return f"https://{re.sub(r'[^a-z0-9]+', '-', f'{owner}-{name}'.lower())}.hf.space"


def wait_for_health(api: HfApi, repo_id: str, url: str) -> bool:
    deadline = time.monotonic() + HEALTH_TIMEOUT_S
    last_stage = ""
    while time.monotonic() < deadline:
        stage = api.get_space_runtime(repo_id).stage
        if stage != last_stage:
            print(f"  space: {stage}")
            last_stage = stage
        if stage in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            return False
        try:
            response = httpx.get(f"{url}/api/health", timeout=10)
            if response.status_code == 200:
                print(f"  /api/health: {response.text}")
                return True
        except httpx.HTTPError:
            pass
        time.sleep(15)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_id", help="<hf-user>/<space-name>, e.g. vbodduku/labellens-api")
    parser.add_argument("--cors", default="http://localhost:5173",
                        help="comma-separated allowed origins, e.g. the Vercel URL of the frontend")
    args = parser.parse_args()

    api = HfApi()
    api.create_repo(args.repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
    for key, value in {"ENGINE_MODE": "real", "CORS_ORIGINS": args.cors, "CACHE_DIR": "/tmp/labellens-cache"}.items():
        api.add_space_variable(args.repo_id, key, value)
    with tempfile.TemporaryDirectory() as tmp:
        assemble(Path(tmp))
        api.upload_folder(repo_id=args.repo_id, repo_type="space", folder_path=tmp,
                          commit_message="Deploy LabelLens backend")
    url = space_url(args.repo_id)
    print(f"uploaded -> https://huggingface.co/spaces/{args.repo_id}\nwaiting for {url}/api/health ...")
    if not wait_for_health(api, args.repo_id, url):
        raise SystemExit("the Space did not become healthy; open its Logs tab on huggingface.co")
    print(f"live: {url}  (add GEMINI_API_KEY as a Space secret if /api/health shows gemini=false)")


if __name__ == "__main__":
    main()
