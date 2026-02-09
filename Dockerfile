FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a separate file system
ENV UV_LINK_MODE=copy

# Install dependencies (only pyproject.toml and uv.lock are needed for this step)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy the entire src directory to satisfy internal imports (src.config, src.database, etc.)
COPY src/ ./src/
COPY .env.example ./

# Create data directory for SQLite persistence
RUN mkdir -p /app/data

# Default environment variables for Zeabur / Production
# Zeabur typically uses port 8080 by default
ENV PINCER_HOST="0.0.0.0"
ENV PINCER_PORT="8080"
ENV DATABASE_PATH="/app/data/pincer.db"
ENV LOG_LEVEL="INFO"
ENV LOG_FORMAT="json"

# Expose the port
EXPOSE 8080

# Run the pincer service using uv
# This ensures the virtual environment managed by uv is used
CMD ["uv", "run", "python", "src/pincer/server.py"]
