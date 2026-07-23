---
phase: 26
title: "Research - Production Guard Boot/Login Protocol"
date: 2026-06-24
status: complete
requirements:
  - PRG-07
  - PRG-10
context_budget_target: "75k-95k tokens"
execution_model_target: "gpt-5.3-codex-spark"
---

# Phase 26 Research

## Finding 1: Boot checks need to survive stuck user targets

Prior resource-governor work found user `default.target` could be stuck. The
protocol should prefer robust targets/timers and document how to inspect failures
without killing live sessions.

## Finding 2: Login checks must not degrade RDP

The operator cares about RDP/XRDP continuity. Login/session checks must be
lightweight, non-blocking and explicit about whether they can flicker or affect
the desktop. Default behavior: no RDP restart and no session kill.

## Finding 3: Verification units should be static until approved

Planning and file validation can happen in git. Live `systemctl --user enable`
or install should be a gate, because this is production.

## Plan Implication

Create versioned units/timers and a runbook, validate them with
`systemd-analyze verify --user`, and run `$gsd-verify-work 26` after automated
checks.
