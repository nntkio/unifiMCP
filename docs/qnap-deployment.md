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

Built and pushed from a workstation, not the NAS, with the script in
`scripts/`:

```bash
# Multi-arch (linux/amd64 + linux/arm64) so one tag works on x86_64 and ARM
# QNAP models. Pushes :latest, :<version from pyproject.toml>, :sha-<git sha>.
scripts/publish-image.sh

# Add one more tag on top of those, e.g. a release candidate
scripts/publish-image.sh rc1

# Build for this machine only and load it into local docker, without pushing,
# to run the container before publishing
scripts/publish-image.sh --local
```

It needs Docker with buildx, and the `gh` CLI logged in with a token that
carries `write:packages` (`gh auth refresh -s write:packages` adds it). Set
`GHCR_TOKEN` and `GHCR_USER` instead to use a dedicated PAT, or `IMAGE` and
`PLATFORMS` to publish elsewhere. If your default buildx builder cannot do
both platforms the script creates one called `unifi-mcp-multiarch` and uses
it just for this build.

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
revoke any single token, reset a user's password (a dialog asks for the new
temporary password; the user's tokens keep working), or delete a user
(which removes the account and all of its tokens).

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

## Publishing the MCP endpoint with a Cloudflare Tunnel

The reverse proxy above serves the LAN. Claude custom connectors need more
than that: the connection is made from Anthropic's servers, so the endpoint
must be reachable over public HTTPS. A Cloudflare Tunnel does that without
opening a single inbound port — `cloudflared` dials out to Cloudflare and
traffic comes back down that connection.

Only the MCP service is published. The admin UI on 8766 stays on the LAN.

### 1. Create the tunnel

In the Cloudflare Zero Trust dashboard, go to **Networks → Tunnels → Create
a tunnel**, choose **Cloudflared**, name it `unifi-mcp`, and copy the
connector token it shows.

### 2. Run the connector next to the MCP service

Put the token in `qnap.env`:

```bash
CLOUDFLARE_TUNNEL_TOKEN=<the token you just copied>
MCP_PUBLIC_URL=https://unifi-mcp.seeg.io
```

`deploy/docker-compose.qnap.yml` already carries the `cloudflared` service.
Bring it up:

```bash
docker compose -f docker-compose.qnap.yml --env-file qnap.env up -d
```

`MCP_PUBLIC_URL` is what turns on the OAuth endpoints. It must be the bare
origin — scheme and host, no path — and must match the URL entered in Claude
minus `/mcp`. An invalid value stops the service at startup with a message
saying so, rather than serving broken metadata.

### 3. Publish the hostname

In the tunnel's **Routes** tab, select **Add route → Published application**:

| Field | Value |
|-------|-------|
| Subdomain | `unifi-mcp` |
| Domain | `seeg.io` |
| Path | leave empty |
| Service type | `HTTP` |
| URL | `unifi-mcp:8765` |

The URL is the compose service name: `cloudflared` shares the default
network with the MCP container, so it reaches it directly and the NAS never
exposes the port publicly.

Cloudflare creates a proxied CNAME for the hostname. **Delete any existing
record for that name in the zone first** — the tunnel will not overwrite
one. If your LAN resolver has its own override pointing the same name at
nginx-proxy-manager, leave it: LAN clients keep the direct route, and both
paths present the same hostname, so the OAuth metadata is identical either
way.

### 4. Verify from outside the LAN

Run these from a network that is not your LAN, such as a phone on cellular:

```bash
curl -si https://unifi-mcp.seeg.io/healthz                     # 200, body "ok"
curl -si -X POST https://unifi-mcp.seeg.io/mcp | head -20      # 401 + WWW-Authenticate
curl -s https://unifi-mcp.seeg.io/.well-known/oauth-protected-resource/mcp
curl -s https://unifi-mcp.seeg.io/.well-known/oauth-authorization-server
curl -si https://unifi-mcp-admin.seeg.io/login                 # must NOT be reachable
```

The 401 must carry a `WWW-Authenticate: Bearer resource_metadata="..."`
header — that pointer is how Claude discovers the authorization server. The
protected-resource document's `resource` field must equal
`https://unifi-mcp.seeg.io/mcp` exactly, character for character, including
the path. If it does not match the URL typed into Claude, the connector
fails to attach with no useful error.

### Restricting who can reach it

Two mechanisms are worth keeping apart, because **bypass** means something
specific in Cloudflare.

**Cloudflare Access with a Bypass policy** puts an identity check in front
of the hostname. Anthropic's servers cannot complete an interactive login,
so they need a **Bypass** policy — Access's term for letting traffic through
without enforcement. Go to **Zero Trust → Access controls → Applications →
Create new application → Self-hosted and private → Add public hostname**,
select the `unifi-mcp` hostname, and attach two policies:

| Order | Action | Selector | Value |
|-------|--------|----------|-------|
| 1 | Bypass | IP ranges | Anthropic's egress range, `160.79.104.0/21` |
| 2 | Allow | Emails | your own address |

Access evaluates Service Auth first, then Bypass, then Block and Allow, so
the Bypass is what keeps `/mcp`, `/token`, `/register`, and the metadata
documents reachable. The Allow policy matters just as much: the sign-in page
is opened by **your browser**, which is not in Anthropic's range, so without
it you could never complete a connector sign-in. Note Cloudflare's own
caveat that a Bypass policy "does not enforce any Access security controls
and requests are not logged" — the OAuth layer is still doing the real
authentication underneath, so this is defence in depth rather than the
primary control.

**A WAF custom rule** is the lighter alternative if you would rather not put
Access in the path at all. Under **Security → WAF → Custom rules**, create a
rule with action **Block**:

```
(http.host eq "unifi-mcp.seeg.io"
  and not ip.src in {160.79.104.0/21}
  and not http.request.uri.path in {"/authorize" "/oauth/login"})
```

The two path exceptions exist for the same reason as the Allow policy above.

Check Anthropic's published egress range before relying on either form; if
it changes, this is what breaks. Skipping both is defensible, since every
path still requires a valid token or a valid login.

**One Cloudflare setting can break the connector outright: Bot Fight Mode.**
It challenges clients it thinks are automated, and server-to-server requests
from Anthropic look exactly like that. Cloudflare's documentation is explicit
that "you cannot bypass or skip Bot Fight Mode using WAF custom rules or Page
Rules", and that it runs "in a separate evaluation pipeline where *Skip*,
*Bypass*, and *Allow* actions have no effect". If it is enabled on the zone,
turn it off or move to Super Bot Fight Mode, which does support exceptions.
The symptom is a connector that never completes its first request, with
nothing useful in any log.

### What the OAuth endpoints add

With `MCP_PUBLIC_URL` set, the MCP service serves these alongside `/mcp`:

| Path | Purpose |
|------|---------|
| `/.well-known/oauth-protected-resource[/mcp]` | Tells a client which authorization server protects this endpoint |
| `/.well-known/oauth-authorization-server` | Endpoint discovery, advertising S256 PKCE |
| `/register` | Dynamic client registration (RFC 7591) |
| `/authorize` | Starts a sign-in; redirects the browser to `/oauth/login` |
| `/oauth/login` | The sign-in and consent page, served by this service |
| `/token` | Authorization-code and refresh-token exchange |
| `/revoke` | Token revocation (RFC 7009) |

None of them require a bearer token, by design. `/mcp` still does.

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
