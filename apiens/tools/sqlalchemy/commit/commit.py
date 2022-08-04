""" SqlAlchemy Session tools related to Session.commit() """

import sqlalchemy as sa
import sqlalchemy.orm


def session_disable_commit(ssn: sa.orm.Session):
    """ Disable commit() on a Session: fail with an exception instead

    Use case: when commit() has unwanted side-effects, such as expiring object, or unit-of-work breakage
    """
    def commit_fail():
        """ commit()? No way; fail """
        raise Exception(
            "commit() is disabled: you can only use flush(). "
            "If you still want to commit(), use session_flush_instead_of_commit(), but then clean-up after yourself!"
        )
    ssn.commit = commit_fail  # type: ignore[assignment]


def session_enable_commit(ssn: sa.orm.Session):
    """ Enable commit() on a Session """
    # Restore the original function
    ssn.commit = type(ssn).commit  # type: ignore[assignment]


def session_flush_instead_of_commit(ssn: sa.orm.Session):
    """ Disable commit() on a Session: flush() instead """
    def commit_flush():
        """ commit()? No way; flush() """
        # Simulate: send all the correct signals
        ssn.dispatch.before_commit(ssn)
        ssn.flush()  # flush() instead
        ssn.dispatch.after_commit(ssn)

    ssn.commit = commit_flush  # type: ignore[assignment]
