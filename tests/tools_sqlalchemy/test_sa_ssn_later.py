import pytest
import sqlalchemy as sa
import sqlalchemy.orm

from jessiql.testing import created_tables
from jessiql.util import sacompat
from apiens.tools.sqlalchemy.session import ssn_later



def test_ssn_later():
    def main():
        # === Test: flush(), rollback()
        with Session() as ssn:
            set_up_logging(ssn)

            # Flush
            ssn.add(User())
            ssn.flush()

            assert log == [
                'before_flush',
                'after_flush',
                'after_flush_postexec',
            ]

            # Flush again, make sure same handlers won't fire again
            log.clear()
            ssn.flush()
            assert log == []

            # Rollback. Let the remaining handlers fire
            ssn.rollback()
            assert log == [
                'after_rollback',
            ]

        # === Test: commit()
        with Session() as ssn:
            set_up_logging(ssn)

            # Commit
            ssn.add(User())
            ssn.commit()

            assert log == [
                'before_commit',  # note: goes before flush!
                'before_flush',
                'after_flush',
                'after_flush_postexec',
                'after_commit',
            ]

    # Logging facilities
    log = []
    def set_up_logging(ssn: sa.orm.Session):
        log.clear()
        ssn_later.reset(ssn)
        ssn_later.before_flush(ssn, log.append, 'before_flush')
        ssn_later.after_flush(ssn, log.append, 'after_flush')
        ssn_later.after_flush_postexec(ssn, log.append, 'after_flush_postexec')
        ssn_later.before_commit(ssn, log.append, 'before_commit')
        ssn_later.after_commit(ssn, log.append, 'after_commit')
        ssn_later.after_rollback(ssn, log.append, 'after_rollback')
        ssn_later.after_soft_rollback(ssn, log.append, 'after_soft_rollback')

    # Go
    with created_tables(engine, Base.metadata):
        main()


def test_session_events_can_recover_after_exception():
    # Test that it can recover after exceptions thrown inside the event handler
    def main():
        with Session() as ssn:
            ssn_later.after_commit(ssn, i_will_fail)

            with pytest.raises(AssertionError, match=':trollface'):
                ssn.commit()

            # EXPECTED BEHAVIOR:
            # a rollback() works just fine
            #
            # UNEXPECTED BEHAVIOR:
            # The session is left in a dysfunctional state and raises an error
            #   sqlalchemy.exc.InvalidRequestError: This session is in 'committed' state;
            #   no further SQL can be emitted within this transaction
            ssn.rollback()

            # Clean-up
            rowcount = ssn.query(User).delete()
            assert rowcount == 0  # nothing
            ssn.commit()

    # Failing func
    def i_will_fail():
        raise AssertionError(':trollface:')

    # Go
    with created_tables(engine, Base.metadata):
        main()


# SqlAlchemy models
Base = sacompat.declarative_base()

class User(Base):
    __tablename__ = 'u'

    id = sa.Column(sa.Integer, primary_key=True)
    login = sa.Column(sa.String)
    name = sa.Column(sa.String)


# DB Engine
from tests.crud.test_crud import engine, Session  # reuse DB connection
