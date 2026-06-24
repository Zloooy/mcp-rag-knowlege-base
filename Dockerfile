FROM python:3.14-slim

WORKDIR /app

# Build dependencies (gcc/g++ for tree-sitter native extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Install uv and sync dependencies from lockfile
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv sync --frozen --no-dev

# Copy application code and prompts
COPY prompts/ ./prompts
COPY src/ ./src
COPY __main__.py ./

# Persisted directories (mounted via volumes at runtime)
RUN mkdir -p /data/chroma_db /data/documents

ENV PYTHONPATH=/app/src

EXPOSE 8000

ENTRYPOINT ["uv", "run", "--no-sync", "."]
