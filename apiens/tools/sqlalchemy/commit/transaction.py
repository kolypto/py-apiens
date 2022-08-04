""" SqlAlchemy tools related to transactions """

from contextlib import contextmanager
from typing import ContextManager

import sqlalchemy as sa
import sqlalchemy.orm


@contextmanager  # type: ignore[arg-type]
def db_transaction(session: sa.orm.Session) -> ContextManager[sa.orm.Session]:  # type: ignore[var-annotated,misc]
    """ Transactional context manager: commit things if everything goes fine, rollback if it doesn't 
    
    Example:
        with SessionMaker() as ssn, db_transaction(ssn):
            ssn.add(...)
    """
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
