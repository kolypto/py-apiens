""" Execute a callback on Session events at a later time.

Usa case: schedule a Celery task to be executed if, and only if, a session commits.

Example:
    ssn_later.after_commit(ssn, do_something_useful)

If you're wondering: all callbacks are executed in sequence, because they're stored as an ordered list.
"""

from collections import abc
from collections import defaultdict
from functools import partial
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.util import symbol

from .session_info_storage import SessionInfoDictStorage


UserCallback = abc.Callable[..., Any]


def before_flush(ssn: Session, before_flush: UserCallback, *args, **kwargs):
    """ Exec a callable before the saved objects are flushed to the database

    You can iter(ssn), or analyze ssn.new, ssn.dirty, ssn.deleted to find out which objects will be flushed.

    Note that unless the objects are commit()ed, they're not final: a rollback may undo them.
    """
    schedule_once_on_session_event(ssn, 'before_flush', partial(before_flush, *args, **kwargs))


def after_flush(ssn: Session, after_flush: UserCallback, *args, **kwargs):
    """ Exec a callable after the saved objects are flushed to the database

    You can still inspect the session at this point: it's still in pre-flush state.

    Note that unless the objects are commit()ed, they're not final: a rollback may undo them.

    ***WARNING***: It's unsafe to do ORM operations here because they may confuse the unfinished Session object!
    """
    schedule_once_on_session_event(ssn, 'after_flush', partial(after_flush, *args, **kwargs))


def after_flush_postexec(ssn: Session, after_flush_postexec: UserCallback, *args, **kwargs):
    """ Exec a callable after the saved objects are flushed to the database

    Unlike `after_flush`, it's a safe place to make additional ORM operations.

    Note that unless the objects are commit()ed, they're not final: a rollback may undo them.
    """
    schedule_once_on_session_event(ssn, 'after_flush_postexec', partial(after_flush_postexec, *args, **kwargs))


def before_commit(ssn: Session, before_commit: UserCallback, *args, **kwargs):
    """ Exec a callable before the session commits and persists the changes to the database

    At this point, it's very likely that everything will be saved successfully.

    NOTE: if flush() is not called explicitly, then `before_commit` goes in front of `before_flush`!
    """
    schedule_once_on_session_event(ssn, 'before_commit', partial(before_commit, *args, **kwargs))


def after_commit(ssn: Session, after_commit: UserCallback, *args, **kwargs):
    """ Exec a callable after the session has committed the changes to the database

    Note: the session is not active anymore; you can't make queries.
    If you need to make a query, perhaps make it in `before_commit`, but send your notifications in `after_commit`
    """
    schedule_once_on_session_event(ssn, 'after_commit', partial(after_commit, *args, **kwargs))


def after_rollback(ssn: Session, after_rollback: UserCallback, *args, **kwargs):
    """ Exec a callable after the session's outermost transaction is rolled back.

    Note: the session is not active; it's invalid!
    """
    schedule_once_on_session_event(ssn, 'after_rollback', partial(after_rollback, *args, **kwargs))


def after_soft_rollback(ssn: Session, after_soft_rollback: UserCallback, *args, **kwargs):
    """ Exec a callable after the session's ourtermost transaction is rolled back.

    Note: the session is still active; you can make queries
    """
    schedule_once_on_session_event(ssn, 'after_soft_rollback', partial(after_soft_rollback, *args, **kwargs))


def schedule_once_on_session_event(ssn: Session, event_name: str, callback: UserCallback, *args, **kwargs):
    """ A low-level API to schedule an event to be fired once on a Session event """
    assert isinstance(ssn, Session)
    _storage.append_callback(ssn, event_name, callback)


def reset(ssn: Session, event_name: str = None):
    """ Remove all scheduled callbacks, or if name is given, reset callbacks for one particular event """
    if event_name is None:
        _storage.reset_stored_callbacks(ssn)
    else:
        _storage.reset_stored_callbacks_for(ssn, event_name)


# region Store callbacks into Session

class _SessionCallbacksStorage(SessionInfoDictStorage[list]):
    DEFAULT_FACTORY: abc.Callable[..., Any] = lambda self: defaultdict(list)

    def reset_stored_callbacks(self, session: Session):
        """ Clean-up all stored callbacks """
        self.storage_cleanup(session)

    def reset_stored_callbacks_for(self, session: Session, event_name: str):
        """ Clean-up callbacks stored for a particular `event_name` """
        self.pop(session, event_name, None)

    def append_callback(self, session: Session, event_name: str, callback: UserCallback):
        """ Append a one-shot callback onto a given Session event """
        self.get(session, event_name).append(callback)

    def fire_callbacks_for_event(self, session: Session, event_name: str):
        """ Fire all callbacks for a given event on a given Session """
        for callback in self.pop(session, event_name, ()):
            callback()


_storage = _SessionCallbacksStorage(key=symbol('ssn-event-later'))

# endregion


# region Subscribe to events

@event.listens_for(Session, 'before_flush', named=True)
def _session_before_flush_handler(session: Session, **kw):
    _storage.fire_callbacks_for_event(session, 'before_flush')


@event.listens_for(Session, 'after_flush', named=True)
def _session_after_flush_handler(session: Session, **kw):
    _storage.fire_callbacks_for_event(session, 'after_flush')


@event.listens_for(Session, 'after_flush_postexec', named=True)
def _session_after_flush_postexec_handler(session: Session, **kw):
    _storage.fire_callbacks_for_event(session, 'after_flush_postexec')


@event.listens_for(Session, 'before_commit', named=True)
def _session_before_commit_handler(session: Session, **kw):
    _storage.fire_callbacks_for_event(session, 'before_commit')


# Subscribe to events that require some clean-up

@event.listens_for(Session, 'after_commit', named=True)
def _session_after_commit_handler(session: Session):
    try:
        _storage.fire_callbacks_for_event(session, 'after_commit')
    except:
        # When an exception is fired inside the after_commit handler, it ruins the Session:
        # it's left in a dysfunctional state. Any attempt to execute anything gives the following error:
        #
        #   sqlalchemy.exc.InvalidRequestError: This session is in 'committed' state;
        #   no further SQL can be emitted within this transaction
        #
        # This happens because Session.commit() fails to close() the session.
        # We do it here to make sure the Session remains functional.
        session.close()

        # Keep failing
        raise
    finally:
        # The session is closed now.
        # Reset the session to make sure nothing gets executed when it's reused
        _storage.reset_stored_callbacks(session)


@event.listens_for(Session, "after_rollback")
def _session_after_rollback_handler(session: Session):
    try:
        _storage.fire_callbacks_for_event(session, 'after_rollback')
    finally:
        # The session is closed now.
        # Reset the session to make sure nothing gets executed when it's reused
        _storage.reset_stored_callbacks(session)


@event.listens_for(Session, "after_soft_rollback")
def _session_after_soft_rollback_handler(session: Session, previous_transaction):
    # This handler may be executed multiple times, for nested transactions.
    # The `session.is_active` test makes sure it's only executed for the outermost rollback
    if session.is_active:
        try:
            _storage.fire_callbacks_for_event(session, 'after_soft_rollback')
        finally:
            # The session is closed now.
            # Reset the session to make sure nothing gets executed when it's reused
            _storage.reset_stored_callbacks(session)

# endregion
