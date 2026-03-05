
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
        CREATE TYPE userrole AS ENUM ('owner', 'admin', 'agent', 'analyst');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'calldirection') THEN
        CREATE TYPE calldirection AS ENUM ('inbound', 'outbound');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'callstatus') THEN
        CREATE TYPE callstatus AS ENUM ('queued', 'ringing', 'in_progress', 'completed', 'failed', 'no_answer', 'escalated');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    recording_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    pii_redaction_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    retention_days INTEGER NOT NULL DEFAULT 90,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(320) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role userrole NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_user_tenant_email UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    persona TEXT NOT NULL,
    script TEXT NOT NULL,
    required_fields JSON NOT NULL,
    tools_config JSON NOT NULL,
    policy_config JSON NOT NULL,
    workflow_dsl JSON NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS phone_numbers (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    phone_number VARCHAR(32) NOT NULL,
    provider VARCHAR(64) NOT NULL DEFAULT 'twilio',
    agent_id UUID REFERENCES agents(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_phone_tenant_number UNIQUE (tenant_id, phone_number)
);

CREATE TABLE IF NOT EXISTS business_hours (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    day_of_week INTEGER NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'America/Indiana/Indianapolis'
);

CREATE TABLE IF NOT EXISTS routing_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    rule_config JSON NOT NULL,
    target_agent_id UUID REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    agent_id UUID REFERENCES agents(id),
    external_call_id VARCHAR(255),
    direction calldirection NOT NULL,
    status callstatus NOT NULL DEFAULT 'queued',
    from_number VARCHAR(32) NOT NULL,
    to_number VARCHAR(32) NOT NULL,
    campaign_id VARCHAR(255),
    session_id VARCHAR(255),
    context_payload JSON NOT NULL,
    outcome VARCHAR(255),
    outcome_tags JSON NOT NULL,
    escalation_reason TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    call_id UUID NOT NULL REFERENCES calls(id),
    speaker VARCHAR(32) NOT NULL,
    text TEXT NOT NULL,
    is_final BOOLEAN NOT NULL DEFAULT FALSE,
    confidence DOUBLE PRECISION,
    started_ms INTEGER,
    ended_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS recordings (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    call_id UUID NOT NULL REFERENCES calls(id),
    provider_url TEXT,
    storage_key TEXT,
    policy_snapshot JSON NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS forms (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    schema JSON NOT NULL,
    workflow_config JSON NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS form_submissions (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    form_id UUID NOT NULL REFERENCES forms(id),
    payload JSON NOT NULL,
    linked_call_id UUID REFERENCES calls(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integration_secrets (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    encrypted_secret TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_integration_secret_tenant_name UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    actor_user_id UUID REFERENCES users(id),
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    metadata JSON NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kpi_events (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    call_id UUID REFERENCES calls(id),
    event_type VARCHAR(64) NOT NULL,
    value DOUBLE PRECISION NOT NULL DEFAULT 0,
    metadata JSON NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);

INSERT INTO alembic_version(version_num)
VALUES ('20260305_0001')
ON CONFLICT (version_num) DO NOTHING;

DELETE FROM alembic_version WHERE version_num <> '20260305_0001';
