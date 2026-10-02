-- psql initializer (not executable host bind): new volumes and explicit operator
-- repair of an existing DB. Idempotent: existing passwords/roles are preserved.
\set ON_ERROR_STOP on
\getenv runtime_password SFR_ANALYTICS_RUNTIME_PASSWORD
\getenv reader_password SFR_ANALYTICS_READER_PASSWORD
\if :{?runtime_password}
\else
DO $$ BEGIN RAISE EXCEPTION 'SFR_ANALYTICS_RUNTIME_PASSWORD is required'; END $$;
\endif
\if :{?reader_password}
\else
DO $$ BEGIN RAISE EXCEPTION 'SFR_ANALYTICS_READER_PASSWORD is required'; END $$;
\endif

SELECT format('CREATE ROLE sfr_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'runtime_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sfr_runtime')
\gexec
SELECT format('CREATE ROLE sfr_reader LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', :'reader_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sfr_reader')
\gexec

-- An unexpected existing elevated role is a blocker, not permission to alter it.
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM pg_roles WHERE rolname IN ('sfr_runtime', 'sfr_reader')
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR NOT rolcanlogin)
    ) OR EXISTS (
        SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
        WHERE r.rolname IN ('sfr_runtime', 'sfr_reader')
    ) THEN
        RAISE EXCEPTION 'Existing analytics role privileges require operator review';
    END IF;
END $$;

REVOKE ALL ON DATABASE sfr_analytics FROM PUBLIC;
GRANT CONNECT ON DATABASE sfr_analytics TO sfr_runtime, sfr_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE sfr_runtime SET timezone = 'UTC';
ALTER ROLE sfr_runtime SET statement_timeout = '1000ms';
ALTER ROLE sfr_runtime SET lock_timeout = '250ms';
ALTER ROLE sfr_reader SET timezone = 'UTC';
ALTER ROLE sfr_reader SET default_transaction_read_only = on;
ALTER ROLE sfr_reader SET statement_timeout = '5000ms';
