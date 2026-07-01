# Landscape self-hosted preflight

**Date:** 2026-06-25
**Context:** `landscape.atius.com.br` currently serves a reserved placeholder on `atius-srv-1`.

## Current endpoint state

- DNS: `landscape.atius.com.br -> 137.131.190.161` (`atius-srv-1`).
- Apache: explicit vhost exists on `atius-srv-1`.
- TLS: Let's Encrypt certificate exists for `landscape.atius.com.br`.
- Backend: placeholder only; Landscape Server is not installed.

## Canonical packaging finding

Checked Launchpad PPA indices for Ubuntu Noble packages:

| PPA | Arch | `landscape-server` | `landscape-server-quickstart` | Assessment |
| --- | --- | --- | --- | --- |
| `ppa:landscape/self-hosted-26.04` | arm64 | missing | missing | Cannot install 26.04 server package on current ARM64 fleet from versioned PPA. |
| `ppa:landscape/self-hosted-26.04` | amd64 | present | present | Viable for a new AMD64 app server. |
| `ppa:landscape/self-hosted-24.04` | arm64 | present | present | Viable LTS option on current ARM64 hosts. |
| `ppa:landscape/latest-stable` | arm64 | present | present | Viable technically, but rolling/stable channel is not preferred for production governance. |

Canonical docs say production manual install should use the versioned LTS PPA pattern (`ppa:landscape/self-hosted-<VERSION>`) and recommend manual deployment with at least an application server and database server. Quickstart is for smaller/non-large-scale deployments.

## Host fit

| Host | Fit | Notes |
| --- | --- | --- |
| `atius-srv-1` | poor | Already runs dense Apache reverse proxy, K3s control-plane, PostgreSQL, high disk usage around 86%. Installing Landscape here risks Apache/PostgreSQL collisions. |
| `horistic-srv` | better | Lower disk/memory pressure and already intended as edge/reverse-proxy host, but would need DNS move/proxy update and careful Apache ownership. |
| new AMD64 VM | best for 26.04 | Required if the hard target is Landscape 26.04 LTS server packages from versioned PPA. |

## Recommendation

For immediate self-hosted on current OCI ARM64 fleet: install Landscape 24.04 LTS on `horistic-srv`, then move or proxy `landscape.atius.com.br` there.

For strict 26.04 LTS: provision a new AMD64 app server and use `ppa:landscape/self-hosted-26.04`.

## Not executed

No Landscape Server packages were installed in this preflight. No DNS was changed. No Apache vhost was replaced.
