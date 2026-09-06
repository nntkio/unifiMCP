FROM python:3.13-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install the exact dependency versions recorded in uv.lock instead of
# re-resolving at build time. An unpinned resolve silently pulled in mcp 2.x,
# whose low-level Server API is incompatible with this code, so the image
# must match the dependency set the test suite actually runs against.
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
 && uv pip install --system --no-deps -r /tmp/requirements.txt \
 && uv pip install --system --no-deps -e . \
 && rm /tmp/requirements.txt

# Credentials are supplied at container run time (see docker-compose.yml),
# never at build time, so they are never baked into an image layer.

# Run the MCP server
CMD ["unifi-mcp"]
