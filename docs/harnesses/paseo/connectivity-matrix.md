# Paseo Fleet Connectivity Matrix: Relay E2EE vs Internal DRG DNS

## 1. Dual Transport Model

To ensure universal reachability without triggering browser security constraints (such as W3C Mixed Content blocking `ws://` on `https://` origins), the ATIUS Paseo harness utilizes a dual-transport model:

1. **Relay E2EE:** Used for browser Web UI and external clients. All packets are encrypted with Curve25519/TweetNaCl keypairs before traversing `relay.paseo.sh:443`.
2. **Internal OCI DRG:** Used for high-speed, direct backend communication between daemons and agents over internal DNS (`atius-srv-X.atius.internal`).

## 2. Server Identifiers and Connection URIs

| Server | OCI DRG IP | Daemon Port | Server ID | Public Key (Base64) | Internal DRG URI | Public Relay URI |
|---|---|---|---|---|---|---|
| `atius-srv-1` | `10.1.0.11` | `37815` | `srv_jZvEHFirGmhi` | `RKCv1HZkaVEDKV7HH62lHfhQ8XDLQfou6pj9WRJfP0I=` | `tcp://atius-srv-1.atius.internal:37815` | `relay://relay.paseo.sh:443/srv_jZvEHFirGmhi?key=RKCv1HZkaVEDKV7HH62lHfhQ8XDLQfou6pj9WRJfP0I%3D&ssl=true` |
| `atius-srv-2` | `10.12.1.12` | `37825` | `srv_iwPCODMrLTYZ` | `cCSZ8W40TGd1T+LlxKFidMsXnboCTOAY7g2alGIuj2Y=` | `tcp://atius-srv-2.atius.internal:37825` | `relay://relay.paseo.sh:443/srv_iwPCODMrLTYZ?key=cCSZ8W40TGd1T%2BLlxKFidMsXnboCTOAY7g2alGIuj2Y%3D&ssl=true` |
| `atius-srv-3` | `10.13.1.13` | `37835` | `srv_e5EPqrS7hl33` | `bFCAn5zjycHy86FbX6BSnalkaJ/8hmaJGqVTHwr2EXw=` | `tcp://atius-srv-3.atius.internal:37835` | `relay://relay.paseo.sh:443/srv_e5EPqrS7hl33?key=bFCAn5zjycHy86FbX6BSnalkaJ%2F8hmaJGqVTHwr2EXw%3D&ssl=true` |
| `atius-srv-4` | `10.14.1.14` | `37845` | `srv_1hdoSOERpnYd` | `u0DICauNdisk9twEz5/9jneascC3vy/EilAZ3C0olDw=` | `tcp://atius-srv-4.atius.internal:37845` | `relay://relay.paseo.sh:443/srv_1hdoSOERpnYd?key=u0DICauNdisk9twEz5%2F9jneascC3vy%2FEilAZ3C0olDw%3D&ssl=true` |
