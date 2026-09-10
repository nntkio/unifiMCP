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

## 3. Start the services and verify directly

Verify against the NAS directly **before** putting a proxy in front. If you
only ever test the proxied URL, a failure leaves you unable to tell whether
the container or the proxy is at fault.

If you deployed from a shell rather than the Container Station UI:

```bash
docker compose -f docker-compose.qnap.yml --env-file qnap.env pull
docker compose -f docker-compose.qnap.yml --env-file qnap.env up -d
```

Set the NAS address once so the commands below can be pasted as-is:

```bash
NAS=172.16.25.50
```

### 3.1 Health check (unauthenticated by design)

```bash
curl -i http://$NAS:8765/healthz
```

Expect `HTTP/1.1 200 OK` and a body of `ok`. This endpoint has no auth so
the Docker healthcheck can use it.

| What you see | Meaning |
|--------------|---------|
| `200` + `ok` | Transport is up |
| `Connection refused` | Container not running, or the port isn't published |
| Hangs, then nothing | Firewall between you and the NAS |

If it's refused, check the container is actually running and did not
crash-loop — in Container Station, look at the container's logs rather than
just its status.

### 3.2 Confirm authentication is enforced

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://$NAS:8765/mcp
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://$NAS:8765/mcp \
  -H 'Authorization: Bearer not-a-real-token'
```

Both must print `401`. Anything else means the bearer check isn't running —
stop and investigate before going further, because the MCP tools can restart
devices and rewrite firewall rules.

### 3.3 Admin UI reachable

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://$NAS:8766/login
```

Expect `200`.

### 3.4 Mint a token, then prove a real MCP call works

Follow section 4 to create a token, then:

```bash
TOKEN='<paste the token>'

curl -sS -X POST http://$NAS:8765/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

Expect an SSE frame containing `"serverInfo":{"name":"unifi-mcp"`.

All three headers matter. The `Accept` header must list **both**
`application/json` and `text/event-stream`; omit either and the MCP SDK
rejects the request with `406 Not Acceptable`, which is easy to misread as
an auth failure.

## 4. Mint a bearer token

1. Open `http://<nas-ip>:8766/login` and log in as `root` with
   `ROOT_ADMIN_PASSWORD`.
2. On `/admin`, create an account for each person who needs access, with a
   temporary password.
3. Log out, then log back in as that account. You land on `/tokens`.
4. Create a token with a label and an expiry. **It is displayed exactly
   once** — only its SHA-256 hash is stored, so copy it immediately.

Root cannot create tokens for itself; it only provisions accounts. From
`/admin` root sees every account with its tokens grouped underneath, can
revoke any single token, or delete a user (which removes the account and
all of its tokens).

### 4.1 Watch who is calling

`http://<nas-ip>:8766/admin/usage` (root only) lists every JSON-RPC message
the MCP service accepted: time (UTC), user, token label, client IP,
`X-Forwarded-For`, method, tool, HTTP status, and duration. Every column has
a filter, so you can answer "which tools did `alice` call from
`203.0.113.7` this week" in a couple of clicks. The log lives in the same
`tokens.db` volume as the accounts, so nothing extra needs mounting or
backing up.

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

The services speak plain HTTP, so terminate TLS in a proxy rather than
exposing 8765/8766 directly. These steps use nginx-proxy-manager; the same
directives apply to any nginx.

Create **two** proxy hosts:

| Proxy host | Forward to | Advanced config needed |
|------------|-----------|------------------------|
| `unifi-mcp.seeg.io` | `172.16.25.50` : `8765` | Yes — see below |
| `unifi-mcp-admin.seeg.io` | `172.16.25.50` : `8766` | No |

### DNS records and certificate issuance

Point both names at the **reverse proxy**, not at the NAS:

| Record | Value |
|--------|-------|
| `unifi-mcp.seeg.io` | the proxy host's IP (e.g. `172.16.25.190`) |
| `unifi-mcp-admin.seeg.io` | the proxy host's IP |

If the proxy sits on a private address, these must be **DNS-only** records
(in Cloudflare, the grey cloud — not the orange one). Cloudflare cannot
proxy traffic to an RFC1918 address, and turning proxying on for such a
record produces errors that look like proxy or certificate faults.

**A private IP forces a DNS-01 challenge.** Let's Encrypt validates HTTP-01
by connecting to the name from the public internet; if it resolves to
`172.16.x.x` — or resolves only on your internal network — that connection
cannot succeed, and issuance fails with a connection or timeout error that
is easy to misread as an nginx misconfiguration.

In nginx-proxy-manager's SSL tab, tick **Use a DNS Challenge**, choose the
provider hosting the zone, and supply an API token scoped to edit DNS for
that zone (for Cloudflare: `Zone:DNS:Edit` plus `Zone:Zone:Read`). This
never requires inbound reachability, so it works for a service published
only inside your network.

### Proxy host settings — MCP endpoint (8765)

**Details tab**

| Field | Value |
|-------|-------|
| Domain Names | `unifi-mcp.seeg.io` |
| Scheme | `http` |
| Forward Hostname / IP | your NAS IP |
| Forward Port | `8765` |
| Cache Assets | **off** |
| Block Common Exploits | on |
| Websockets Support | on |

Leave **Cache Assets off**. Caching a streaming response is precisely the
wrong behaviour and produces the same stall as buffering.

**SSL tab** — request a new certificate, then enable **Force SSL** and
**HTTP/2 Support**.

**Advanced tab** — paste:

```nginx
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
chunked_transfer_encoding on;
```

This is the step people miss. MCP Streamable HTTP returns Server-Sent
Events, and nginx buffers proxied responses by default — so the client
connects, then hangs with no error while the response sits in the proxy's
buffer. It looks like an auth or client bug, and neither the container log
nor the proxy log reports a failure.

The long timeouts matter separately: a streamed MCP session can stay open
far longer than nginx's 60-second default, which would otherwise cut
long-running tool calls off mid-flight.

Nginx Proxy Manager adds `X-Forwarded-For` on its own, which is what the
admin's Usage screen (section 4.1) reads for the IP column. Without it every
call would appear to come from the proxy's address, which is still recorded
separately as the direct peer.

### Proxy host settings — admin UI (8766)

Same Details and SSL settings with port `8766`. No Advanced config: the
admin UI is ordinary form-post HTML with no streaming.

### Re-verify through HTTPS

Repeat the direct checks against the proxied hostnames — the proxy is a new
component and inherits none of the guarantees you established in section 3.

```bash
MCPHOST=https://unifi-mcp.seeg.io

curl -i $MCPHOST/healthz
curl -s -o /dev/null -w '%{http_code}\n' -X POST $MCPHOST/mcp
```

Expect `200` + `ok`, then `401`.

Then the streaming check, which is the one that actually exercises the
buffering config:

```bash
time curl -sS -N -X POST $MCPHOST/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

Expect `"serverInfo":{"name":"unifi-mcp"` returning in roughly the same time
as the direct call in 3.4. A response that arrives only after a long delay,
or not at all, means buffering is still on — recheck the Advanced tab and
that Cache Assets is off.

**Always use the `https://` URL in clients, never `http://`.** With Force
SSL enabled, an `http://` request gets a 301 redirect, and an MCP client
that doesn't follow redirects on POST will fail against it.

Once proxied, point clients at the HTTPS URL:

```json
{
  "mcpServers": {
    "unifi": {
      "url": "https://unifi-mcp.seeg.io/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
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
