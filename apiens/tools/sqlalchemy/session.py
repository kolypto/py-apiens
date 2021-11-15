""" Utilities for working with the database """

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

        # commit() it, but only if it's active
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

    # Need to refresh the instances because commit() has expired every attribute
    # This also enables us to receive new primary keys, server defaults, etc, from the updated row.
    for instance in instances:  # TODO: a more efficient way to refresh multiple instances??
        session.refresh(instance)

    # Done
    return instances
