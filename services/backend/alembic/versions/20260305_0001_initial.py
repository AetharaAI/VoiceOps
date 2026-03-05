"""Initial schema

Revision ID: 20260305_0001
Revises:
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '20260305_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = sa.Enum('owner', 'admin', 'agent', 'analyst', name='userrole')
    call_direction = sa.Enum('inbound', 'outbound', name='calldirection')
    call_status = sa.Enum(
        'queued', 'ringing', 'in_progress', 'completed', 'failed', 'no_answer', 'escalated', name='callstatus'
    )

    user_role.create(op.get_bind(), checkfirst=True)
    call_direction.create(op.get_bind(), checkfirst=True)
    call_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False, unique=True),
        sa.Column('recording_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('pii_redaction_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', user_role, nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email'),
    )

    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('persona', sa.Text(), nullable=False),
        sa.Column('script', sa.Text(), nullable=False),
        sa.Column('required_fields', sa.JSON(), nullable=False),
        sa.Column('tools_config', sa.JSON(), nullable=False),
        sa.Column('policy_config', sa.JSON(), nullable=False),
        sa.Column('workflow_dsl', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'phone_numbers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('phone_number', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False, server_default='twilio'),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'phone_number', name='uq_phone_tenant_number'),
    )

    op.create_table(
        'business_hours',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='America/Indiana/Indianapolis'),
    )

    op.create_table(
        'routing_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('rule_config', sa.JSON(), nullable=False),
        sa.Column('target_agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id')),
    )

    op.create_table(
        'calls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id')),
        sa.Column('external_call_id', sa.String(length=255)),
        sa.Column('direction', call_direction, nullable=False),
        sa.Column('status', call_status, nullable=False, server_default='queued'),
        sa.Column('from_number', sa.String(length=32), nullable=False),
        sa.Column('to_number', sa.String(length=32), nullable=False),
        sa.Column('campaign_id', sa.String(length=255)),
        sa.Column('session_id', sa.String(length=255)),
        sa.Column('context_payload', sa.JSON(), nullable=False),
        sa.Column('outcome', sa.String(length=255)),
        sa.Column('outcome_tags', sa.JSON(), nullable=False),
        sa.Column('escalation_reason', sa.Text()),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'transcript_segments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('calls.id'), nullable=False),
        sa.Column('speaker', sa.String(length=32), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('is_final', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('confidence', sa.Float()),
        sa.Column('started_ms', sa.Integer()),
        sa.Column('ended_ms', sa.Integer()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'recordings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('calls.id'), nullable=False),
        sa.Column('provider_url', sa.Text()),
        sa.Column('storage_key', sa.Text()),
        sa.Column('policy_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'forms',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('schema', sa.JSON(), nullable=False),
        sa.Column('workflow_config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'form_submissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('form_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('forms.id'), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('linked_call_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('calls.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'integration_secrets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('encrypted_secret', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_integration_secret_tenant_name'),
    )

    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('resource_type', sa.String(length=64), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'kpi_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('call_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('calls.id')),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Float(), nullable=False, server_default='0'),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('kpi_events')
    op.drop_table('audit_events')
    op.drop_table('integration_secrets')
    op.drop_table('form_submissions')
    op.drop_table('forms')
    op.drop_table('recordings')
    op.drop_table('transcript_segments')
    op.drop_table('calls')
    op.drop_table('routing_rules')
    op.drop_table('business_hours')
    op.drop_table('phone_numbers')
    op.drop_table('agents')
    op.drop_table('users')
    op.drop_table('tenants')

    sa.Enum(name='callstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='calldirection').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
