"""outreach_phase_b

Phase B: Outreach engine tables — template library (outreach_templates),
outbound message log (outreach_messages), follow-up cadence rules
(follow_up_rules) and explicit human follow-up authorizations
(outreach_follow_up_authorizations).

Revision ID: b0a1e2f3c4d5
Revises: a2c0e4f8b6d1
Create Date: 2026-09-22 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b0a1e2f3c4d5'
down_revision = 'a2c0e4f8b6d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('outreach_templates',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('channel', sa.String(length=32), nullable=False),
    sa.Column('subject', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outreach_templates'))
    )
    op.create_index(op.f('ix_outreach_templates_name'), 'outreach_templates', ['name'], unique=True)

    op.create_table('outreach_messages',
    sa.Column('ticket_id', sa.String(length=36), nullable=False),
    sa.Column('contact_id', sa.String(length=36), nullable=True),
    sa.Column('template_id', sa.String(length=36), nullable=True),
    sa.Column('channel', sa.String(length=32), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('subject', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('provider_ref', sa.String(length=500), nullable=True),
    sa.Column('transport', sa.String(length=32), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('sent_by', sa.String(length=64), nullable=True),
    sa.Column('meta', sa.JSON(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], name=op.f('fk_outreach_messages_contact_id_contacts')),
    sa.ForeignKeyConstraint(['template_id'], ['outreach_templates.id'], name=op.f('fk_outreach_messages_template_id_outreach_templates')),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], name=op.f('fk_outreach_messages_ticket_id_tickets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outreach_messages'))
    )
    op.create_index(op.f('ix_outreach_messages_contact_id'), 'outreach_messages', ['contact_id'], unique=False)
    op.create_index(op.f('ix_outreach_messages_scheduled_for'), 'outreach_messages', ['scheduled_for'], unique=False)
    op.create_index(op.f('ix_outreach_messages_status'), 'outreach_messages', ['status'], unique=False)
    op.create_index(op.f('ix_outreach_messages_ticket_id'), 'outreach_messages', ['ticket_id'], unique=False)

    op.create_table('follow_up_rules',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('channel', sa.String(length=32), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('delay_hours', sa.Integer(), nullable=False),
    sa.Column('max_follow_ups', sa.Integer(), nullable=False),
    sa.Column('requires_human_authorization', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.UniqueConstraint('channel', 'sequence', name=op.f('uq_follow_up_rules_channel_sequence')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_follow_up_rules'))
    )
    op.create_index(op.f('ix_follow_up_rules_name'), 'follow_up_rules', ['name'], unique=True)

    op.create_table('outreach_follow_up_authorizations',
    sa.Column('ticket_id', sa.String(length=36), nullable=False),
    sa.Column('authorized_by', sa.String(length=36), nullable=False),
    sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('max_follow_ups', sa.Integer(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], name=op.f('fk_outreach_follow_up_authorizations_ticket_id_tickets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outreach_follow_up_authorizations'))
    )
    op.create_index(op.f('ix_outreach_follow_up_authorizations_ticket_id'), 'outreach_follow_up_authorizations', ['ticket_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_outreach_follow_up_authorizations_ticket_id'), table_name='outreach_follow_up_authorizations')
    op.drop_table('outreach_follow_up_authorizations')
    op.drop_index(op.f('ix_follow_up_rules_name'), table_name='follow_up_rules')
    op.drop_table('follow_up_rules')
    op.drop_index(op.f('ix_outreach_messages_ticket_id'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_status'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_scheduled_for'), table_name='outreach_messages')
    op.drop_index(op.f('ix_outreach_messages_contact_id'), table_name='outreach_messages')
    op.drop_table('outreach_messages')
    op.drop_index(op.f('ix_outreach_templates_name'), table_name='outreach_templates')
    op.drop_table('outreach_templates')