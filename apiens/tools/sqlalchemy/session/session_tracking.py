""" Track SqlAlchemy Sessions and verify that they are properly close()d.

This module verifies that your Session()s are properly close()d.
Because if not, DB connections may hang and deplete the pool.

Usage #1: use a session maker:
    Session = TrackingSessionMaker()
    ssn = Session()
    ...
    ssn.close()
    Session.assert_no_active_sessions()

Usage #2: use Session class that tracks its own instances:
    Session = TrackingSessionCls()
    ssn = Session(bind=engine)
    ...
    ssn.close()
    Session.assert_no_active_sessions()

NOTE: designed for unit-tests. Don't use in production.
"""

from __future__ import annotations

import inspect
import weakref
from collections.abc import MutableMapping
from functools import wraps
from typing import Generic, TypeVar, ClassVar

import sqlalchemy as sa
import sqlalchemy.orm


class TrackingSessionMaker(sa.orm.sessionmaker):
    """ SessionMaker that keeps track of every Session. If it's not close()d, it fails.

    Usage: in unit-tests, call `assert_no_active_sessions()` to make sure your code close()es them properly.

    NOTE: it may not be thread-safe. Don't use in production.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._active_sessions = ActiveSessionRegistry(weak=False)

    def __call__(self, **kwargs):
        ssn = super().__call__(**kwargs)
        self._active_sessions.add_and_decorate(ssn)
        return ssn

    def assert_no_active_sessions(self):
        self._active_sessions.assert_no_active_objects()


def TrackingSessionCls(weak: bool) -> type[_TrackingSessionBase]:
    """ Class factory: init a Session class that will track itself

    It's a *factory*: use it to get a class with its own tracking registry.
    """
    class TrackingSession(_TrackingSessionBase):
        _active_sessions = ActiveSessionRegistry(weak=weak)

    return TrackingSession


class _TrackingSessionBase(sa.orm.Session):
    """ Base class for Sessions that track themselves """
    assert not hasattr(sa.orm.Session, '_active_sessions')  # make sure there's no clash
    _active_sessions: ClassVar[ActiveSessionRegistry]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_sessions.add_and_decorate(self)

    @classmethod
    def assert_no_active_sessions(cls):
        cls._active_sessions.assert_no_active_objects()





T = TypeVar('T')


class ActiveObjectsRegistry(Generic[T]):
    """ A registry for objects that must be properly closed """
    active_objects: MutableMapping[T, str]

    def __init__(self, weak: bool):
        """
        Args:
            weak: use weak references?
        """
        if weak:
            self.active_objects = weakref.WeakKeyDictionary()
        else:
            self.active_objects = dict()

    def add_object(self, object: T):
        """ Register an object """
        tb_skip = 3  # how many traceback records to skip

        # Format the traceback
        # TODO: use traceback.format_stack()?
        created_at = '\n'.join(
            f'\t#{i} {frame[1]}:{frame[2]}'
            for i, frame in enumerate(reversed(list(inspect.stack(0))[tb_skip:]))
        )

        # Remember it
        self.active_objects[object] = created_at

    def add_and_decorate(self, object: T, method_name: str):
        """ Register an object. Automatically un-register it when `method_name` is called. """
        # Remember the original method
        orig_method = getattr(object, method_name)

        # Replace the method
        @wraps(orig_method)
        def method_wrapper(*args, **kwargs):
            try:
                return orig_method(*args, **kwargs)
            finally:
                self.del_object(object)

        setattr(object, method_name, method_wrapper)

        # Register the object
        self.add_object(object)

    def del_object(self, object: T):
        """ Un-register an object """
        if object in self.active_objects:
            del self.active_objects[object]

    def reset(self):
        """ Forget every object """
        self.active_objects.clear()

    def get_active_objects_info(self) -> list[str]:
        """ Get a list of objects that are still active as string reports """
        return [
            f'{object!r}\nCreated at:\n{created_at}'
            for object, created_at in self.active_objects.items()
        ]

    def assert_no_active_objects(self):
        """ Make sure there are no active objects left

        Raises:
            AssertionError: if there are active objects
        """
        if len(self.active_objects):
            active_count = len(self.active_objects)
            report = '\n\n=======\n\n'.join(self.get_active_objects_info())
            msg = f'{active_count} active:\n\n{report}'
            raise AssertionError(msg)


class ActiveSessionRegistry(ActiveObjectsRegistry[sa.orm.Session]):
    """ Implementation for SqlAlchemy sessions """

    def add_and_decorate(self, ssn: sa.orm.Session):  # type: ignore[override]
        return super().add_and_decorate(ssn, 'close')  # must be properly close()d
