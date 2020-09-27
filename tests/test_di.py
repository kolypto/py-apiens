""" Test dependency injection """
from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass
from typing import Optional

import pytest

from apiens import di


def test_di_functions():
    """ Test DI with functions: automatic dependency reading from a function's signature """
    # Prepare some resolvables

    @di.signature(exclude=['debug'])  # exclude an argument from DI consideration
    def init_application(debug: bool = False) -> Application:
        """ Provider: Application """
        return Application(title='App')

    @di.signature()
    def authenticate_user(app: Application) -> User:
        """ Provider: User """
        assert app.title == 'App'
        return User(email='kolypto@gmail.com')

    @di.signature()
    def db_connect(app: Application) -> Connection:
        """ Provider: DB connection """
        assert app.title == 'App'
        return Connection(url='localhost')

    @di.signature('connection')  # pick one argument
    @contextmanager
    def db_session(connection: Connection, connect: bool = True) -> DatabaseSession:
        """ Provider: DB session """
        connection = DatabaseSession(connection=connection, closed=False)
        try:
            yield connection
        finally:
            connection.closed = True

    @di.signature()
    def authenticated(user: User):
        """ Provider: anonymous requirement to be signed in (guard) """
        if user.email != 'kolypto@gmail.com':
            raise Unauthenticated('Unauthenticated')

    # Prepare an injector
    with di.Injector() as root:
        root.provide(Application, init_application)
        root.provide(Connection, db_connect)
        root.provide(DatabaseSession, db_session)

        # Authenticate
        with di.Injector(parent=root) as client:
            client.provide(User, authenticate_user)
            client.provide(authenticated, authenticated)

            # Run a function
            @di.kwargs(app=Application, ssn=DatabaseSession)  # explicit kwargs
            @di.depends(authenticated)  # double-depends
            def hello_app(greeting: str, app, ssn):  # `greeting` is not provided; it's a required argument
                """ The function to invoke """
                if not ssn.closed:
                    return f'{greeting} {app.title}'

            ret = client.invoke(hello_app, greeting='hello')
            assert ret == 'hello App'

        # Authenticate as another user
        with di.Injector(parent=root) as client:
            root.provide_value(User, User(email='anonymous'))
            client.provide(authenticated, authenticated)

            # See that authenticated() reports an error
            with pytest.raises(Unauthenticated):
                client.invoke(authenticated)

            # See that user_func() fails with it
            with pytest.raises(Unauthenticated):
                client.invoke(hello_app, greeting='hello')


def test_di_cleanup():
    """ Test how cleanup works """

    # Only one connection is available. The Injector should be able to reuse it
    connection_pool = ['connection-1']

    @di.signature()
    @contextmanager
    def get_connection():
        try:
            # Get a connection
            connection = connection_pool.pop()
            yield connection
        finally:
            # Clean-up
            connection_pool.append(connection)

    @di.kwargs(ssn='connection')
    def save_to_db(ssn):
        pass

    with di.Injector() as root:
        # I'm lazy. Let's use a custom token
        root.provide('connection', get_connection)

        root.get('connection')
        root.get('connection')
        root.get('connection')
        root.get('connection')

        # The only connection is in use
        assert len(connection_pool) == 0

    # Clean-up returned it to the pool
    assert len(connection_pool) == 1


def test_di_overrides():
    """ Test how overrides work with DI """

    # NOTE: it does not!

    @di.kwargs(user='authenticated_user')
    def authenticated_user_email(user: Optional[User]):
        if user is None:
            return None
        else:
            return user.email

    with di.Injector() as request:
        request.provide_value('authenticated_user', User(email='kolypto@gmail.com'))
        request.provide('email', authenticated_user_email)

        # User authenticated ok
        assert request.get('email') == 'kolypto@gmail.com'

        # Now relogin as another user
        with di.Injector(parent=request) as anonymized:
            anonymized.provide_value('authenticated_user', User(email='anonymous@localhost'))

            # The higher-level injector still sees the old value
            assert request.get('email') == 'kolypto@gmail.com'

            # NOTE: at this level, we don't see any changes.
            # Currently, this is the expected behavior: you can't override higher-level things from down below.
            # assert anonymized.get('email') == 'anonymous@localhost'  # not implemented
            assert anonymized.get('email') == 'kolypto@gmail.com'  # ❗ not overridden!

        # And it's immediately lost when the `anonymized` context quits
        assert request.get('email') == 'kolypto@gmail.com'


def test_di_cleanup_when_everything_fails():
    """ Test how cleanup behaves when there are multiple failures """

    cleaned_up = []

    root = di.Injector()

    # Init 5 providers
    # Get 5 instances
    for n in range(5):
        @di.depends()
        @contextmanager
        def failing_provider(n=n):
            try:
                yield n
            finally:
                cleaned_up.append(n)
                raise AssertionError

        root.provide(n, failing_provider)
        assert root.get(n) == n

    # Now we have 5 clean-ups waiting to be executed
    # Quit. They will all fail, but report their numbers into `cleaned_up`
    with pytest.raises(AssertionError):
        root.close()

    # See that all 5 clean-ups have had a chance to run.
    assert cleaned_up == [4, 3, 2, 1, 0]


def test_injector_low_level_api():
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

class Unauthenticated(RuntimeError):
    pass
