# Optimized multi-stage Dockerfile for ct-app
# Uses slim base image and layer caching for faster builds and smaller image size

# Stage 1: Builder - Install dependencies
FROM python:3.14-slim AS builder

# Install uv package manager (0.9.x+ supports Python 3.14)
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

# Set working directory
WORKDIR /code

# Copy dependency files first for better layer caching
# When these files don't change, Docker will reuse cached layers
COPY pyproject.toml uv.lock .python-version ./
COPY core/pyproject.toml ./core/
COPY core/api/pyproject.toml ./core/api/
COPY core/components/pyproject.toml ./core/components/
COPY core/subgraph/pyproject.toml ./core/subgraph/
COPY core/rpc/pyproject.toml ./core/rpc/
COPY test/pyproject.toml ./test/
COPY .configs ./.configs/
COPY scripts ./scripts/

# Copy source code needed for editable installs (setuptools needs to find packages)
COPY core/__init__.py ./core/
COPY core/__main__.py ./core/
COPY core/node.py ./core/
COPY core/mixins ./core/mixins/
COPY core/rpc ./core/rpc/
COPY core/api ./core/api/
COPY core/components ./core/components/
COPY core/subgraph ./core/subgraph/
COPY test ./test/

# Install production dependencies only (no dev dependencies)
RUN uv sync --frozen --no-dev

# Install uv itself in the venv (so runtime can call uv)
RUN uv pip install uv

# Install your project into the env
RUN uv pip install --no-cache-dir ./core
RUN uv pip install --no-cache-dir .

# Stage 2: Runtime - Minimal production image
FROM python:3.14-slim AS runtime

# Add metadata labels
LABEL maintainer="HOPR Team"
LABEL description="CT-App - HOPR Cover Traffic Application"

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser

# Set working directory
WORKDIR /code

# Copy the prebuilt virtual environment
COPY --from=builder /code/.venv /code/.venv

# Copy application source code and scripts
COPY --from=builder --chown=appuser:appuser /code/core ./core
COPY --from=builder --chown=appuser:appuser /code/test ./test
COPY --from=builder --chown=appuser:appuser /code/scripts ./scripts
COPY --from=builder --chown=appuser:appuser /code/.configs ./.configs

# Set PATH to use Python and uv from venv
ENV PATH="/code/.venv/bin:$PATH"

# Make run script executable
RUN chmod +x ./scripts/run.sh

# Switch to non-root user
USER appuser

# Entrypoint
ENTRYPOINT ["./scripts/run.sh", "--no-log-file"]