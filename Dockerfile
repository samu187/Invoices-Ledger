FROM node:22-bookworm-slim AS frontend-build

WORKDIR /project/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project

COPY backend/app ./app
RUN uv sync --locked

COPY --from=frontend-build /project/backend/app/static ./app/static

ENV PATH="/app/backend/.venv/bin:$PATH"

EXPOSE 8888

CMD ["ledger", "web"]
