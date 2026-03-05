-- Run this as postgres superuser while connected to the 'postgres' database.
-- Example:
--   psql -U postgres -d postgres -f infra/sql/00_recreate_voiceops_db.sql

-- Only adjust this password.
\set voiceops_password 'CHANGE_ME_STRONG_PASSWORD'

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'voiceops') THEN
        EXECUTE format('CREATE ROLE %I WITH LOGIN PASSWORD %L', 'voiceops', :'voiceops_password');
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', 'voiceops', :'voiceops_password');
    END IF;
END $$;

-- Terminate active sessions so DROP DATABASE works.
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT pid
        FROM pg_stat_activity
        WHERE datname = 'voiceops'
          AND pid <> pg_backend_pid()
    LOOP
        PERFORM pg_terminate_backend(r.pid);
    END LOOP;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'voiceops') THEN
        EXECUTE format('DROP DATABASE %I', 'voiceops');
    END IF;
    EXECUTE format('CREATE DATABASE %I OWNER %I', 'voiceops', 'voiceops');
END $$;
