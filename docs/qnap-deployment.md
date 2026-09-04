# Deploying UnifiMCP to QNAP Container Station

This guide covers deploying the HTTP-transport build of UnifiMCP to a QNAP
NAS running Container Station, pulling a prebuilt image from GitHub
Container Registry (ghcr.io) rather than building on the NAS.

Two containers run from a **single image**, separated only by their
`command:`:

| Service | Port | Purpose |
|---------|------|---------|
| `unifi-mcp` | 8765 | MCP Streamable HTTP endpoint (`/mcp`), bearer-token protected |
| `unifi-mcp-admin` | 8766 | Web UI for minting and revoking those bearer tokens |

They share a Docker named volume (`unifi-mcp-data`) holding the SQLite token
database, so the admin service writes tokens the MCP server can validate
without any network call between them.

## 1. Publish the image

Built and pushed from a workstation, not the NAS:

```bash
# One-time: authenticate to ghcr.io with a PAT that has write:packages
gh auth token | docker login ghcr.io -u <github-username> --password-stdin

# Multi-arch so the same tag works on x86_64 and ARM QNAP models
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/nntkio/unifi-mcp:latest \
  --push .
```

If the resulting package is private, either make it public in the GitHub
package settings, or run `docker login ghcr.io` on the NAS with a PAT that
has `read:packages`.

## 2. Stage the deployment files on the NAS

Copy `deploy/docker-compose.qnap.yml` and `deploy/qnap.env.example` into a
directory on the NAS — e.g. `/share/CACHEDEV2_DATA/container/unifi-mcp/` —
then create the real environment file:

```bash
cp qnap.env.example qnap.env
```

Fill in `qnap.env`:

- `UNIFI_HOST`, `UNIFI_USERNAME`, `UNIFI_PASSWORD` — your controller and its
  credentials. Set `UNIFI_IS_UNIFI_OS=true` for a UDM/UDM Pro/UCG, and
  `UNIFI_VERIFY_SSL=false` for the usual self-signed certificate.
- `ROOT_ADMIN_PASSWORD` — the admin UI's root login. Root has no database
  row, which is what makes it structurally unable to own a bearer token.
- `ADMIN_SESSION_SECRET` — signs session cookies. Generate one with:

  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

`MCP_TRANSPORT=http` is the setting that switches the server off stdio;
without it the container starts a stdio server that nothing can reach.

## 3. Start the services

```bash
docker compose -f docker-compose.qnap.yml --env-file qnap.env pull
docker compose -f docker-compose.qnap.yml --env-file qnap.env up -d
```

Verify the MCP server is healthy — this endpoint is deliberately
unauthenticated so the Docker healthcheck works:

```bash
curl http://<nas-ip>:8765/healthz     # expect: ok
```

And confirm the endpoint actually rejects unauthenticated MCP traffic:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://<nas-ip>:8765/mcp
# expect: 401
```

## 4. Mint a bearer token

1. Open `http://<nas-ip>:8766/login` and log in as `root` with
   `ROOT_ADMIN_PASSWORD`.
2. On `/admin`, create an account for each person who needs access, with a
   temporary password.
3. Log out, then log back in as that account. You land on `/tokens`.
4. Create a token with a label and an expiry. **It is displayed exactly
   once** — only its SHA-256 hash is stored, so copy it immediately.

Root cannot create tokens for itself; it only provisions accounts and can
revoke anyone's token from `/admin`.

## 5. Point an MCP client at it

```json
{
  "mcpServers": {
    "unifi": {
      "url": "http://<nas-ip>:8765/mcp",
      "headers": {
        "Authorization": "Bearer <the token you just copied>"
      }
    }
  }
}
```

Check your client's documentation for its exact remote-server config shape;
the fields above are what a Streamable HTTP client needs.

## Security notes

- **Traffic is plain HTTP.** Admin passwords and freshly minted tokens cross
  the LAN in cleartext. This is an explicit non-goal of the current design
  (see `docs/superpowers/specs/2026-07-13-http-transport-design.md`). Put
  both ports behind a reverse proxy with TLS before exposing them beyond a
  trusted network, and never port-forward 8765/8766 from the internet.
- A valid token grants **everything the MCP server can do**, including
  mutating operations like restarting devices and changing firewall rules.
  There is no per-token scoping. Prefer short expiries.
- The token database lives only in the `unifi-mcp-data` volume. Deleting the
  volume invalidates every issued token.

## Upgrading

```bash
docker compose -f docker-compose.qnap.yml --env-file qnap.env pull
docker compose -f docker-compose.qnap.yml --env-file qnap.env up -d
```

Issued tokens and accounts survive, since they live in the named volume
rather than the image.

## Troubleshooting

**Container exits immediately with `AttributeError: 'Server' object has no
attribute 'list_tools'`** — the image was built against an incompatible
`mcp` release. The Dockerfile installs from `uv.lock` specifically to
prevent this; make sure you did not build with a modified Dockerfile that
re-resolves dependencies.

**`unifi-mcp-admin` exits with `KeyError: 'ADMIN_SESSION_SECRET'`** — the
variable is missing from `qnap.env`. Both it and `ROOT_ADMIN_PASSWORD` are
required, and the service refuses to start without them.

**Every MCP request returns 401** — the token is unknown, revoked, or
expired, or `TOKEN_DB_PATH` differs between the two services. Both must
point at the same file on the shared volume (`/data/tokens.db`).
