# AI Agent Harnesses Architecture & Fleet Directory

This directory centralizes operational and architectural documentation for AI Agent Runtimes (harnesses) managed across the ATIUS fleet.

## Available Harnesses

1. **[Paseo AI Agent Runtime](paseo/architecture.md)**
   - Multi-host distributed daemon cluster across `atius-srv-1..4`.
   - Dedicated ports `37815..37845`, OCI DRG low-latency private routing.
   - Dual-Domain Apache edge ingress (`paseo.atius.io` / `paseo.atius.com.br`) integrated with Atius Admin Edge SSO (`:8210`) in the canonical PM2 Model.
   - Dual-Transport connectivity: E2EE Relay for public/browser access and private OCI DRG for node-to-node streaming.

2. **Antigravity AI Agent**
   - Autonomous agent environment powered by Google DeepMind agentic tools.
   - Fleet-wide coordination, pre-CI validation gates, and headless automation.

3. **Codex Desktop & CLI**
   - Windows 11 / WSL native runtime with Zero-UI Task Scheduler automation.

4. **Hermes Runtime**
   - Upstream reference skills and subagent configurations in `~/.hermes/`.
