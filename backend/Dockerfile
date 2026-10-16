# LabelLens backend. Build from the REPO ROOT (it copies shared/, engine/ and backend/):
#   docker build -f backend/Dockerfile -t labellens-api .
#   docker run -p 7860:7860 -e GEMINI_API_KEY=... labellens-api
# Hugging Face Docker Spaces use this file as the Space's root Dockerfile (see backend/README.md).
FROM python:3.12-slim

# rapidocr-onnxruntime pulls in opencv-python, which needs these system libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run the container as user 1000.
RUN useradd --create-home --uid 1000 user
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY shared/ shared/
COPY engine/*.py engine/
COPY engine/kb/ engine/kb/
COPY backend/__init__.py backend/__init__.py
COPY backend/app/ backend/app/

ENV PYTHONUNBUFFERED=1 \
    ENGINE_MODE=real \
    CACHE_DIR=/tmp/labellens-cache \
    OLLAMA_BASE_URL=http://localhost:11434 \
    PORT=7860

USER user
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD curl -fsS "http://localhost:${PORT}/api/catalog" > /dev/null || exit 1
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
