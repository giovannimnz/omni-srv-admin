# Spike Conventions

## Remote Development Benchmarks

- Use lowercase canonical FQDNs: `atius-srv-1.atius.internal`,
  `atius-srv-2.atius.internal`, `atius-srv-3.atius.internal`, and
  `horistic-srv.atius.internal`.
- Resolve each FQDN to its OCI/DRG address before measuring. A name resolving
  through a reserve or public path is a failed sample, not a fallback success.
- Keep cold connection setup, warm `true`, warm interactive shell, reconnect,
  and expired-master recovery as separate measurements.
- Report sample count, arithmetic mean, p50, p95, p99, failures and host load.
  Treat 13-15 ms as a controlled warm stretch target, not a universal SLA.
- Create `ControlPath` sockets only below a caller-owned `0700` directory and
  use `%C` or a tuple that contains remote user, host and port.
- Run benchmarks with `BatchMode=yes` and `StrictHostKeyChecking=yes`. Missing
  trust evidence blocks the benchmark; never auto-accept a host key.

## Fleet Identity And Transport

- Owner users are `ubuntu` on `atius-srv-1`, `atius-srv-2`, and
  `atius-srv-3`, and `horistic` on `horistic-srv`.
- Keep OpenSSH encryption enabled. Prefer upstream AEAD defaults; do not deploy
  Telnet, rsh, HPN NoneSwitch, `none` cipher patches, or an unauthenticated raw
  TCP shell.
- FreeIPA DNS records and FreeIPA/SSSD SSH host-key records are separate
  controls. Passing DNS does not prove host identity.
- Detect the installed SSSD integration before generating client config.
  SSSD 2.9 uses the distro-installed `sss_ssh_knownhostsproxy` path; newer
  deployments may support `sss_ssh_knownhosts` through `KnownHostsCommand`.

## Wayland Workspace Boundary

- NFS automount remains the fleet discovery, picker, light read/diff and
  fallback plane until an owner-local remote mode passes equivalence gates.
- Git, dependency trees, watchers, LSP, tests, builds and runtime commands
  should execute on the workspace owner host.
- A persistent SSH master accelerates terminal channels but does not create a
  filesystem namespace, cache, locking, project browser or remote agent.
- Any future NFS retirement is per host and reversible; never remove the whole
  workspace tree merely to save idle resources.

## Embedding Runtime Benchmarks

- Treat `ebeddings-local/tei-gte` as a read-only baseline. Benchmark manifests
  must use the separate `embeddings-bench` namespace and start at zero replicas.
- Enforce one active canary and `500m` total canary CPU with Kubernetes quota,
  in addition to per-pod requests and limits.
- Run candidates sequentially with one tokenizer/inference thread. Never
  compare candidates while two canaries are competing for the node.
- Record CPU-seconds and CFS throttling directly from container cgroup v2
  counters; use kubelet samples for in-run shape and memory. Also record
  peak/mean millicores, latency and dimension/finite-value validation.
- Model revision, image digest, quantization, pooling, dimensions,
  normalization and chunking are part of the embedding contract.
- Never mix 768- and 1024-dimensional vectors in one table or index. A model
  change requires a new alias plus reembedding/reindexing before cutover.
- No benchmark Deployment may create an Ingress, NodePort, public DNS route or
  router alias. Bind host-network canaries only to the private node address.
