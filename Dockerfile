# DartsMod API container.
# Build:  docker build -t dartsmod .
# Run:    docker run -p 8000:8000 dartsmod
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY dartsmod ./dartsmod

RUN pip install --no-cache-dir ".[api]"

EXPOSE 8000

# Respect a platform-provided $PORT (Render, Railway, Cloud Run, ...) if present.
ENV PORT=8000
CMD ["sh", "-c", "uvicorn dartsmod.api:api --host 0.0.0.0 --port ${PORT}"]
