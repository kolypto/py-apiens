""" Utilities for working with the database """

from collections import abc
from contextlib import contextmanager
from typing import ContextManager

import sqlalchemy as sa
import sqlalchemy.orm


@contextmanager
def db_transaction(session: sa.orm.Session) -> ContextManager[sa.orm.Session]:
    """ Transactional context manager: commit things if everything goes fine, rollback if it doesn't """
    try:
        # session.begin()  # is started automatically
        yield session

        # commit() it, but only if the session is active
        # it may be inactive when an error was raised, but properly handled
        if session.is_active:
            session.commit()
        # if the session is not active, rollback()
        else:
            session.rollback()
    # rollback() on errors
    except:
        session.rollback()
        raise


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


def db_save(session: sa.orm.Session, *instances):
    """ Commit a number of instances to the database

    1. add() them
    2. commit() them
    3. refresh() them
    """
    session.add_all(instances)
    session.commit()

    with no_expire_on_commit(session):
        session.commit()

    # Done
    return instances


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
    ssn.commit = commit_fail


def session_flush_instead_of_commit(ssn: sa.orm.Session):
    """ Disable commit() on a Session: flush() instead """
    def commit_flush():
        """ commit()? No way; flush() """
        # Simulate: send all the correct signals
        ssn.dispatch.before_commit(ssn)
        ssn.flush()  # flush() instead
        ssn.dispatch.after_commit(ssn)

    ssn.commit = commit_flush


def session_enable_commit(ssn: sa.orm.Session):
    """ Enable commit() on a Session """
    # Restore the original function
    ssn.commit = type(ssn).commit


def session_safe_commit(session: sa.orm.Session):
    """ Commit a session

    This function is useful when you don't know where the session came from.
    It may be in a non-active state, e.g. after an error. In this case, it cannot be committed.
    """
    try:
        # commit(), but only if the session is active
        if session.is_active:
            session.commit()
        # If a session is not active, some query has probably failed. Roll back.
        else:
            session.rollback()
    except:
        session.rollback()
        raise


def refresh_instances(session: sa.orm.Session, instances: abc.Iterable[object]):
    """ Refresh multiple instances at once

    This is much faster than doing `ssn.refresh()` in a loop.

    Consider using no_expire_on_commit(): in some cases, it may serve your purposes better

    Args:
        session: The session to use for querying
        instances: The list of instances to refresh
    """
    for mapper, states in _group_instances_by_mapper(instances).items():
        _refresh_multiple_instance_states(session, mapper, states).all()


def _refresh_multiple_instance_states(session: sa.orm.Session, mapper: sa.orm.mapper, states: list[sa.orm.state.InstanceState]) -> sa.orm.Query:
    """ Create a query to refresh multiple instance states at once

    Args:
        session: The session to use
        mapper: The mapper to load the instances for
        states: The list of instances to update

    Returns:
        a Query that will do it
    """
    # Collect instance identities
    identities = (state.identity for state in states)

    # Build a condition using primary keys
    pk_columns: tuple[sa.Column, ...] = mapper.primary_key
    condition = sa.tuple_(*pk_columns).in_(identities)

    # Execute one bulk query to load all instances at once.
    # This query will Session.merge() them into the Session, and thus, a bulk refresh is achieved.
    return session.query(mapper).filter(condition)


def _group_instances_by_mapper(instances: abc.Iterable[object]) -> dict[sa.orm.Mapper, list[sa.orm.state.InstanceState]]:
    """ Walk the list of instances and group them by Mapper """
    mappers_and_states = {}

    for instance in instances:
        # Get state, mapper
        state: sa.orm.state.InstanceState = sa.orm.base.instance_state(instance)
        mapper: sa.orm.Mapper = state.mapper

        # Group them
        if mapper not in mappers_and_states:
            mappers_and_states[mapper] = []
        mappers_and_states[mapper].append(state)

    return mappers_and_states
