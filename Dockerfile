# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_PATH=/mcp

COPY pyproject.toml README.md ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir .

EXPOSE 8000

CMD ["ai-pose-gallery-mcp"]
