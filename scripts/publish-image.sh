#!/usr/bin/env bash
# Build the UniFi MCP image and push it to GitHub Container Registry.
#
# Usage:
#   scripts/publish-image.sh [--local] [extra-tag]
#
#   (default)   Multi-arch build (linux/amd64, linux/arm64) pushed to ghcr.io,
#               tagged latest, the version from pyproject.toml, and sha-<git sha>.
#   extra-tag   One more tag to push alongside those, e.g. rc1.
#   --local     Build for this machine only and load it into the local docker
#               daemon as <IMAGE>:local. Nothing is pushed. Use it to run the
#               container before publishing.
#
# Environment overrides:
#   IMAGE        Image name                 (default ghcr.io/nntkio/unifi-mcp)
#   PLATFORMS    buildx platform list       (default linux/amd64,linux/arm64)
#   GHCR_USER    Registry username          (default: gh api user)
#   GHCR_TOKEN   PAT with write:packages    (default: gh auth token)
#
# Requires docker with buildx. Without GHCR_TOKEN it also needs the gh CLI
# logged in with a token that carries the write:packages scope.
set -euo pipefail

IMAGE="${IMAGE:-ghcr.io/nntkio/unifi-mcp}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
BUILDER="unifi-mcp-multiarch"
SOURCE_URL="https://github.com/nntkio/unifiMCP"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required but not installed"; }

usage() {
  # Print the header comment block above as the help text.
  sed -n '2,/^set -euo pipefail/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'
}

local_only=0
extra_tag=""
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --local) local_only=1 ;;
    --*) die "unknown option: $1 (see --help)" ;;
    *)
      [ -z "$extra_tag" ] || die "only one extra tag is accepted (got '$extra_tag' and '$1')"
      extra_tag="$1"
      ;;
  esac
  shift
done

need docker
need git
docker buildx version >/dev/null 2>&1 || die "docker buildx is required (Docker Desktop ships it; on Linux install docker-buildx-plugin)"

version="$(sed -n 's/^version = "\(.*\)"/\1/p' "$REPO_ROOT/pyproject.toml")"
[ -n "$version" ] || die "could not read the version from pyproject.toml"
sha="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"

if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
  warn "the working tree has uncommitted changes, so the image will not match commit $sha exactly"
fi

labels=(
  --label "org.opencontainers.image.source=$SOURCE_URL"
  --label "org.opencontainers.image.version=$version"
  --label "org.opencontainers.image.revision=$sha"
)

# ── Local build: host architecture only, loaded into docker, never pushed ──
if [ "$local_only" = 1 ]; then
  local_tag="$IMAGE:local"
  log "Building $local_tag for this machine (no push)"
  docker buildx build --load -t "$local_tag" "${labels[@]}" "$REPO_ROOT"
  log "Loaded $local_tag"
  printf '\nTry it:\n  docker run --rm -p 8765:8765 -e MCP_TRANSPORT=http -e TOKEN_DB_PATH=/tmp/tokens.db %s\n' "$local_tag"
  printf '  curl -i http://localhost:8765/healthz\n'
  exit 0
fi

# ── Registry login ────────────────────────────────────────────────────────
token="${GHCR_TOKEN:-}"
user="${GHCR_USER:-}"
if [ -z "$token" ]; then
  need gh
  token="$(gh auth token 2>/dev/null)" || die "gh is not logged in; run 'gh auth login' or set GHCR_TOKEN"
fi
if [ -z "$user" ]; then
  need gh
  user="$(gh api user --jq .login 2>/dev/null)" || die "could not resolve the GitHub username; set GHCR_USER"
fi
log "Logging in to ghcr.io as $user"
printf '%s' "$token" | docker login ghcr.io -u "$user" --password-stdin >/dev/null \
  || die "ghcr.io login failed; the token needs the write:packages scope (gh auth refresh -s write:packages)"

# ── Builder: the current one if it can do every platform, else a named one ──
builder_args=()
current_platforms="$(docker buildx inspect --bootstrap 2>/dev/null | sed -n 's/^Platforms: *//p' | head -1 | tr -d ' ')"
missing=0
IFS=',' read -ra wanted <<<"$PLATFORMS"
for platform in "${wanted[@]}"; do
  case ",$current_platforms," in
    *",$platform,"*) ;;
    *) missing=1 ;;
  esac
done
if [ "$missing" = 1 ]; then
  if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
    log "Creating buildx builder '$BUILDER' (docker-container driver) for $PLATFORMS"
    docker buildx create --name "$BUILDER" --driver docker-container >/dev/null
  fi
  builder_args=(--builder "$BUILDER")
fi

# ── Build and push ────────────────────────────────────────────────────────
tags=(-t "$IMAGE:latest" -t "$IMAGE:$version" -t "$IMAGE:sha-$sha")
if [ -n "$extra_tag" ]; then
  tags+=(-t "$IMAGE:$extra_tag")
fi

log "Building $IMAGE for $PLATFORMS at commit $sha (version $version)"
docker buildx build \
  ${builder_args[@]+"${builder_args[@]}"} \
  --platform "$PLATFORMS" \
  "${tags[@]}" \
  "${labels[@]}" \
  --push \
  "$REPO_ROOT"

log "Pushed:"
for tag in "${tags[@]}"; do
  [ "$tag" = "-t" ] && continue
  printf '  %s\n' "$tag"
done
printf '\nOn the NAS:\n  docker pull %s:latest\n' "$IMAGE"
