# Notes from Part 2 (backend) for the other parts

## For Part 1 (frontend)
- Error bodies are always `ErrorResponse`. Besides the codes in the master spec, `NOT_FOUND` (404) can appear for a wrong URL; treat it like `INTERNAL`.
- An oversized photo returns **413 with `error_code: "BAD_IMAGE"`** and a message like "Each photo must be smaller than 8 MB."
- Every response carries an `X-Request-ID` header (exposed through CORS); showing it in error toasts helps us find the log line.

## For Part 3 (engine)
- `ENGINE_MODE=real` imports the top-level `engine` package and requires all five functions from `shared/engine_interface.py` to be importable from `engine/__init__.py`; otherwise every engine-backed endpoint fails with a clear error naming the missing functions.

## For main / humans
- Backend needs Python 3.12 (not 3.13) because of `rapidocr-onnxruntime`: `brew install python@3.12 && python3.12 -m venv .venv`.
- No contract changes requested.
