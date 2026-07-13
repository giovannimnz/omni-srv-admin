# RDP Trust PKI

Canonical trust model for the Windows `mstsc` client and the Ubuntu ARM64
XRDP fleet.

Managed scope:

- `atius-srv-1`
- `atius-srv-2`
- `atius-srv-3`
- `horistic-srv`
- `GIOVANNI-W11-PC`

## Goal

Eliminate the two distinct trust problems in Remote Desktop:

1. `.rdp` files opened on Windows must be signed by a trusted publisher.
2. XRDP servers must present a TLS certificate whose issuer is trusted by the
   Windows client and whose SAN matches the target that the user actually uses
   in `full address:s:`.

## Windows side

The Windows client trusts:

- Root CA subject: `CN=ATIUS RDP Fleet Root CA, OU=Infra, O=ATIUS, L=SaoPaulo, S=SP, C=BR`
- RDP publisher subject: `CN=ATIUS RDP Publisher, OU=Infra, O=ATIUS, L=SaoPaulo, S=SP, C=BR`

Current-user trust stores:

- `Cert:\CurrentUser\Root`
- `Cert:\CurrentUser\TrustedPublisher`
- `Cert:\CurrentUser\My`

Current-user policy:

```text
HKCU\Software\Policies\Microsoft\Windows NT\Terminal Services
  AllowSignedFiles=1
  TrustedCertThumbprints=<SHA1 thumbprint of ATIUS RDP Publisher>
```

Desktop `.rdp` files that must stay signed:

- `C:\Users\muniz\Desktop\ATIUS-SRV-1.rdp`
- `C:\Users\muniz\Desktop\ATIUS-SRV-2.rdp`
- `C:\Users\muniz\Desktop\ATIUS-SRV-3.rdp`
- `C:\Users\muniz\Desktop\HORISTIC-SRV.rdp`

Expected markers in each file:

```text
signscope:s:...
signature:s:...
```

## XRDP side

Each host must use an explicit XRDP certificate and key, not Ubuntu
`snakeoil`.

Revocation and issuer retrieval are served from the trusted public endpoint:

```text
https://landscape.atius.com.br/rdp-pki/atius-rdp-fleet-root.crl.pem
https://landscape.atius.com.br/rdp-pki/atius-rdp-fleet-root-ca.crt.pem
```

Live paths:

```text
/etc/xrdp/atius-rdp/server.crt.pem
/etc/xrdp/atius-rdp/server.key.pem
```

Expected permissions:

```text
/etc/xrdp/atius-rdp               root:xrdp 750
/etc/xrdp/atius-rdp/server.crt.pem root:root 644
/etc/xrdp/atius-rdp/server.key.pem root:xrdp 640
```

`/etc/xrdp/xrdp.ini` must point to:

```text
certificate=/etc/xrdp/atius-rdp/server.crt.pem
key_file=/etc/xrdp/atius-rdp/server.key.pem
```

Each leaf certificate must include SAN entries for the addresses actually used
 by the operator:

- `atius-srv-1`: `137.131.190.161`, `10.100.100.1`, legacy `10.1.1.1`, `atius-srv-1`, `srv1`, `atius`, `atius-srv-1.atius.internal`
- `atius-srv-2`: `129.148.47.32`, `10.100.100.2`, legacy `10.1.1.2`, `atius-srv-2`, `srv2`, `zentrius`
- `atius-srv-3`: `136.248.126.12`, `10.100.100.3`, legacy `10.1.1.3`, legacy `10.1.1.7`, `atius-srv-3`, `srv3`, `atius-srv-3.atius.internal`
- `horistic-srv`: `163.176.232.119`, `10.100.100.4`, legacy `10.1.1.4`, `100.102.126.61`, `horistic-srv`, `horistic-srv-1`, `horistic`

2026-07-10 note: OCI/DRG private networking is the primary server-to-server
plane where validated. `10.100.100.0/24` / `wg100` is reserve/fallback and
break-glass for clients such as W11/S23. Keep `10.1.1.x` SANs only until all
RDP entrypoints and shortcuts stop using the old `wg0` addresses.

## Verification

Windows:

```powershell
Get-ChildItem Cert:\CurrentUser\Root |
  Where-Object Subject -like '*ATIUS RDP Fleet Root CA*'

Get-ChildItem Cert:\CurrentUser\TrustedPublisher |
  Where-Object Subject -like '*ATIUS RDP Publisher*'

reg query "HKCU\Software\Policies\Microsoft\Windows NT\Terminal Services"

rg -n "^(signscope|signature):" `
  C:\Users\muniz\Desktop\ATIUS-SRV-1.rdp `
  C:\Users\muniz\Desktop\ATIUS-SRV-2.rdp `
  C:\Users\muniz\Desktop\ATIUS-SRV-3.rdp `
  C:\Users\muniz\Desktop\HORISTIC-SRV.rdp
```

Linux:

```bash
grep -En '^(certificate|key_file|security_layer|ssl_protocols)=' /etc/xrdp/xrdp.ini
sudo -u xrdp test -r /etc/xrdp/atius-rdp/server.crt.pem
sudo -u xrdp test -r /etc/xrdp/atius-rdp/server.key.pem
sudo openssl x509 -in /etc/xrdp/atius-rdp/server.crt.pem -noout -subject -issuer -fingerprint -sha256 -dates
sudo openssl x509 -in /etc/xrdp/atius-rdp/server.crt.pem -noout -ext subjectAltName
sudo systemctl is-active xrdp xrdp-sesman
```

Windows revocation check:

```powershell
certutil -user -urlfetch -verify C:\Users\muniz\.local\share\rdp-fleet-pki\atius-srv-1-v4.crt.pem
certutil -user -urlfetch -verify C:\Users\muniz\.local\share\rdp-fleet-pki\rdp-signing-v4.crt.pem
```

Expected result:

- AIA fetched from `https://landscape.atius.com.br/rdp-pki/atius-rdp-fleet-root-ca.crt.pem`
- CDP fetched from `https://landscape.atius.com.br/rdp-pki/atius-rdp-fleet-root.crl.pem`
- `Verificação de revogação de certificado secundário aprovada.`

## Operational rules

- Keep the private CA and signing material outside Git.
- Re-sign the four Desktop `.rdp` files after any content change that touches a
  signed field.
- Reissue the matching XRDP leaf if a public IP, VPN IP, or canonical alias
  changes.
- If the `landscape.atius.com.br` vhost is replaced, keep the `/rdp-pki/`
  static path alive before rotating this PKI.
- Use the signed Desktop `.rdp` files as the default operator entrypoint on
  Windows. Creating a fresh unsigned `.rdp` or manually targeting a name/IP
  outside the SAN set can still produce a trust prompt.
