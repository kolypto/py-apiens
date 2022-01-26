""" Helpers to store things inside the Session object (using its Session.info attribute)

* `SessionInfoStorage` is a helper class that lets you
  store things into a `Session`. Our model observers use it
  to store the recorded changes there. Then, once you're done
  changing, those changes are reported from that Session storage.
* `SessionInfoDictStorage` is a special helper class that
  further assists you with storing mappings into a Session
* Each Session.info storage helper provides common functions:
  init storage, get value, set value, clean-up
* Each Session.info storage helper uses a unique key
  in Session.info, so changes recorded by different observers
  won't overwrite each other.
"""

from typing import Hashable, Any, Generic, TypeVar, Callable, Optional, Mapping

from sqlalchemy.orm import Session


# The default value factory
T = TypeVar('T')


class SessionInfoStorage(Generic[T]):
    """ Helper to store things inside sessions' Session.info

    Example:

        in_session = SessionInfoStorage(f'myclass:{id(self)}', default_factory=dict)

        storage = in_session(ssn).storage()
        in_session[key] = value  # store anything on a Session
    """

    DEFAULT_FACTORY: Callable[[], T]

    @classmethod
    def for_object(cls, prefix: str, obj: object):
        """ Create a separate Session info storage for an object using its hash and a unique prefix """
        return cls(key=key_for_object(prefix, obj))

    def __init__(self, key: Hashable):
        """

        Args:
            key: The key to use in Session.info
            default: The default value factory that initializes the session info key
        """
        self.key = key
        self.default_factory = self.DEFAULT_FACTORY

    def storage(self, session: Session) -> T:
        """ Get the Session storage or initialize it """
        try:
            return session.info[self.key]
        except KeyError:
            default = self.default_factory()
            session.info[self.key] = default
            return default

    def storage_get(self, session: Session) -> T:
        """ Get the Session storage, or raise a KeyError """
        return session.info[self.key]

    def storage_cleanup(self, session: Session, default: Any = None) -> Optional[T]:
        """ Clean-up the Session storage and return its former value (or `default`) """
        return session.info.pop(self.key, default)


def key_for_object(prefix: str, obj: object):
    """ Generate a unique name using a prefix and an object's hash """
    return f'{prefix}:{id(obj)}'


# The values of a mapping
DT = TypeVar('DT')


NOTHING = object()


class SessionInfoDictStorage(SessionInfoStorage[Mapping[Hashable, DT]], Generic[DT]):
    """ Helper for storing things in a dict within sessions' Session.info """

    DEFAULT_FACTORY: Callable[[], DT] = dict

    def exists(self, session: Session, key: Hashable) -> bool:
        """ Check if a key exists within the Session's info storage """
        return self.key in session and key in session.info[self.key]

    def get(self, session: Session, key: Hashable, default=NOTHING) -> DT:
        """ Get a key, [a default], or raise a KeyError """
        try:
            return self.storage(session)[key]
        except KeyError:
            # If a default factory is provided, use its value to initialize
            if default is not NOTHING:
                return self.set(session, key, default)
            # No default? raise the error
            else:
                raise

    def get_factory(self, session: Session, key: Hashable, default_factory: Callable[[], DT]) -> DT:
        """ Get a key, [a default from the factory function], or raise a KeyError """
        try:
            return self.storage(session)[key]
        except KeyError:
            # If a default factory is provided, use its value to initialize
            if default_factory:
                return self.set(session, key, default_factory())
            # No default? raise the error
            else:
                raise

    def set(self, session: Session, key: Hashable, value: DT) -> DT:
        """ Set a value to the key within the Session's info storage """
        self.storage(session)[key] = value
        return value

    def pop(self, session: Session, key: Hashable, default=NOTHING) -> DT:
        """ Remove a key and get its value """
        storage = self.storage(session)
        if default is NOTHING:
            return storage.pop(key)
        else:
            return storage.pop(key, default)
