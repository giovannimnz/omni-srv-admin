---
spike: 004
name: plaintext-transport-negative-gate
type: standard
validates: "Disabling SSH encryption or adopting HPN NoneSwitch materially improves interactive command latency on the ATIUS DRG"
verdict: INVALIDATED
related: [48]
tags: [ssh, security, hpn, latency]
---

# Spike 004: Plaintext Transport Negative Gate

## What This Validates

This spike tests the original hypothesis that trusted OCI/DRG peers should use
an unencrypted terminal transport to reach extreme interactive speed.

## Research

- RFC 4253 defines the SSH `none` cipher as optional, without confidentiality
  and explicitly not recommended. Current upstream OpenSSH does not expose it
  as a negotiable cipher.
- HPN-SSH is a downstream throughput patch for long, high-bandwidth paths. Its
  own documentation says NoneSwitch cannot be used for an interactive shell
  and is intended for bulk transfers such as `scp`.
- A private DRG reduces exposure but does not remove compromised-peer, lateral
  capture, routing-error or credential-output risk. Interactive sessions can
  carry commands, source, tokens and forwarded traffic.

Primary references:

- https://www.rfc-editor.org/info/rfc4253/
- https://man.openbsd.org/ssh_config
- https://www.psc.edu/hpn-ssh-home/hpn-ssh-faq/
- https://www.psc.edu/hpn-ssh-home/hpn-readme/

## Investigation Trail

- The srv-3 OpenSSH 9.6p1 client did not advertise `none` through
  `ssh -Q cipher`.
- OCI/DRG RTT from srv-3 was about 0.52-0.55 ms, far below the observed cold
  SSH setup cost.
- A cold direct-DRG master opened in about 158-159 ms. Reusing that master
  reduced small commands to about 14-18 ms.
- With the same persistent-master conditions, ChaCha20-Poly1305 and
  AES128-GCM both produced approximately 13-14 ms samples. Changing modern
  ciphers did not materially change interactive startup.
- The current latency root cause is repeated setup/authentication plus
  SSSD/GSSAPI/multiple-identity processing, not symmetric encryption per
  packet.

## Results

Verdict: INVALIDATED.

Do not deploy a plaintext shell, patch OpenSSH for `none`, or install HPN-SSH
for this workflow. HPN NoneSwitch cannot satisfy the interactive requirement,
and the measured cipher comparison gives no performance case for sacrificing
confidentiality.

The accepted optimization boundary is:

- upstream encrypted OpenSSH with modern AEAD defaults;
- canonical OCI/DRG FQDNs and fail-closed host-key verification;
- one managed identity per host path;
- persistent connection/channel reuse;
- owner-local execution to avoid NFS metadata work for heavy development
  operations.

Any future alternative transport must remain authenticated, confidential,
integrity-protected, benchmark faster than the multiplexed baseline, support an
interactive terminal and have a reversible fleet rollout. Plain TCP, Telnet,
rsh and HPN NoneSwitch fail that gate.
