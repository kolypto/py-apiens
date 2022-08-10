""" SqlAlchemy tools related to instance expiration """

from contextlib import contextmanager

import sqlalchemy as sa
import sqlalchemy.orm


@contextmanager
def no_expire_on_commit(session: sa.orm.Session):
    """ Temporarily stop expiring SqlAlchemy instances on commit()

    When you do `session.commit()`, every sqlalchemy instance becomes expired. This means that every attribute is
    treated as if it's not loaded, and whenever you touch them, a lazy-load will occur.

    This context manager turns this behavior off temporarily: you commit(), and the instance is still there for you.
    """
    # Expire on commit
    prev_expire_on_commit = session.expire_on_commit
    session.expire_on_commit = False

    # Yield
    try:
        yield session
    # Restore
    finally:
        session.expire_on_commit = prev_expire_on_commit


def commit_no_expire(session: sa.orm.Session):
    """ Do commit() on this session without expiring instances

    When you commit(), every instance is marked as "expired": that is, touching an attribute makes an SQL query.
    This function will commit without expiring instances.
    """
    # Expire on commit: disable
    prev_expire_on_commit = session.expire_on_commit
    session.expire_on_commit = False

    # Yield
    try:
        session.commit()
    # Restore
    finally:
        session.expire_on_commit = prev_expire_on_commit
