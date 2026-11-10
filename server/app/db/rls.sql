-- App role: not superuser, cannot bypass RLS.
-- Dev password only. Change it, and keep it in the secrets manager, for production.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gharmind_app') THEN
    CREATE ROLE gharmind_app LOGIN PASSWORD 'gharmind_app' NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO gharmind_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO gharmind_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gharmind_app;

-- Enable RLS on every table that has a tenant_id column.
-- No tenant set in the session means no rows and no writes.
DO $$
DECLARE t record;
BEGIN
  FOR t IN
    SELECT DISTINCT table_name FROM information_schema.columns
    WHERE table_schema = 'public' AND column_name = 'tenant_id'
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t.table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t.table_name);
    EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t.table_name);
    EXECUTE format(
      'CREATE POLICY tenant_isolation ON %I
         USING (tenant_id = nullif(current_setting(''app.tenant_id'', true), '''')::uuid)
         WITH CHECK (tenant_id = nullif(current_setting(''app.tenant_id'', true), '''')::uuid)',
      t.table_name);
  END LOOP;
END $$;

-- The tenants table is keyed by id. Not FORCEd, so the owner-run lookup
-- functions below can read it. The app role is still fully restricted.
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON tenants;
CREATE POLICY tenant_isolation ON tenants
  USING (id = nullif(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (id = nullif(current_setting('app.tenant_id', true), '')::uuid);

-- Narrow lookup used by the webhook: WhatsApp number -> tenant id.
-- Returns only an id, never any tenant data.
CREATE OR REPLACE FUNCTION resolve_tenant_by_whatsapp(p_number text)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT id FROM tenants
  WHERE whatsapp_number IS NOT NULL
    AND p_number ~ '[0-9]'
    AND regexp_replace(whatsapp_number, '\D', '', 'g') = regexp_replace(p_number, '\D', '', 'g')
  LIMIT 1
$$;
REVOKE ALL ON FUNCTION resolve_tenant_by_whatsapp(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_tenant_by_whatsapp(text) TO gharmind_app;

-- One login per person, across all companies, so the email alone finds the account.
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON users (lower(email));

-- Narrow lookup used by login, before we know which company the user belongs to.
-- Returns only what password checking needs. Never the MFA secret itself.
-- NOTE: the function owner must be able to bypass row-level security. In dev the owner
-- is the Postgres superuser. In production, own it with a dedicated role that has BYPASSRLS.
CREATE OR REPLACE FUNCTION login_lookup(p_email text)
RETURNS TABLE (user_id uuid, tenant_id uuid, password_hash text, active boolean, has_mfa boolean)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT u.id, u.tenant_id, u.password_hash::text, u.active, (u.mfa_secret IS NOT NULL)
  FROM users u
  WHERE lower(u.email) = lower(p_email)
  LIMIT 1
$$;
REVOKE ALL ON FUNCTION login_lookup(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION login_lookup(text) TO gharmind_app;
