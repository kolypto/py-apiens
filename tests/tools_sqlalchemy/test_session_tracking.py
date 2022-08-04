import pytest
import sqlalchemy as sa
import sqlalchemy.orm

from apiens.tools.sqlalchemy.session.session_tracking import TrackingSessionMaker, TrackingSessionCls
from apiens.tools.sqlalchemy import sainfo


@pytest.mark.xfail(sainfo.version.SA_13, reason='Session() is not a context manager in SA 1.3', )
def test_tracking_sessionmaker(engine: sa.engine.Engine):
    Session = TrackingSessionMaker(bind=engine)

    # === Test: use as a context manager
    # Check that the session itself works
    with Session() as ssn:
        assert ssn.query(1).scalar() == 1

    # Verify that it's properly closed
    Session.assert_no_active_sessions()  # does not fail

    # === Test: failing
    # Open a session
    ssn = Session()

    # It fails
    with pytest.raises(AssertionError) as e:
        Session.assert_no_active_sessions()

    msg = str(e.value)
    assert '1 active' in msg
    assert __file__ in msg

    # Close it. No more failures.
    ssn.close()
    Session.assert_no_active_sessions()


def test_tracking_session(engine: sa.engine.Engine):
    Session = TrackingSessionCls(weak=False)

    # === Test
    ssn = Session()

    # It fails
    with pytest.raises(AssertionError) as e:
        Session.assert_no_active_sessions()

    # Close it. No more failures
    ssn.close()
    Session.assert_no_active_sessions()
