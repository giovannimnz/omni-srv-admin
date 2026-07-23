---
phase: 14-resource-governor-pm2-boot-hardening
plan: 06
subsystem: k3s
tags: [jenkins, jenkins-agent, k3s, kubernetes-plugin, podman-runtime, m005]
requires:
  - phase: 13
    provides: "M005 live K3s HA cluster (SRV-1/2/7 Ready control-plane+etcd), Portainer CE 2.39.3 deployed"
  - phase: 14
    provides: "Phase 14 context, M006 resource-governor baseline, 14-05 Jenkins Podman cleanup complete"
provides:
  - "Jenkins agent Deployment (2 replicas) running in K3s HA cluster"
  - "JNLP registration over WireGuard wg0 (no public exposure)"
  - "Namespace `jenkins` with ResourceQuota, ServiceAccount, Secret"
  - "Foundation para Kubernetes plugin (next: install plugin + pod templates in controller)"
affects: [k3s-ha-portainer-oci, jenkins, srv1-ops, build-pipelines, m005-extensions]
tech-stack:
  added:
    - "jenkins/inbound-agent:latest (official JNLP agent, multi-arch)"
  patterns:
    - "Jenkins agent as K8s Deployment with explicit ResourceQuota"
    - "In-cluster service account + secret for JNLP registration"
    - "Secret stored in vault only, never in git"
key-files:
  created:
    - modules/k3s-ha-portainer-oci/jenkins/agent-deployment.yaml
    - /home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-15-jenkins-agent-k3s-secret.md
  modified:
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-PLAN.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md
    - .planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md
    - inventory/hosts/atius-srv-1.yaml
key-decisions:
  - "Use jenkins/inbound-agent:latest (multi-arch) instead of localhost/jenkins:podman-latest — K3s uses containerd, not podman; localhost images not resolvable from cluster"
  - "JNLP goes over wg0 (10.1.1.1:8085) — no public exposure, no Cloudflare hop"
  - "Secret generated with openssl rand -hex 32, stored in vault only, never committed"
  - "Static Deployment (2 replicas) for now; will move to Kubernetes plugin pod templates once plugin installed in controller"
patterns-established:
  - "M005 extension: K3s workloads that need CI access go through the Jenkins K8s plugin + Pod template"
  - "ResourceQuota at namespace level (4 CPU req, 8 CPU limit, 8Gi/16Gi mem, 20 pods)"
requirements-completed:
  - M005-JENKINS-PODMAN
  - M005-JENKINS-AGENT
duration: ~30 min
status: complete
---

# Phase 14 Plan 06: Jenkins agent on K3s (M005 extension) — Summary

**Jenkins agent Deployment deployed live in K3s HA cluster. 2/2 pods Running. JNLP reachable via wg0. Foundation for Kubernetes plugin integration.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-15T11:35:00Z
- **Completed:** 2026-06-15T11:55:00Z
- **Tasks:** 4
- **Files modified:** 4 (yaml + 3 planning/inventory) + 1 vault secret

## Accomplishments

- Created K8s namespace `jenkins` with `ResourceQuota` (4/8 CPU, 8Gi/16Gi mem, 20 pods).
- Created `ServiceAccount jenkins-agent` + `Secret jenkins-agent` (JNLP URL + secret).
- Deployed `Deployment jenkins-agent` with 2 replicas using `jenkins/inbound-agent:latest` (official multi-arch).
- Agent pod boot script confirms JNLP controller reachable on wg0 (`http://10.1.1.1:8085/login`).
- Secret stored in vault (`/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-15-jenkins-agent-k3s-secret.md`), never in git.
- Added `jenkins-agent` entry to `inventory/hosts/atius-srv-1.yaml` apps section.
- Added `M005-JENKINS-PODMAN` + `M005-JENKINS-AGENT` requirements to REQUIREMENTS.md and 14-PLAN.md (wave 5).

## Task Commits

1. **14-06 live + planning** - `230facfc9` (in same commit as 14-05) and post-execution adjustments in this SUMMARY

## Files Created/Modified

### Live (K8s manifests)
- `modules/k3s-ha-portainer-oci/jenkins/agent-deployment.yaml` — Namespace, ServiceAccount, Secret, ResourceQuota, Deployment
- Applied to cluster via `sudo kubectl apply -f /tmp/jenkins-agent-applied.yaml` (with secret substituted)

### Vault
- `/home/ubuntu/GitHub/obsidian-vault/ideaverse/60-LOGS/2026-06-15-jenkins-agent-k3s-secret.md` — JNLP secret + recovery procedure

### Planning
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-06-PLAN.md` — created (8978 bytes)
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/phases/14-resource-governor-pm2-boot-hardening/14-PLAN.md` — wave 5 + M005-JENKINS-AGENT requirement
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/STATE.md` — Plan 14-06 entry added
- `.planning/workstreams/runtime-trust-codex-delivery-convergence/REQUIREMENTS.md` — M005-JENKINS-PODMAN/AGENT rows

### Inventory
- `inventory/hosts/atius-srv-1.yaml` — `jenkins-agent` entry (runtime: k8s, cluster: srv1-k3s, namespace: jenkins)

## Decisions Made

- **`jenkins/inbound-agent:latest` over `localhost/jenkins:podman-latest`:** K3s nodes don't have access to localhost podman image registry. The official inbound-agent image is multi-arch and pulls from Docker Hub.
- **Static Deployment (not Kubernetes plugin pods) for now:** Plugin installation in Jenkins controller is a separate task. Static Deployment proves the cluster integration works and gives a known-good target for the JNLP registration once the plugin is installed.
- **Secret handling:** openssl rand -hex 32, stored in vault, applied via sed to a temp file (not in repo).
- **ResourceQuota 4/8 CPU + 8Gi/16Gi mem:** reasonable for build workloads; can be tuned based on observed usage.

## Deviations from Plan

**1. [Rule 2 - Missing Critical] localhost/jenkins:podman-latest not available in K3s**
- **Found during:** Task 3 (Deployment)
- **Issue:** K3s node agent tried to pull `localhost/jenkins:podman-latest` and got `ImagePullBackOff` because containerd can't resolve `localhost`.
- **Fix:** Swapped to `jenkins/inbound-agent:latest` (official multi-arch) and added a comment in the YAML explaining the swap.
- **Committed in:** this SUMMARY

## Issues Encountered

- First apply used `localhost/jenkins:podman-latest` (mirroring the SRV-1 podman local registry) — failed in K3s because containerd has no host-side access to that registry. Swapped to official image.

## Verification

```bash
# Namespace + resources
$ sudo kubectl -n jenkins get all
NAME                                READY   STATUS    RESTARTS   AGE
pod/jenkins-agent-5b6d7dc8b5-bjf7p 1/1     Running   0          30s
pod/jenkins-agent-5b6d7dc8b5-lgq5q 1/1     Running   0          18s

NAME                            READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/jenkins-agent   2/2     2            2           30s

# Agent logs
$ sudo kubectl -n jenkins logs jenkins-agent-5b6d7dc8b5-bjf7p
[agent] booting in cluster pod $
[agent] JENKINS_AGENT_NAME=k3s-agent-static
[agent] jnlp url=http://10.1.1.1:8085
[agent] waiting for jenkins controller on wg0...
[agent] controller reachable

# Resource quota applied
$ sudo kubectl -n jenkins get resourcequota
NAME            AGE
jenkins-quota   30s

# Public-domain Jenkins still healthy (sanity)
$ curl -sI https://jenkins.atius.com.br/ | grep x-jenkins
x-jenkins: 2.541.3
```

## User Setup Required

**Next step requires manual action in Jenkins controller UI** (out of scope for this plan):

1. Install **Kubernetes plugin** (id: `kubernetes`) via Manage Jenkins → Plugins
2. Configure cloud: Manage Jenkins → Clouds → Kubernetes → Add
   - Kubernetes URL: `https://10.1.1.1:6443` (in-cluster)
   - Credentials: K8s service account token (auto-generated by plugin if configured)
   - Jenkins URL: `http://10.1.1.1:8085`
3. Add Pod Template:
   - Name: `k3s-podman`
   - Namespace: `jenkins`
   - Label: `k3s`
   - Container template: `localhost/jenkins:podman-latest` (Podman-in-container for builds)
4. Create a test pipeline job with `agent { label 'k3s' }` and verify pod auto-provision

## Next Phase Readiness

Ready for `14-02` (PM2 boot canonicalization) and `14-03` (boot/login-linger + cgroup validation).

The K8s agent foundation is in place; the dynamic JNLP registration becomes a one-time controller-side config change.

---

*Phase: 14-resource-governor-pm2-boot-hardening*
*Plan: 14-06*
*Completed: 2026-06-15*
