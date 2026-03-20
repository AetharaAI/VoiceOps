"""Add outbound campaigns

Revision ID: 20260320_0002
Revises: 20260305_0001
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '20260320_0002'
down_revision = '20260305_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'outbound_campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id')),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('caller_id_number', sa.String(length=32)),
        sa.Column('lead_source', sa.String(length=255)),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('opening_line', sa.Text(), nullable=False),
        sa.Column('qualification_fields', sa.JSON(), nullable=False),
        sa.Column('objection_guidance', sa.Text()),
        sa.Column('booking_target', sa.Text()),
        sa.Column('retry_rules', sa.JSON(), nullable=False),
        sa.Column('voicemail_config', sa.JSON(), nullable=False),
        sa.Column('handoff_rules', sa.JSON(), nullable=False),
        sa.Column('crm_mapping', sa.JSON(), nullable=False),
        sa.Column('llm_config', sa.JSON(), nullable=False),
        sa.Column('tts_config', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('outbound_campaigns')
