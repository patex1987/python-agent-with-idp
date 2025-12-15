# syntax=docker/dockerfile:1.7

ARG UV_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm-slim
FROM ${UV_IMAGE} AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/venv \
    PATH=/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl tini htop \
 && rm -rf /var/lib/apt/lists/*

# use the selected folder as the virtual environment path
ENV UV_PROJECT_ENVIRONMENT=/venv
ENV PATH=/venv/bin:$PATH
WORKDIR /app

# ---------- dependencies (cache-friendly) ----------
FROM base AS dependencies
# copy only metadata first
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md
# COPY uv.lock /app/uv.lock   # (optional if you keep a lock)

# install third-party dependencies only
# TODO: check caching improvements: https://docs.docker.com/build/cache/optimize/#use-cache-mounts
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --no-install-project --no-dev --frozen || \
  uv sync --no-install-project --no-dev

# ---------- build (normal install) ----------
FROM dependencies AS build
COPY llm_agent /app/llm_agent
COPY manage.py /app/manage.py
RUN uv sync --no-dev --compile-bytecode --no-editable

# ---------- dev (editable install) ----------
FROM dependencies AS dev

RUN apt-get update && apt-get install -y --no-install-recommends vim \
 && rm -rf /var/lib/apt/lists/*

COPY llm_agent /app/llm_agent
COPY manage.py /app/manage.py
RUN uv sync --dev
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini","--"]
#CMD ["uvicorn","llm_agent.app:create_app","--host","0.0.0.0","--port","8080","--reload","--log-config","./llm_agent/configuration/log_config_json.json","--factory"]
CMD ["python", "manage.py"]

# ---------- prod (lean runtime) ----------
FROM base AS prod
COPY --from=build /venv /venv
COPY --from=build /app /app
RUN useradd -r -u 10001 appuser && chown -R appuser:appuser /app /venv
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD \
  sh -c 'curl -fsS http://127.0.0.1:8080/api/v1/health/dummy-health || exit 1'
ENTRYPOINT ["/usr/bin/tini","--"]
#CMD ["uvicorn","llm_agent.app:create_app","--host","0.0.0.0","--port","8080","--log-config","./llm_agent/configuration/log_config_json.json","--factory"]
CMD ["python", "manage.py"]

