#!/bin/sh
# Executed only for a NEW volume. Existing volumes: migration grants plus
# explicit operator role provisioning; passwords never appear as CLI arguments.
set -eu
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
\getenv runtime_password SFR_ANALYTICS_RUNTIME_PASSWORD
CREATE ROLE sfr_runtime LOGIN PASSWORD :'runtime_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
\getenv reader_password SFR_ANALYTICS_READER_PASSWORD
CREATE ROLE sfr_reader LOGIN PASSWORD :'reader_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE sfr_reader SET timezone = 'UTC';
ALTER ROLE sfr_reader SET default_transaction_read_only = on;
ALTER ROLE sfr_reader SET statement_timeout = '5000ms';
REVOKE ALL ON DATABASE sfr_analytics FROM PUBLIC;
GRANT CONNECT ON DATABASE sfr_analytics TO sfr_runtime, sfr_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE sfr_runtime SET timezone = 'UTC';
ALTER ROLE sfr_runtime SET statement_timeout = '1000ms';
ALTER ROLE sfr_runtime SET lock_timeout = '250ms';
SQL
