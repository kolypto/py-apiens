""" Test dependency injection """
from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass
from typing import Optional

import pytest

from apiens import di


def test_add_provider():
    """ Test low level: Injector.add_provider() """
    # Use the following scenario:
    # "root" will be an application-wide injector with global stuff.
    # When a user connects via WebSockets, they are authenticated and get a connection-level injector.
    # When a user calls a function, a request-level injector is created.

    # Root injector.
    # Application-wide
    with di.Injector() as root:
        root.register_provider(di.Provider(
            token=Application,
            func=lambda: Application(title='App'),
        ))

        # A connected session injector.
        # For every connected user. Imagine WebSockets
        with di.Injector(parent=root) as connection:
            connection.register_provider(di.Provider(
                token=User,
                func=lambda: User(email='kolypto@gmail.com'),
            ))

            # A request injector.
            # For every command the user sends, an injector is created to keep the context
            with di.Injector(parent=connection) as request:
                request.register_provider(di.Provider(
                    token=DatabaseSession,
                    func=session_maker,
                    deps_kw={
                        # Function argument
                        'connection': di.Dependency(token=Connection)
                    },
                ))
                request.register_provider(di.Provider(
                    token=Connection,
                    func=lambda: Connection(url='localhost')
                ))

                # Get Application: root injector
                app = request.get(Application)
                assert isinstance(app, Application)
                assert app.title == 'App'

                # Get Application again; get the very same instance
                assert request.get(Application) is app

                # Get User: request injector (parent)
                user = request.get(User)
                assert isinstance(user, User) and user.email == 'kolypto@gmail.com'

                # Get DB session
                # Local injector + dependencies
                ssn = request.get(DatabaseSession)
                assert isinstance(ssn, DatabaseSession)
                assert isinstance(ssn.connection, Connection) and ssn.connection.url == 'localhost'  # got its dependency
                assert ssn.closed == False

            # Request quit. Make sure context managers cleaned up
            assert ssn.closed == True  # magic

            # Cannot reuse the same injector because it's been closed
            with pytest.raises(di.exc.ClosedInjectorError):
                with request:
                    pass

            # Copy its providers
            def new_request():
                return copy(request)

            # ### Test: InjectFlags.SELF
            with new_request() as request:
                # Can get local things
                assert request.has(DatabaseSession, di.SELF) == True
                assert request.get(DatabaseSession, di.SELF)
                assert request.get(DatabaseSession, di.SELF) is not ssn  # a different object!

                # Cannot go upwards
                assert request.has(Application, di.SELF) == False
                with pytest.raises(di.NoProviderError):
                    request.get(Application, di.SELF)

                # Optional works though
                assert request.has(Application, di.SELF | di.OPTIONAL) == False
                assert request.get(Application, di.SELF | di.OPTIONAL, default='Z') == 'Z'

            # ### Test: InjectFlags.SKIP_SELF
            with new_request() as request:
                # Can find things on parents
                assert request.has(Application, di.SKIP_SELF) == True
                assert request.get(Application, di.SKIP_SELF)

                # Can't find things on self
                assert request.has(DatabaseSession, di.SKIP_SELF) == False
                with pytest.raises(di.NoProviderError):
                    request.get(DatabaseSession, di.SKIP_SELF)

            # ### Test: InjectFlags.OPTIONAL
            with new_request() as request:
                assert request.get('NONEXISTENT', default=123) == 123  # no error


def test_complex_dependencies():
    """ Test low-level: nested dependencies """
    root = di.Injector()

    # "Z" depends on "A" and "B'
    root.register_provider(di.Provider(
        'Z', lambda a, b: f'a={a},b={b}', deps_kw={'a': di.Dependency('A'), 'b': di.Dependency('B')},
    ))
    # "A" depends on "C"
    root.register_provider(di.Provider(
        'A', lambda c: f'one before {c}', deps_kw={'c': di.Dependency('C')}
    ))
    # "B" depends on "D"
    root.register_provider(di.Provider(
        'B', lambda d: f'one before {d}', deps_kw={'d': di.Dependency('D')}
    ))
    # "C", "D" are regular
    root.register_provider(di.Provider('C', lambda: 'cee'))
    root.register_provider(di.Provider('D', lambda: 'dee'))

    # The whole tree is resolved
    assert root.get('Z') == 'a=one before cee,b=one before dee'

    # Done
    root.close()



@dataclass
class Application:
    title: str

@dataclass
class User:
    email: str

@dataclass
class FunctionCall:
    name: str
    result: Optional[bool]

@dataclass
class Connection:
    url: str

@dataclass
class DatabaseSession:
    connection: Connection
    closed: bool

@contextmanager
def session_maker(connection: Connection) -> DatabaseSession:
    session = DatabaseSession(connection=connection, closed=False)
    ...  # prepare

    yield session  # return and pause

    ... # clean-up
    session.closed = True
