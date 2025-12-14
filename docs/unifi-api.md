# UniFi Local Controller API Documentation

This document covers the local UniFi gateway API for self-hosted controllers and UniFi OS devices (not the cloud-based API).

## Authentication

### Standard Controller (port 8443)

```http
POST /api/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password",
  "remember": true
}
```

### UniFi OS Devices (UDM/UDM Pro/UCG Max - port 443)

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

### Session Verification

```http
GET /api/self
```

### Logout

```http
POST /api/logout
```

**Important:** For UniFi OS devices, all API endpoints must be prefixed with `/proxy/network`

Example: `https://192.168.1.1/proxy/network/api/s/default/stat/sta`

## Response Format

All API responses follow this structure:

```json
{
  "meta": {
    "rc": "ok"
  },
  "data": [...]
}
```

Error response:

```json
{
  "meta": {
    "rc": "error",
    "msg": "api.err.LoginRequired"
  },
  "data": []
}
```

## Port Reference

| Controller Type | Port |
|-----------------|------|
| Software/Self-hosted | 8443 |
| UniFi OS Console (UDM, UDM Pro, etc.) | 443 |
| UniFi OS Server | 11443 |

## API Endpoints

All endpoints are prefixed with `/api/s/{site}/` where `{site}` is typically `default`.

### Device Management

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| List Devices | GET | `/api/s/{site}/stat/device` | Retrieve all network devices |
| Device Details | GET | `/api/s/{site}/stat/device/{mac}` | Get specific device information |
| Device Basic Info | GET | `/api/s/{site}/stat/device-basic` | Get mac and type only |
| Device Stats | GET | `/api/s/{site}/stat/device/{mac}/stats` | Obtain performance metrics |
| Restart Device | POST | `/api/s/{site}/cmd/devmgr` | Reboot specific device |
| Upgrade Firmware | POST | `/api/s/{site}/cmd/devmgr` | Update device firmware |

#### Restart Device Example

```http
POST /api/s/{site}/cmd/devmgr
Content-Type: application/json

{
  "cmd": "restart",
  "mac": "00:11:22:33:44:55"
}
```

### Client Management

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| Active Clients | GET | `/api/s/{site}/stat/sta` | List currently connected clients |
| All Clients | GET | `/api/s/{site}/stat/alluser` | Historical client list |
| Client Details | GET | `/api/s/{site}/stat/user/{mac}` | Individual client information |
| Block Client | POST | `/api/s/{site}/cmd/stamgr` | Deny network access |
| Unblock Client | POST | `/api/s/{site}/cmd/stamgr` | Restore access |
| Disconnect Client | POST | `/api/s/{site}/cmd/stamgr` | Force disconnection |

#### Block Client Example

```http
POST /api/s/{site}/cmd/stamgr
Content-Type: application/json

{
  "cmd": "block-sta",
  "mac": "00:11:22:33:44:55"
}
```

#### Unblock Client Example

```http
POST /api/s/{site}/cmd/stamgr
Content-Type: application/json

{
  "cmd": "unblock-sta",
  "mac": "00:11:22:33:44:55"
}
```

#### Disconnect Client Example

```http
POST /api/s/{site}/cmd/stamgr
Content-Type: application/json

{
  "cmd": "kick-sta",
  "mac": "00:11:22:33:44:55"
}
```

### Network Configuration

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| List Networks | GET | `/api/s/{site}/rest/networkconf` | Get all networks |
| Create Network | POST | `/api/s/{site}/rest/networkconf` | Add new network |
| Update Network | PUT | `/api/s/{site}/rest/networkconf/{id}` | Modify network |
| Delete Network | DELETE | `/api/s/{site}/rest/networkconf/{id}` | Remove network |

### Firewall Rules

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| List Rules | GET | `/api/s/{site}/rest/firewallrule` | Get all firewall rules |
| Create Rule | POST | `/api/s/{site}/rest/firewallrule` | Add new rule |
| Update Rule | PUT | `/api/s/{site}/rest/firewallrule/{id}` | Modify rule |
| Delete Rule | DELETE | `/api/s/{site}/rest/firewallrule/{id}` | Remove rule |

### Routing

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| List Routes | GET | `/api/s/{site}/rest/routing` | Get all routes |
| Create Route | POST | `/api/s/{site}/rest/routing` | Add new route |

### Site Management

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| List Sites | GET | `/api/self/sites` | Access all sites |
| Site Health | GET | `/api/s/{site}/stat/health` | Get health metrics |
| Create Site | POST | `/api/s/default/cmd/sitemgr` | New site creation |
| Delete Site | POST | `/api/s/default/cmd/sitemgr` | Remove site |

### Statistics & Monitoring

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| Dashboard Health | GET | `/api/s/{site}/stat/health` | Overall health status |
| DPI Stats | GET | `/api/s/{site}/stat/dpi` | Deep packet inspection stats |
| Client DPI | GET | `/api/s/{site}/stat/stadpi` | Per-client DPI stats |
| Gateway Stats | GET | `/api/s/{site}/stat/gateway` | Gateway statistics |
| Daily Report | GET | `/api/s/{site}/stat/report/daily.site` | Daily site report |
| Current Channels | GET | `/api/s/{site}/stat/current-channel` | Available WiFi channels |

### Traffic Rules

| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| Set User Access | POST | `/api/s/{site}/rest/user/{client_id}` | Set client access |
| Bandwidth Limits | POST | `/api/s/{site}/rest/trafficrule` | Set bandwidth rules |

## Query Parameters

| Parameter | Function | Example |
|-----------|----------|---------|
| `_limit` | Limit number of results | `?_limit=50` |
| `_start` | Offset for pagination | `?_start=50` |
| `mac` | Filter by MAC address | `?mac=001122334455` |
| `ip` | Filter by IP address | `?ip=192.168.1.100` |
| `within` | Timeframe in seconds | `?within=86400` |
| `attrs` | Select specific attributes | `?attrs=mac,hostname,ip` |

## WebSocket Events

For real-time updates, connect to the WebSocket endpoint:

```
wss://{controller}/wss/s/{site}/events
```

### Event Types

| Event | Description |
|-------|-------------|
| `sta:sync` | Client updates |
| `device:sync` | Device changes |
| `alarm` | Alarm triggered |
| `speedtest:done` | Speed test completed |
| `backup:done` | Backup completed |
| `notification` | General notification |

## Notes

- MAC addresses should be lowercase, typically without separators (e.g., `001122334455`)
- The API is session-based with cookie persistence
- For UniFi OS devices (UDM, UDM Pro, UCG Max), prefix all endpoints with `/proxy/network`
- Supported controller versions: 5.x through 10.x
- Supported UniFi OS versions: 3.x through 5.x

## References

- [UniFi Best Practices API Guide](https://github.com/uchkunrakhimow/unifi-best-practices)
- [Art-of-WiFi/UniFi-API-client](https://github.com/Art-of-WiFi/UniFi-API-client)
- [Ubiquiti Community Wiki](https://ubntwiki.com/products/software/unifi-controller/api)
- [unificontrol Python library](https://unificontrol.readthedocs.io/en/latest/introduction.html)
