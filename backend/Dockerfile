# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/backend

FROM base AS runtime

COPY pyproject.toml README.md ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install .

CMD ["python", "-m", "backend_api.server", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS test

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install '.[test]'

CMD ["python", "-m", "pytest"]

FROM base AS development

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
COPY examples ./examples
COPY tools ./tools

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -e '.[dev]'

CMD ["python", "-m", "pytest"]
