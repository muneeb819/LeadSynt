"""ai_phase_a

Phase A: LLM provider/model catalog tables + per-agent monthly budget cap.

Revision ID: a2c0e4f8b6d1
Revises: ed1b5a8cff29
Create Date: 2026-09-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a2c0e4f8b6d1'
down_revision = 'ed1b5a8cff29'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('ai_providers',
    sa.Column('provider_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('base_url', sa.String(length=500), nullable=False),
    sa.Column('api_key_env', sa.String(length=120), nullable=True),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_providers'))
    )
    op.create_index(op.f('ix_ai_providers_provider_id'), 'ai_providers', ['provider_id'], unique=True)

    op.create_table('ai_models',
    sa.Column('model_id', sa.String(length=120), nullable=False),
    sa.Column('provider_id', sa.String(length=36), nullable=False),
    sa.Column('display_name', sa.String(length=120), nullable=False),
    sa.Column('context_window', sa.Integer(), nullable=False),
    sa.Column('input_price_per_mtok', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('output_price_per_mtok', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], name=op.f('fk_ai_models_provider_id_ai_providers')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_models'))
    )
    op.create_index(op.f('ix_ai_models_model_id'), 'ai_models', ['model_id'], unique=True)
    op.create_index(op.f('ix_ai_models_provider_id'), 'ai_models', ['provider_id'], unique=False)

    # 0 = unlimited; server_default keeps the ALTER safe on populated DBs.
    op.add_column('ai_agents', sa.Column('monthly_budget_usd', sa.Numeric(precision=12, scale=2),
                                         server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('ai_agents', 'monthly_budget_usd')
    op.drop_index(op.f('ix_ai_models_provider_id'), table_name='ai_models')
    op.drop_index(op.f('ix_ai_models_model_id'), table_name='ai_models')
    op.drop_table('ai_models')
    op.drop_index(op.f('ix_ai_providers_provider_id'), table_name='ai_providers')
    op.drop_table('ai_providers')