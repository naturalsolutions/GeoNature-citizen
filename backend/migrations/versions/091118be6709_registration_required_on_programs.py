"""Registration required on programs

Revision ID: 091118be6709
Revises: 7be0cef93665
Create Date: 2024-03-04 09:59:18.725779

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "091118be6709"
down_revision = "7be0cef93665"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("t_programs", schema="gnc_core") as batch_op:
        batch_op.add_column(
            sa.Column(
                "registration_required",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.alter_column(
            "is_active",
            existing_type=sa.BOOLEAN(),
            nullable=False,
            existing_server_default=sa.text("true"),
        )

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("t_programs", schema="gnc_core") as batch_op:
        batch_op.alter_column(
            "is_active",
            existing_type=sa.BOOLEAN(),
            nullable=True,
            existing_server_default=sa.text("true"),
        )
        batch_op.drop_column("registration_required")

    # ### end Alembic commands ###
