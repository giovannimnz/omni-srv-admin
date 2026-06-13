-- Live one-time table rename for the M004 naming contract.
-- Run inside DbOmniFleet after the database has been renamed from omni_fleet.
-- The DO blocks are idempotent for old lowercase names; quoted names are
-- required because PostgreSQL folds unquoted CamelCase identifiers to lowercase.

BEGIN;

ALTER TABLE IF EXISTS public.hosts RENAME TO "TbHosts";
ALTER TABLE IF EXISTS public.nodes RENAME TO "TbNodes";
ALTER TABLE IF EXISTS public.programs RENAME TO "TbPrograms";
ALTER TABLE IF EXISTS public.versions RENAME TO "TbVersions";
ALTER TABLE IF EXISTS public.update_plans RENAME TO "TbUpdatePlans";
ALTER TABLE IF EXISTS public.licenses RENAME TO "TbLicenses";
ALTER TABLE IF EXISTS public.audit_events RENAME TO "TbAuditEvents";
ALTER TABLE IF EXISTS public.ops_scopes RENAME TO "TbOpsScopes";
ALTER TABLE IF EXISTS public.config_items RENAME TO "TbConfigItems";
ALTER TABLE IF EXISTS public.slash_commands RENAME TO "TbSlashCommands";
ALTER TABLE IF EXISTS public.slash_command_bindings RENAME TO "TbSlashCommandBindings";

ALTER INDEX IF EXISTS public.idx_nodes_health_status RENAME TO "IdxTbNodesHealthStatus";
ALTER INDEX IF EXISTS public.idx_programs_host_name RENAME TO "IdxTbProgramsHostName";
ALTER INDEX IF EXISTS public.idx_update_plans_host_state RENAME TO "IdxTbUpdatePlansHostState";
ALTER INDEX IF EXISTS public.idx_licenses_program_status RENAME TO "IdxTbLicensesProgramStatus";
ALTER INDEX IF EXISTS public.idx_audit_events_host_action RENAME TO "IdxTbAuditEventsHostAction";
ALTER INDEX IF EXISTS public.idx_ops_scopes_host RENAME TO "IdxTbOpsScopesHost";
ALTER INDEX IF EXISTS public.idx_config_items_scope_key RENAME TO "IdxTbConfigItemsScopeKey";
ALTER INDEX IF EXISTS public.idx_config_items_host_key RENAME TO "IdxTbConfigItemsHostKey";
ALTER INDEX IF EXISTS public.idx_slash_commands_provider_enabled RENAME TO "IdxTbSlashCommandsProviderEnabled";
ALTER INDEX IF EXISTS public.idx_slash_command_bindings_scope RENAME TO "IdxTbSlashCommandBindingsScope";

COMMIT;
