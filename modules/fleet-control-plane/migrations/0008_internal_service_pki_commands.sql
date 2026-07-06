-- Internal service PKI command allowlist for Omni Fleet agents.
-- Idempotent and safe through PgBouncer on DbOmniFleet.

INSERT INTO "TbFleetCommands" (
    command_key, description, local_invocation, default_profile,
    requires_approval, enabled, timeout_seconds, allowed_host_ids, metadata
)
VALUES
    (
        'omni.trust-pki.preflight',
        'Read-only local preflight for internal service PKI onboarding.',
        'python3 -m omni fleet trust-pki agent-runner preflight --host {host_id} --json',
        'interactive',
        false,
        true,
        120,
        '[]'::jsonb,
        '{"kind":"internal-service-pki","stage":"preflight"}'::jsonb
    ),
    (
        'omni.trust-pki.init-ca',
        'Initialize the internal service PKI CA on the CA host.',
        'python3 -m omni fleet trust-pki agent-runner init-ca --host {host_id} --json',
        'interactive',
        true,
        true,
        900,
        '["atius-srv-1"]'::jsonb,
        '{"kind":"internal-service-pki","stage":"init-ca"}'::jsonb
    ),
    (
        'omni.trust-pki.ensure-key-csr',
        'Ensure local host private key and CSR for internal service PKI.',
        'python3 -m omni fleet trust-pki agent-runner ensure-key-csr --host {host_id} --json',
        'interactive',
        true,
        true,
        900,
        '[]'::jsonb,
        '{"kind":"internal-service-pki","stage":"ensure-key-csr"}'::jsonb
    ),
    (
        'omni.trust-pki.issue-host',
        'Sign one host CSR from the internal service PKI CA host.',
        'python3 -m omni fleet trust-pki agent-runner issue-host --host {host_id} --json',
        'interactive',
        true,
        true,
        900,
        '["atius-srv-1"]'::jsonb,
        '{"kind":"internal-service-pki","stage":"issue-host"}'::jsonb
    ),
    (
        'omni.trust-pki.install-ca',
        'Install the internal service PKI CA chain into the local trust store.',
        'python3 -m omni fleet trust-pki agent-runner install-ca --host {host_id} --json',
        'interactive',
        true,
        true,
        900,
        '[]'::jsonb,
        '{"kind":"internal-service-pki","stage":"install-ca"}'::jsonb
    ),
    (
        'omni.trust-pki.install-leaf',
        'Install the signed internal service PKI leaf and chain locally.',
        'python3 -m omni fleet trust-pki agent-runner install-leaf --host {host_id} --json',
        'interactive',
        true,
        true,
        900,
        '[]'::jsonb,
        '{"kind":"internal-service-pki","stage":"install-leaf"}'::jsonb
    ),
    (
        'omni.trust-pki.verify',
        'Verify local internal service PKI material and trust.',
        'python3 -m omni fleet trust-pki agent-runner verify --host {host_id} --json',
        'interactive',
        false,
        true,
        300,
        '[]'::jsonb,
        '{"kind":"internal-service-pki","stage":"verify"}'::jsonb
    ),
    (
        'omni.trust-pki.reconcile',
        'Compare local internal service PKI leaf SANs with desired inventory SANs.',
        'python3 -m omni fleet trust-pki agent-runner reconcile --host {host_id} --json',
        'interactive',
        false,
        true,
        300,
        '[]'::jsonb,
        '{"kind":"internal-service-pki","stage":"reconcile"}'::jsonb
    )
ON CONFLICT (command_key) DO UPDATE SET
    description = EXCLUDED.description,
    local_invocation = EXCLUDED.local_invocation,
    default_profile = EXCLUDED.default_profile,
    requires_approval = EXCLUDED.requires_approval,
    enabled = EXCLUDED.enabled,
    timeout_seconds = EXCLUDED.timeout_seconds,
    allowed_host_ids = EXCLUDED.allowed_host_ids,
    metadata = EXCLUDED.metadata,
    updated_at = now();
