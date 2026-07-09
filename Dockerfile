FROM python:3.13-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install dependencies
RUN uv pip install --system -e .

# Credentials are supplied at container run time (see docker-compose.yml),
# never at build time, so they are never baked into an image layer.

# Run the MCP server
CMD ["unifi-mcp"]
