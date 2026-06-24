---
phase: 27
title: "Research - Horistic Remote Apache, Rename Drift and Webhook Safety"
date: 2026-06-24
status: complete
requirements:
  - PRG-08
  - PRG-09
  - PRG-10
  - PRG-11
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 27 Research

## Finding 1: Horistic runtime and proxy are split across hosts

Backend/frontend/webhooks run on `atius-srv-1`; Apache vhosts live on
`horistic-srv`. Local SRV-1 PM2 checks can pass while public Horistic sites fail
if remote Apache is broken.

Plan implication:

- Model Horistic runtime and proxy as separate guard sections.

## Finding 2: Apache unit drift caused a real outage

The broken custom unit called `apache2 -k start` directly and failed on boot.
The guard must check:

- fragment path is package default where expected;
- no unexpected drop-ins;
- service enabled/active;
- `apache2ctl -S` works;
- `sites-enabled` contains expected vhosts;
- ports 80/443 listen on remote host.

## Finding 3: Rename drift needs classification

Rename refs are not all equal. The detector should classify:

- stale benign docs refs;
- active PM2 cwd/script refs;
- active Apache vhost/proxy refs;
- GDrive/backup paths;
- inventory/DB/manifest refs;
- missing target folders or symlinks.

Plan implication:

- Output drift findings with severity, evidence path, suggested fix and apply
  gate, but no automatic rename.

## Finding 4: Webhook validation can cause side effects

Real POSTs to `webhook.horistic.com/{divap,forex,scalp}` can send Telegram
messages and forward to ATS. Health checks must use GET/HEAD unless an operator
explicitly authorizes a real fire-drill.

Plan implication:

- Add a no-POST scanner/test and encode endpoint methods in config.
- Reference Horistic scalp behavior as a contract, but do not test it with live
  POST from `omni-srv-admin`.
