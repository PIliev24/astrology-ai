FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . .
RUN uv sync --frozen --no-dev

# Expose port (Railway will set PORT env var)
EXPOSE 8000

# Run the application (use PORT env var if provided, default to 8000)
CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]