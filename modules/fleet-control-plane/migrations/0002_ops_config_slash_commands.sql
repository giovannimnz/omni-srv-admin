-- Omni Srv Admin ops/config/slash-command registry.
-- This extends DbOmniFleet into the canonical PostgreSQL database for
-- omni-srv-admin operational state. Raw secrets remain outside this database.

CREATE TABLE IF NOT EXISTS "TbOpsScopes" (
    id TEXT PRIMARY KEY,
    host_id TEXT REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    filesystem_path TEXT NOT NULL,
    purpose TEXT NOT NULL,
    owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "TbConfigItems" (
    id BIGSERIAL PRIMARY KEY,
    scope_id TEXT REFERENCES "TbOpsScopes"(id) ON DELETE CASCADE,
    host_id TEXT REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value JSONB,
    value_type TEXT NOT NULL DEFAULT 'json',
    source TEXT NOT NULL DEFAULT 'database',
    sensitive BOOLEAN NOT NULL DEFAULT false,
    secret_ref TEXT,
    description TEXT,
    updated_by TEXT NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (sensitive = false AND value IS NOT NULL AND secret_ref IS NULL)
        OR
        (sensitive = true AND value IS NULL AND secret_ref IS NOT NULL)
    ),
    UNIQUE (scope_id, host_id, key)
);

CREATE TABLE IF NOT EXISTS "TbSlashCommands" (
    id BIGSERIAL PRIMARY KEY,
    command TEXT NOT NULL UNIQUE CHECK (command LIKE '/%'),
    provider TEXT NOT NULL DEFAULT 'cli-anything',
    target_program TEXT NOT NULL,
    target_path TEXT NOT NULL,
    invocation TEXT NOT NULL,
    description TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "TbSlashCommandBindings" (
    id BIGSERIAL PRIMARY KEY,
    command_id BIGINT NOT NULL REFERENCES "TbSlashCommands"(id) ON DELETE CASCADE,
    scope_id TEXT REFERENCES "TbOpsScopes"(id) ON DELETE CASCADE,
    host_id TEXT REFERENCES "TbHosts"(id) ON DELETE CASCADE,
    required_role TEXT NOT NULL DEFAULT 'operator',
    apply_policy TEXT NOT NULL DEFAULT 'plan-first',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (command_id, scope_id, host_id)
);

CREATE INDEX IF NOT EXISTS "IdxTbOpsScopesHost" ON "TbOpsScopes"(host_id, status);
CREATE INDEX IF NOT EXISTS "IdxTbConfigItemsScopeKey" ON "TbConfigItems"(scope_id, key);
CREATE INDEX IF NOT EXISTS "IdxTbConfigItemsHostKey" ON "TbConfigItems"(host_id, key);
CREATE INDEX IF NOT EXISTS "IdxTbSlashCommandsProviderEnabled" ON "TbSlashCommands"(provider, enabled);
CREATE INDEX IF NOT EXISTS "IdxTbSlashCommandBindingsScope" ON "TbSlashCommandBindings"(scope_id, host_id);

INSERT INTO "TbOpsScopes" (id, host_id, name, filesystem_path, purpose, owner, metadata)
SELECT values_table.id, values_table.host_id, values_table.name, values_table.filesystem_path, values_table.purpose, values_table.owner, values_table.metadata::jsonb
FROM (
    VALUES
        ('srv1-ops', 'atius-srv-1', 'SRV-1 Ops', 'modules/srv1-ops', 'ATIUS-SRV-1 operational scripts and service policies', 'giovanni', '{"config_source":"database"}'),
        ('srv2-ops', 'atius-srv-2', 'SRV-2 Ops', 'modules/srv2-ops', 'ATIUS-SRV-2 operational scripts and service policies', 'giovanni', '{"config_source":"database"}'),
        ('srv3-ops', 'atius-srv-3', 'SRV-3 Ops', 'modules/srv3-ops', 'ATIUS-SRV-3 operational scripts and service policies', 'giovanni', '{"config_source":"database"}')
) AS values_table(id, host_id, name, filesystem_path, purpose, owner, metadata)
WHERE EXISTS (SELECT 1 FROM "TbHosts" WHERE "TbHosts".id = values_table.host_id)
ON CONFLICT (id) DO UPDATE SET
    host_id = EXCLUDED.host_id,
    name = EXCLUDED.name,
    filesystem_path = EXCLUDED.filesystem_path,
    purpose = EXCLUDED.purpose,
    owner = EXCLUDED.owner,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO "TbConfigItems" (scope_id, host_id, key, value, value_type, source, description, updated_by)
SELECT 'srv1-ops', 'atius-srv-1', 'resource-governor.config_source', '"database"'::jsonb, 'string', 'database', 'SRV-1 ops parameters must be resolved from PostgreSQL, with files only as bootstrap/export artifacts.', 'm004'
WHERE EXISTS (SELECT 1 FROM "TbOpsScopes" WHERE id = 'srv1-ops')
ON CONFLICT (scope_id, host_id, key) DO UPDATE SET
    value = EXCLUDED.value,
    source = EXCLUDED.source,
    description = EXCLUDED.description,
    updated_by = EXCLUDED.updated_by,
    updated_at = now();

INSERT INTO "TbSlashCommands" (command, provider, target_program, target_path, invocation, description, metadata)
VALUES
    ('/cli-anything', 'cli-anything', 'CLI-Anything', '/home/ubuntu/GitHub/Programs/CLI-Anything', '/cli-anything <software-path-or-repo>', 'Build a full CLI harness for an agent-operated target.', '{"source":"CLI-Anything README","mode":"build"}'),
    ('/cli-anything:refine', 'cli-anything', 'CLI-Anything', '/home/ubuntu/GitHub/Programs/CLI-Anything', '/cli-anything:refine <software-path> [focus]', 'Refine an existing CLI-Anything harness.', '{"source":"CLI-Anything README","mode":"refine"}'),
    ('/cli-anything:test', 'cli-anything', 'CLI-Anything', '/home/ubuntu/GitHub/Programs/CLI-Anything', '/cli-anything:test <software-path-or-repo>', 'Run CLI-Anything harness tests and update evidence.', '{"source":"CLI-Anything README","mode":"test"}'),
    ('/cli-anything:validate', 'cli-anything', 'CLI-Anything', '/home/ubuntu/GitHub/Programs/CLI-Anything', '/cli-anything:validate <software-path-or-repo>', 'Validate a CLI-Anything harness against HARNESS.md.', '{"source":"CLI-Anything README","mode":"validate"}'),
    ('/cli-anything:list', 'cli-anything', 'CLI-Anything', '/home/ubuntu/GitHub/Programs/CLI-Anything', '/cli-anything:list', 'List available CLI-Anything harnesses.', '{"source":"CLI-Anything README","mode":"list"}'),
    ('/omni-srv-admin', 'cli-anything', 'omni-srv-admin', '/home/ubuntu/GitHub/omni-srv-admin', 'cli-anything-omni-srv-admin --help', 'Future generated harness entrypoint for omni-srv-admin operations.', '{"expected_package":"cli-anything-omni-srv-admin","status":"planned"}')
ON CONFLICT (command) DO UPDATE SET
    provider = EXCLUDED.provider,
    target_program = EXCLUDED.target_program,
    target_path = EXCLUDED.target_path,
    invocation = EXCLUDED.invocation,
    description = EXCLUDED.description,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO "TbSlashCommandBindings" (command_id, scope_id, host_id, required_role, apply_policy)
SELECT "TbSlashCommands".id, "TbOpsScopes".id, "TbOpsScopes".host_id, 'operator', 'plan-first'
FROM "TbSlashCommands"
CROSS JOIN "TbOpsScopes"
WHERE "TbSlashCommands".provider = 'cli-anything'
ON CONFLICT (command_id, scope_id, host_id) DO UPDATE SET
    required_role = EXCLUDED.required_role,
    apply_policy = EXCLUDED.apply_policy;
