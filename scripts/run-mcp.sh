#!/usr/bin/env bash
# Launches unifi-mcp with credentials loaded from .env, so secrets never
# need to be duplicated into an MCP client's config file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"

if [[ -f "$ENV_FILE" ]]; then
  # Read as literal KEY=VALUE pairs rather than `source`-ing the file, since
  # sourcing treats values as shell code and mangles special characters
  # (e.g. a password containing $, !, or &).
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    export "$key=$value"
  done < "$ENV_FILE"
fi

# This script exists to be launched by an MCP client as a subprocess, so it
# always speaks stdio, whatever .env says (the same file serves docker
# compose, where MCP_TRANSPORT=http is the right setting).
export MCP_TRANSPORT=stdio

exec "$REPO_ROOT/.venv/bin/unifi-mcp"
