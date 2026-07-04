-- Customization registry for installed runtimes and upstream-following forks.
-- This extends DbOmniFleet so any omni-srv-admin checkout can read the same
-- managed app/fork/customization state, independent of the admin workstation.

CREATE TABLE IF NOT EXISTS "TbManagedApps" (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    app_id TEXT NOT NULL,
    canonical_product_id TEXT NOT NULL,
    runtime TEXT,
    install_type TEXT,
    install_path TEXT,
    source_url TEXT,
    public_url TEXT,
    healthcheck_url TEXT,
    unit TEXT,
    managed_by TEXT NOT NULL DEFAULT 'omni-srv-admin',
    update_policy TEXT,
    desired_version TEXT,
    current_version TEXT,
    state TEXT NOT NULL DEFAULT 'observed',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT "UqTbManagedAppsHostApp" UNIQUE (host_id, app_id)
);

CREATE INDEX IF NOT EXISTS "IdxTbManagedAppsCanonical"
    ON "TbManagedApps"(canonical_product_id, host_id);

CREATE TABLE IF NOT EXISTS "TbManagedForks" (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT NOT NULL REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    fork_id TEXT NOT NULL,
    canonical_product_id TEXT NOT NULL,
    sync_project TEXT,
    local_path TEXT NOT NULL,
    upstream_url TEXT NOT NULL,
    sync_manifest TEXT NOT NULL,
    runtime_app_id TEXT,
    managed_by TEXT NOT NULL DEFAULT 'omni-srv-admin',
    state TEXT NOT NULL DEFAULT 'observed',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT "UqTbManagedForksHostFork" UNIQUE (host_id, fork_id)
);

CREATE INDEX IF NOT EXISTS "IdxTbManagedForksCanonical"
    ON "TbManagedForks"(canonical_product_id, host_id);

CREATE TABLE IF NOT EXISTS "TbCustomizationPolicies" (
    id BIGSERIAL PRIMARY KEY,
    host_id TEXT REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    scope_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    canonical_product_id TEXT,
    lane TEXT NOT NULL,
    policy_type TEXT NOT NULL DEFAULT 'reapply',
    owner_module TEXT NOT NULL,
    entrypoint TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT "CkTbCustomizationPoliciesScopeType"
        CHECK (scope_type IN ('global', 'host', 'app', 'fork', 'component')),
    CONSTRAINT "CkTbCustomizationPoliciesLane"
        CHECK (lane IN ('managed-apps', 'fork-sync', 'runtime-hook', 'source-patch')),
    CONSTRAINT "CkTbCustomizationPoliciesPolicyType"
        CHECK (policy_type IN ('reapply', 'postinstall', 'sync', 'runtime', 'inventory-mirror')),
    CONSTRAINT "UqTbCustomizationPoliciesHostScope"
        UNIQUE (host_id, scope_type, target_id, lane, owner_module, policy_type)
);

CREATE INDEX IF NOT EXISTS "IdxTbCustomizationPoliciesCanonical"
    ON "TbCustomizationPolicies"(canonical_product_id, COALESCE(host_id, ''));

CREATE UNIQUE INDEX IF NOT EXISTS "UqTbCustomizationPoliciesGlobalScope"
    ON "TbCustomizationPolicies"(scope_type, target_id, lane, owner_module, policy_type)
    WHERE host_id IS NULL;

INSERT INTO "TbSlashCommands" (
    command, provider, target_program, target_path, invocation, description, metadata
)
VALUES (
    '/omni-customizations',
    'cli-anything',
    'omni-srv-admin',
    '/home/ubuntu/GitHub/omni-srv-admin',
    'python3 -m omni fleet registry show --host <host-id>',
    'Inspect or sync managed apps/forks/customization registry stored in DbOmniFleet.',
    '{"owner":"omni-srv-admin","tables":["TbManagedApps","TbManagedForks","TbCustomizationPolicies"]}'::jsonb
)
ON CONFLICT (command) DO UPDATE SET
    provider = EXCLUDED.provider,
    target_program = EXCLUDED.target_program,
    target_path = EXCLUDED.target_path,
    invocation = EXCLUDED.invocation,
    description = EXCLUDED.description,
    metadata = "TbSlashCommands".metadata || EXCLUDED.metadata,
    updated_at = now();
