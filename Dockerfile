FROM python:3.13-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies
RUN uv pip install --system -e .

# Set environment variables (can be overridden at runtime)
ENV UNIFI_HOST=""
ENV UNIFI_USERNAME=""
ENV UNIFI_PASSWORD=""
ENV UNIFI_SITE="default"
ENV UNIFI_VERIFY_SSL="true"
ENV UNIFI_IS_UNIFI_OS="false"

# Run the MCP server
CMD ["unifi-mcp"]
