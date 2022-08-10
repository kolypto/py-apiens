import pytest
import sqlalchemy as sa
import sqlalchemy.exc

from apiens.tools.sqlalchemy.postgres.pg_integrity_error import extract_postgres_unique_violation_columns
from tests.lib import created_tables, declarative_base, insert



def test_pg_integrity_error(connection: sa.engine.Connection):
    def main():
        # Ok insert
        insert(connection, User, dict(login='kolypto', email='kolypto@example.com'))

        # Named contraint
        try:
            insert(connection, User, dict(login='kolypto'))
        except sa.exc.IntegrityError as e:
            assert extract_postgres_unique_violation_columns(e, Base.metadata) == (
                User.__table__.c.login,
            )
        else:
            pytest.fail('Not raised')

        # Unnamed constraint
        try:
            insert(connection, User, dict(email='kolypto@example.com'))
        except sa.exc.IntegrityError as e:
            assert extract_postgres_unique_violation_columns(e, Base.metadata) == (
                # User.__table__.c.email,  # not reported because index does not have a name
            )
        else:
            pytest.fail('Not raised')


    # Models
    Base = declarative_base()

    class User(Base):
        __tablename__ = 'u'
        __table_args__ = (
            # Named
            sa.UniqueConstraint('login', name='u_login_key'),
            # Not named
            sa.UniqueConstraint('email'),
        )

        id = sa.Column(sa.Integer, primary_key=True)
        login = sa.Column(sa.String)
        email = sa.Column(sa.String)

    # Data
    with created_tables(connection, Base):
        main()
