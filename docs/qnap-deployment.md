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

Both listen on plain HTTP. If you have a reverse proxy terminating TLS (see
"Fronting with a reverse proxy" below), point clients at that instead of at
the NAS directly.

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

## 2b. Alternative: deploy through the Container Station UI

If SSH is disabled on the NAS, create the application from Container
Station's web UI instead. Its "Create Application" box pastes YAML into its
own working directory, where a sibling `qnap.env` usually will not resolve —
so use `deploy/docker-compose.container-station.yml`, which inlines the
settings with `environment:` rather than `env_file:`.

1. Container Station → **Applications** → **Create**.
2. Paste the contents of `deploy/docker-compose.container-station.yml`.
3. Replace every `<...>` placeholder — controller URL and credentials,
   `ROOT_ADMIN_PASSWORD`, and a generated `ADMIN_SESSION_SECRET`.
4. **Create**, then continue from section 3 to verify.

Be aware that Container Station stores these values in its application
config, so the controller password and root admin password are readable by
anyone with NAS admin access. The `env_file` approach in section 2 keeps
them in a file you control instead.

If the image is a private package, add your ghcr.io credentials to Container
Station's registry list first, or the pull fails with an auth error.

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

## Fronting with a reverse proxy (TLS)

The services speak plain HTTP, so put them behind a proxy that terminates
TLS rather than exposing 8765/8766 directly. With nginx-proxy-manager,
create one proxy host per service:

| Proxy host | Forward to | Purpose |
|------------|-----------|---------|
| `unifi-mcp.<your-domain>` | `<nas-ip>` : `8765` | MCP endpoint |
| `unifi-mcp-admin.<your-domain>` | `<nas-ip>` : `8766` | Token admin UI |

Request a certificate for each, and enable **Force SSL**.

**Critical for the MCP host:** the Streamable HTTP transport streams
responses as Server-Sent Events. nginx buffers proxied responses by default,
which makes an MCP client hang waiting for data that is sitting in the
proxy's buffer. In the proxy host's **Advanced** tab, add:

```nginx
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
chunked_transfer_encoding on;
```

Without `proxy_buffering off`, the endpoint appears to connect and then
stall — the request never visibly fails, which makes it easy to misdiagnose
as an auth or client problem.

The admin UI needs no special settings; it is ordinary form-post HTML.

Once proxied, clients use the HTTPS URL:

```json
{
  "mcpServers": {
    "unifi": {
      "url": "https://unifi-mcp.<your-domain>/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Verify the proxied path end to end, not just the direct one:

```bash
curl https://unifi-mcp.<your-domain>/healthz     # expect: ok
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  https://unifi-mcp.<your-domain>/mcp            # expect: 401
```

## Security notes

- **The services themselves speak plain HTTP.** TLS is an explicit non-goal
  of the current design (see
  `docs/superpowers/specs/2026-07-13-http-transport-design.md`) — it is
  expected to come from a reverse proxy in front. Until you have one, admin
  passwords and freshly minted tokens cross the LAN in cleartext. Never
  port-forward 8765/8766 from the internet; expose only the proxied HTTPS
  hosts.
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

**MCP client connects but then hangs with no response** — a reverse proxy is
buffering the SSE stream. Set `proxy_buffering off` on the proxy host (see
"Fronting with a reverse proxy"). Confirm by testing the NAS directly on
`http://<nas-ip>:8765/mcp`: if that works and the proxied URL hangs, the
proxy is the cause.
