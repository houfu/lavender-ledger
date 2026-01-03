# Lavender Ledger Dashboard
# Read-only dashboard for family access

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Create non-root user
RUN useradd --create-home appuser

# Install Claude Code CLI (if available)
# Note: You may need to manually install Claude Code in the container
# or mount the claude binary from the host system

USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the dashboard
ENV FLASK_ENV=production
CMD ["uv", "run", "python", "-m", "src.dashboard.app"]
