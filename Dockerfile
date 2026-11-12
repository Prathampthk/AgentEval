# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --strict-ssl=true
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 AGENTEVAL_PROJECT_ROOT=/app
WORKDIR /app
COPY requirements-runtime.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements-runtime.lock
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-build-isolation --no-deps .
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY examples/ ./examples/
COPY scripts/ ./scripts/
COPY deploy/ ./deploy/
COPY reports/judge_validation.json ./reports/judge_validation.json
COPY --from=frontend /build/dist/ ./frontend/dist/
RUN chmod -R a+rX /app && groupadd --gid 10001 agenteval && useradd --uid 10001 --gid 10001 --no-create-home agenteval
RUN mkdir /budgets && chown 10001:10001 /budgets && chmod 700 /budgets
USER 10001:10001
CMD ["uvicorn", "agenteval.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--limit-concurrency", "64", "--backlog", "128"]

FROM runtime AS verification
USER root
COPY requirements.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.lock
COPY tests/ ./tests/
RUN chmod -R a+rX /app/tests
USER 10001:10001
CMD ["pytest", "-q", "-p", "no:cacheprovider", "--junitxml=/tmp/tests.xml"]
