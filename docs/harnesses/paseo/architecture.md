# Paseo AI Agent Runtime — Fleet Architecture & Deployment

## 1. Executive Summary

The Paseo AI Agent Runtime (`@getpaseo/cli@0.14.0`, `@getpaseo/server@0.14.0`, `paseo-agy-acp@2.7.2`) is deployed as a distributed agent harness across the ATIUS fleet (`atius-srv-1..4`).

- **Central Hub:** `atius-srv-4` (`10.14.1.14:37845`).
- **Edge Ingress:** `atius-srv-1` (`10.1.0.11:443`).
- **Dual Domains:** `https://paseo.atius.io` & `https://paseo.atius.com.br`.
- **SSO Authentication:** Atius Admin Edge Gateway (`:8210`) following the canonical PM2 Model (Same-Host App-Local Login Shell).

## 2. Port and Host Topology

| Host | DRG Primary IP | Local Port | Role | Systemd Unit |
|---|---|:---:|---|---|
| `atius-srv-1` | `10.1.0.11` | `37815` | Local Node + Apache Edge Gateway | `paseo-daemon.service` |
| `atius-srv-2` | `10.12.1.12` | `37825` | Local Node / Compute Node | `paseo-daemon.service` |
| `atius-srv-3` | `10.13.1.13` | `37835` | Local Node / Control Host | `paseo-daemon.service` |
| `atius-srv-4` | `10.14.1.14` | `37845` | **Central Hub / Relay Target** | `paseo-daemon.service` |

## 3. Network Transport

- **Node-to-Node:** Private OCI DRG peering with sub-millisecond round-trip time (~0.6ms).
- **Public Ingress:** Apache TLS reverse proxy forwarding to local Atius Admin Edge Gateway (`127.0.0.1:8210`).
- **WebSockets:** Upgraded on `/ws` via Apache `RewriteCond %{HTTP:Upgrade} =websocket` and proxied to upstream daemon.
- **MCP Route:** Streamable HTTP JSON-RPC endpoint at `/mcp/agents`.
