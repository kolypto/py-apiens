[![Test](https://github.com/kolypto/py-apiens/workflows/Test/badge.svg)](/kolypto/py-apiens/actions)
[![Pythons](https://img.shields.io/badge/python-3.9%E2%80%933.10-blue.svg)](noxfile.py)

Apiens
======

Apiens (API sapiens) is a collection of tools for developing API applications with FastAPI and/or GraphQL.

It includes some solutions and best practices for:

* Application configuration with env variables
* Error reporting with error codenames and structured error info
* Failsafe tools to help write better async code
* SqlAlchemy tools for loading, saving, and inspecting objects

Because this library is not a framework but a collection of tools, our docs start with a guide.
We'll create a new application :)






Guide
=====
We will build a new GraphQL application that sits on top of FastAPI application.

Demo application sources are available under [misc/readme-app](misc/readme-app/).






## Application Configuration: Environment Variables
Our application will support 3 running modes:

1. `dev`: Development mode. Your code can enable some debugging features when this mode is on.
2. `prod`: Production mode. All debugging features are disabled.
3. `test:` Testing mode. Used when running unit-tests.

The current environment is determined by the `ENV` environment variable. Like this:

```console
$ ENV=prod app run 
```






### Configuration file
Our configuration will live in a module as a variable that's easy to import like this:

```python
from app.globals.config import settings
```

Here's the module:

```python
# config.py

import pydantic as pd

class Settings(pd.BaseSettings):
    """ Application settings """
    # Human-readable name of this project
    # Used in titles, emails & stuff
    PROJECT_NAME: str = 'My Application'

    class Config:
        # Use this prefix for environment variable names.
        env_prefix = 'APP_'
        case_sensitive = True


# Load default environment values from .env files.
from apiens.tools.settings import (
    set_default_environment, 
    load_environment_defaults_for, 
    switch_environment_when_running_tests,
)
set_default_environment('APP_ENV', default_environment='dev')  
load_environment_defaults_for('APP_ENV')
switch_environment_when_running_tests('APP_ENV')


# Init settings
settings = Settings()
```






### DotEnv files
The application will read its configuration from environment variables, but will also load the following dotenv files:

* `/misc/env/{name}.env`: Configuration variables' values
* `/misc/env.local/{name}.env`: Configuration overrides for running in the so-called "local mode" (see below)
* `/.{name}.env`: Ad-hoc variable value overrides

So, if your current environment is

```console
$ export ENV=dev && cd ~/code/myapp 
```

Then it will:

* Load `/misc/env/dev.env`
* Load `/misc/env.local/dev.env` (only when running locally)
* Load `/.dev.env` (only when running locally)
* Read variable values from the environment and override any previous values

This logic is implemented in the [`load_environment_defaults_for()`](apiens/tools/settings/env.py).







### Running Locally
When your application runs in Docker, it needs to use `postgres` as the host name. 
However, when you run the same application locally, on your host, it needs to use `localhost` as the host name.

To support the "local" running mode, we have this `/misc/env.local` folder. 
To activate this mode, use the following `.envrc` [direnv](https://direnv.net/) file:

```bash
#!/bin/bash
export ENV_RUNNING_LOCALLY=1
```






### direnv file
Okay, while we're at it, here's a `.envrc` file that will load all `.env` files into the current environment:

```bash
#!/bin/bash

# auto-set the environment
[ -z "${APP_ENV}" ] && export APP_ENV='dev'

# auto-load .env into the environment
[ -f "misc/envs/${APP_ENV}.env" ] && dotenv "misc/envs/${APP_ENV}.env"
[ -f "misc/envs.local/${APP_ENV}.env" ] && dotenv "misc/envs.local/${APP_ENV}.env"
[ -f ".${APP_ENV}.env" ] && dotenv ".${APP_ENV}.env"

# Indicate that we are running locally (not in Docker)
export ENV_RUNNING_LOCALLY=1

# Custom PS1
# Your shell must have an "echo -n $CUSTOM_PS1" in order for this to work
export CUSTOM_PS1="$PREVENT_ENV: "

# Automatically activate poetry virtualenv
if [[ -f "pyproject.toml" ]]; then
    # create venv if it doesn't exist; then print the path to this virtualenv
    export VIRTUAL_ENV=$(poetry run true && poetry env info --path)
    export POETRY_ACTIVE=1
    PATH_add "$VIRTUAL_ENV/bin"
    echo "Activated Poetry virtualenv: $(basename "$VIRTUAL_ENV")"
fi
```






### Configuration Mixins
The [tools.settings.mixins](apiens/tools/settings/mixins.py) provides some mixin classes for your `Settings` class.

The `EnvMixin` allows you to check the current environment, like this:

```python
if not settings.is_production:
    ...  # add more debugging information
```

The `LocaleMixin` is a convenience for storing the current locale (language) and timezone:

```python
settings.LOCALE  # -> 'en'
settings.TZ  # -> 'Europe/Moscow'
```

The `DomainMixin` and `CorsMixin` help you configure your web application for allowed Hosts and CORS checks:

```python
settings.SERVER_URL  # -> 'https://example.com/'
settings.CORS_ORIGINS  # -> ['https://example.com', 'https://example.com:443']
```

The `SecretMixin` is for keeping your application's secret key for encryption and stuff:

```python
settings.SECRET_KEY  # -> '...'
```

The `PostgresMixin` reads Postgres configuration from the environment variables you also use for the Docker container:

```python
# Read from the environment:
settings.POSTGRES_HOST  # -> 'localhost'
# Generated:
settings.POSTGRES_URL  # -> 'postgres://user:pass@localhost:port/'
```

The `RedisMixin` reads Redis configuration:

```python
settings.REDIS_URL  # -> 'redis://@localhost/0
```

Now, in our Demo application, we'll use some mixins to get a Postgres connection and settings for the web application:

```python
# config.py
class Settings(EnvMixin, DomainMixin, CorsMixin, PostgresMixin, pd.BaseSettings):
    """ Application settings """

    # Human-readable name of this project
    # Used in titles, emails & stuff
    PROJECT_NAME: str = 'My Application'

    class Config:
        # Use this prefix for environment variable names.
        env_prefix = 'APP_'
        case_sensitive = True
```






### DotEnv files
Now, when we have the `Settings` class that reads our configuration into `config.settings`, 
we need to give it the actual configuration values.

These values can come from the environment:

```python
$ ENV=dev POSTGRES_HOST=localhost POSTGRES_PORT=54321 APP_SERVER_URL=http://localhost/ app run
```

but surely this is too verbose.

Instead, we'll create DotEnv files under `misc/env`:

```env
# misc/env/dev.env
ENV=dev

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=app

APP_SERVER_URL=http://localhost
APP_CORS_ORIGINS=http://localhost
```

And another one, for unit-tests:

```env
ENV=test

POSTGRES_HOST=localhost
POSTGRES_PORT=54321
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=app_test

APP_SERVER_URL=http://localhost
APP_CORS_ORIGINS=http://localhost
```

Note that a different database should be used for unit-tests: otherwise every test run would overwrite your local database =\






## Database init
Let's configure a Postgres database using our configuration:

```python
# postgres.py
from collections import abc
import sqlalchemy as sa

from apiens.tools.settings import unit

# Import settings
from app.globals.config import settings


# Prepare some units for readability
min = unit('minute')
sec = unit('second')

# Initialize SqlAlchemy Engine: the connection pool
engine: sa.engine.Engine = sa.create_engine(
    # Use settings
    settings.POSTGRES_URL,
    future=True,
    # Configure the pool of connections
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    # Use `unit` to make the value more readable
    pool_recycle=10 * min >> sec,
)

# Initialize the SessionMaker: the way to get a SqlAlchemy Session
from sqlalchemy.orm import Session
SessionMakerFn = abc.Callable[[], Session]

SessionMaker: SessionMakerFn = sa.orm.sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
```

Thanks to `settings` being a module variable, we can just import it, and initialize our database as module variables.
Now, your code can use the database like this:

```python
from app.globals.postgres import SessionMaker

with SessionMaker() as ssn:
    ...  # do your stuff
```






### DB Connection Pool
It's really important to use `SessionMaker` as a context manager: because this way you make sure that every connection
you've checked out will then be returned to the pool for reuse.

However, if you used your sessions like this:

```python
ssn = SessionMaker()
...
ssn.close()
```

There is a chance that an exception will be raised before you do `ssn.close()` and the connection will remain checked out.
Such a connection will waste the limited resources of the pool and your application will malfunction.

Because it's so important to make sure that every checked out connection is returned to the pool, 
we add a piece of code that users [`TrackingSessionMaker`](apiens/tools/sqlalchemy/session/session_tracking.py) 
that checks whether all your SqlAlchemy connections have been properly closed:

```python
# In testing, make sure that every connection is properly closed.
if settings.is_testing:
    # Prepare a new SessionMaker that tracks every opened connection
    from apiens.tools.sqlalchemy.session.session_tracking import TrackingSessionMaker
    SessionMaker = TrackingSessionMaker(class_=SessionMaker.class_, **SessionMaker.kw)

    # Define a function for unit-tests: check that all Sessions were properly close()d
    def assert_no_active_sqlalchemy_sessions():
        SessionMaker.assert_no_active_sessions()  
# postgres.py
...
# In testing, make sure that every connection is properly closed.
if settings.is_testing:
    # Prepare a new SessionMaker that tracks every opened connection
    from apiens.tools.sqlalchemy.session.session_tracking import TrackingSessionMaker
    SessionMaker = TrackingSessionMaker(class_=SessionMaker.class_, **SessionMaker.kw)

    # Define a function for unit-tests: check that all Sessions were properly close()d
    def assert_no_active_sqlalchemy_sessions():
        SessionMaker.assert_no_active_sessions()  
```

This code defines a function, `assert_no_active_sqlalchemy_sessions()`, that should be run after each unit-test.
If your code hasn't `close()`d a Session, this function will find a dangling Session and complain.

This is your safeguard against connections left open unintentionally.






## Structured Errors
This is how default FastAPI errors look like:

```javascript
{
    detail: "Not Found"
}
```

and this is how default GraphQL errors look like:

```javascript
{
  //...
  "errors": [
    {
      "message": "Fail",
      "path": ["unexpected_error"],
      "extensions": {
        "exception": {
          "stacktrace": ["Traceback", "File ..., line ... in execute_field"],
          "context": {/*...*/}
        }
      }
    }
  ]
}
```

This is ok for developers, but not for the UI: in order to learn what has happened, the UI would have to parse error message.

Apiens offers *structured errors*: errors where every error has a codename.






### Application Errors
With Apiens, you'll have two types of exceptions:

* Ordinary Python exceptions: seen as *unexpected errors*
* Application Errors: errors that are meant to be reported to the API user

Application errors inherit from [BaseApplicationError](apiens/error/base.py) and have the following fields:

* `error`: The negative message: what has gone wrong.
* `fixit`: The positive message: what the user can do to fix it (user-friendly)

    Thus, every error will have two messages: one for developers, and the other one -- for users.

* `name`: Error codename: the name of the class. E.g. "E_NOT_FOUND". 

    This is the machine-readable codename for the error that the UI can use to react to it.

* `title`: Generic name for the error class that does not depend on the context. E.g. "not found".
* `httpcode`: The HTTP code to use for this error (when in HTTP context)
* `info`: Additional structured information about the error
* `debug`: Additional structured information, only included when the app is not in production

Application errors can be raised like this:

```python
from apiens.error import exc

raise exc.E_NOT_FOUND(
    # Error: the negative message
    "User not found by email",
    # Fixit: the positive message
    "Please check the provided email",
    # additional information will be included as `info`
    object='User',
    email='user@example.com',
)
```

Such an error will be reported as structured JSON Error Object by FastAPI:

```javascript
{
    // Error response starts with the "error" key
    error: {
        // Error codename
        name: "E_NOT_FOUND",
        // Two error messages: negative `error`, and positive `fixit`
        error: "User not found by email",
        fixit: "Please check the provided email",
        // Static information
        httpcode: 404,
        title: "Not found",
        // Structured information about this error
        info: {
            // UI can use this information for display
            object: "User",
            email: "user@example.com"
        },
        debug: { }
    }
}
```

To integrate with this Application Errors framework, we first need to create a file for our application's exceptions.
For starters, we'll reuse some of the standard exceptions pre-defined in the [apiens.error.exc](apiens/error/exc.py) module:

```python
# exc.py
import apiens.error.exc

# Base class for Application Errors
from apiens.error import BaseApplicationError

# Specific application errors
# We'll reuse some errors provided by apiens
from apiens.error.exc import (
    E_API_ARGUMENT,
    E_API_ACTION,
    E_NOT_FOUND,
    F_FAIL,
    F_UNEXPECTED_ERRORS,
)
```

And then we'll install an exception handler (FastAPI) and an error formatter (GraphQL) to render such errors properly.

Because these errors are meant to be returned by the API, they have API schemas:

* <apiens/error/error_object/python.py>: TypedDict definitions for the Error Object
* <apiens/error/error_object/pydantic.py>: Pydantic definitions for the Error Object (to be used with FastAPI)
* <apiens/error/error_object/schema.graphql>: GraphQL definitions for the Error Object






### Converting Errors
By convention, every uncaught Python exception is seen as *unexpected error* and is reported as "F_UNEXPECTED_ERROR".
This is achieved using the so-called "converting" decorator/context manager:
[converting_unexpected_errors()](apiens/error/converting/exception.py)

```python
from apiens.error.converting.exception import converting_unexpected_errors

# Convert every Python exception to `F_UNEXPECTED_ERROR`
with converting_unexpected_errors():
    raise RuntimeError('Fail')
```

In some cases you may want to customize how a Python error gets converted into an Application error:
for instance, you may have an API client with custom errors that you want to report as `F_NETWORK_SERVICE` or something.

To customize how errors are converted into application errors, define a `default_api_error()` method on them.
See [ConvertsToBaseApiExceptionInterface](apiens/error/converting/base.py) protocol.

Note that there are other *converting* decorators as well:

* [`converting_sa_errors()`](apiens/error/converting/sqlalchemy.py) converts SqlAlchemy errors: 
  for instance, `sa.orm.exc.NoResultFound` gets converted into `E_NOT_FOUND`, and `UniqueViolation` into `E_CONFLICT_DUPLICATE`.
* [`converting_jessiql_errors()`](apiens/error/converting/jessiql.py) converts JessiQL errors into `E_API_ARGUMENT`.
* [`converting_apiens_errors()`](apiens/error/converting/apiens.py)






## FastAPI application
Let's start by putting together a FastAPI application.

```python
# fastapi/app.py
from fastapi import FastAPI

from app.globals.config import settings


# ASGI app
asgi_app = FastAPI(
    title=settings.PROJECT_NAME,
    description=""" Test app """,
    # `settings` controls debug mode of FastAPI
    debug=not settings.is_production,
)

# Attach GraphQL routes
from app.expose.graphql.app import graphql_app
asgi_app.mount('/graphql/', graphql_app)
```

This part of the application is pretty straightforward: we initialized an ASGI application,
and mounted a GraphQL ASGI application onto `/graphql/` route.

Let's see how such an API reports a `RuntimeError`:

```javascript
Internal Server Error
```

By adding using [`register_application_exception_handlers()`](apiens/tools/fastapi/exception_handlers.py),
we can improve the way errors are reported: they will become structured Application Errors:

```python
# fastapi/app.py
from apiens.tools.fastapi.exception_handlers import register_application_exception_handlers
register_application_exception_handlers(asgi_app, passthru=settings.is_testing)
```

They will:

* Report every error as `F_UNEXPECTED_ERROR`
* Report FastAPI validation errors as `E_CLIENT_VALIDATION` 
* Report every application error as proper JSON object
* For invalid urls ("route not found"), will generate a list of suggested API paths 






## GraphQL application

Let's start a GraphQL application. First, we create a GraphQL schema, and then create an ASGI application
that serves the schema. 






### GraphQL Schema

```python
# graphql/schema.py

import os
import ariadne

import apiens.error.error_object
from apiens.tools.ariadne.schema.load import load_schema_from_module

app_schema = ariadne.make_executable_schema([
        # Load all *.graphql files from this folder
        ariadne.load_schema_from_path(os.path.dirname(__file__)),
        # Load a *.graphql file from a module
        load_schema_from_module(apiens.error.error_object, 'schema.graphql'),
    ],
    graphql_definitions,
    ariadne.snake_case_fallback_resolvers,
)
```

Let's add a few more line to improve how `Int` and `Float` errors are reported:
human-readable error messages are implemented by 
[`human_readable.install_types_to_schema()`](apiens/tools/graphql/errors/human_readable.py)
that overrides some built-in resolvers with user-friendly error messages that can now be used in the UI:

```python
# graphql/schema.py

# Improve error messages from scalars like Int and Float
from apiens.tools.graphql.errors import human_readable
human_readable.install_types_to_schema(app_schema)
```

This module, `human_readable`, improves the 

Before: 

> 'message': "Int cannot represent non-integer value: 'INVALID'",

After:

> 'message': "Not a valid number",  # Improved, human-readable






### GraphQL ASGI Application

Now we need to create an ASGI application.

This is necessary because the GraphQL schema knows nothing about HTTP requests, JSON payload, etc.
This ASGI application takes JSON data from the request body and passes it to the schema for execution.
The schema gives the response, which is converted into HTTP JSON response and sent to the client.

So, let's init this application with Ariadne:

```python
from ariadne.asgi import GraphQL
from apiens.tools.graphql.middleware.documented_errors import documented_errors_middleware
from apiens.tools.graphql.middleware.unexpected_errors import unexpected_errors_middleware
from apiens.tools.ariadne.errors.format_error import application_error_formatter

from app.globals.config import settings
from app import exc
from .schema import app_schema


# Init the ASGI application
graphql_app = GraphQL(
    # The schema to execute operations against
    schema=app_schema,
    # The context value. None yet.
    context_value=None,
    # Error formatter presents Application Errors as proper JSON Error Objects
    error_formatter=application_error_formatter,
    # Developer features are only available when not in production
    introspection=not settings.is_production,
    debug=not settings.is_production,
    # Some middleware
    middleware=[
        # This middleware makes sure that every application error is documented.
        # That is, if `E_NOT_FOUND` can be returned by your `getUserById`, 
        # then its docstring should contain something like this:
        # > Errors: E_NOT_FOUND: the user is not found
        documented_errors_middleware(exc=exc),

        # Converts every Python exception into F_UNEXPECTED_ERROR.
        # Users `converting_unexpected_errors()`
        unexpected_errors_middleware(exc=exc),
    ],
)
```

The main part is where the ASGI application gets the `schema`.

Let's have a closer look at the `middleware` and the `error_formatter` keys.





#### GraphQL Middleware

This initializer mentions two middlewares:

* [`documented_errors_middleware`](apiens/tools/graphql/middleware/documented_errors.py) 
  requires that every Application Error is documented. 
  That is, if your field raises `E_NOT_FOUND`, your field's docstring must contain something like

  > Error: E_NOT_FOUND: the user is not found

  The middleware simply checks whether the docstring of the field, or the parent object, 
  mentions the error by name. This simple check makes sure that the UI won't get any surprises
  from your GraphQL API: it will know exactly which errors it should expect.

  If an error is undocumented, an additional error is reported.

* [`unexpected_errors_middleware`](apiens/tools/graphql/middleware/unexpected_errors.py) 
  converts every Python exception into `F_UNEXPECTED_ERROR`.
  This basically makes sure that unexpected errors are also reported as application errors.






#### GraphQL Error Formatter
This ASGI application initializer also has a custom error formatter.

The error formatter, [`application_error_formatter`](apiens/tools/ariadne/errors/format_error.py), is a function that gets a `GraphQLError`
and adds a key to `'extensions'` with additional information about this error.
Namely, if it's an Application Error, it will contain its `name`, `error`, `fixit`, and other fields.

Before:

```javascript
{
  "errors": [
    {
      "message": "Fail",
      "path": ["unexpected_error"],
      "extensions": {
        "exception": {
          // Python traceback
          "stacktrace": ["Traceback:", "..."],
        }
      }
    }
  ]
}
```

After:

```javascript
{
  "errors": [
    {
      "message": "Fail",
      "path": ["unexpected_error"],
      "extensions": {
        // The Error Object: additional, structured, information about the error
        "error": {
          // Error codename
          "name": "F_UNEXPECTED_ERROR",
          // Static information: http code, error message
          "httpcode": 500,
          "title": "Generic server error",
          // Two error messages: negative, and positive
          "error": "Fail",
          "fixit": "Please try again in a couple of minutes. If the error does not go away, contact support and describe the issue",
          // Additional structured information, if any 
          "info": {},
          // Additional debug information (only included in non-production mode)
          "debug": {
            "errors": [
              {
                // The original Python exception
                "type": "RuntimeError",
                "msg": "Fail",
                // Easy-to-read traceback
                "trace": [
                  "middleware/unexpected_errors.py:unexpected_errors_middleware_impl",
                  "middleware/documented_errors.py:middleware",
                  "graphql/query.py:resolve_unexpected_error"
                ]
              }
            ]
          }
        },
        "exception": {
          "stacktrace": ["Traceback:", "..."],
        }
      }
    }
  ]
}
```

It also fixes some validation errors to be more readable: 
original validation errors look like this:

> Variable '$user' got invalid value -1 at 'user.age'; Expected type 'PositiveInt'. Must be positive

Such error messages are converted into:

```javascript
{
  // The message is now human-readable
  'message': "Must be positive",
  'extensions': {
    // Validation error is returned as structured data
    'validation': {
      'variable': '$user',
      'path': ['user', 'age'],
    }
  }
}
```






### Resolver Markers

Let's implement a resolver.
A resolver is a Python function that gets called to provide a value for the field:

```python
import ariadne

Query = ariadne.QueryType()

@Query.field('hello')
def resolve_hello(_, info: ResolveInfo):
    return 'Welcome'
```

Not here's the catch: your resolver will get executed inside the async loop.
It's fine when you use `async` functions or functions that do not block.

However, if your sync resolver function is blocking -- i.e. is I/O bound or CPU bound -- 
then you cannot just use it like this: it would block the whole asyncio loop!

You need to run it in a threadpool, like this:

```python
from apiens.tools.python.threadpool import runs_in_threadpool

@runs_in_threadpool
def resolve_something(_, info):
    with SessionMaker() as ssn:
        something = ssn.query(...).one()  # blocking!!!      
```

This thing is, probably, **the** most important to know about async applications.
Because it is so important to remember this decorator, the Apiens library provides a way to make sure
that developers do not forget about this issue.

It provides three decorators:

* [`@resolves_in_threadpool`](apiens/tools/graphql/resolver/resolver_marker.py)
  to decorate a blocking sync function that will be run in a threadpool.
* [`@resolves_nonblocking`](apiens/tools/graphql/resolver/resolver_marker.py)
  to decorate a sync function that promises not to block (i.e. do no networking and such)
* [`@resolves_async`](apiens/tools/graphql/resolver/resolver_marker.py)
  -- an optional decorator for async functions. Just for completeness.

And a unit-test tool to make sure that your schema has every resolver decorated:

```python
# tests/test_api.py


from app.expose.graphql.schema import app_schema
from apiens.tools.graphql.resolver.resolver_marker import assert_no_unmarked_resolvers


def test_no_unmarked_resolvers():
    """ Make sure that every resolver is properly decorated. """
    assert_no_unmarked_resolvers(app_schema)

```

If any resolver is not decorated, the unit-test would fail like this:

> AssertionError: Some of your resolvers are not properly marked. Please decorate with either @resolves_in_threadpool or @resolves_nonblocking. 
>
> List of undecorated resolvers:      
> \* resolve_hello (module: app.expose.graphql.query)
 




## Testing

We'll start with configuring an API client to make requests to our API.

Now, there are two ways to make there requests:

1. We can execute operations against the GraphQL `schema` through `schema.execute()`.

  In this case, we need to provide the `context` value as if the request has come from some HTTP request (because GraphQL does not know anything about HTTP).

  Such a test would verify that your business-logic works, but won't make sure that your application 
  correctly integrates with the HTTP layer.

2. We can execute requests through the FastAPI stack and GraphQL ASGI application. 
  
  This test involves the whole application stack, but it's slower to set up, and may lose some valuable information
  about exceptions because they are converted into JSON.

The recommendation is to unit-test the GraphQL application because it's faster and more flexible,
but also pick some key APIs and unit-test their features involving the whole stack. This is especially true about
any APIs that are supposed to use cookies, authentication, user state, and HTTP headers.

Let's start by defining a GraphQL client and an API client in `conftest.py`.






### GraphQL client

Apiens provides a convenient [GraphQLTestClient](apiens/tools/graphql/testing/test_client.py) client 
for testing operations against your graphql schema:

```python
# tests/conftest.py

from app.expose.graphql.schema import app_schema
from apiens.tools.graphql.testing import test_client


class GraphQLClient(test_client.GraphQLTestClient):
    def __init__(self):
        super().__init__(schema=app_schema, debug=True)

    # The GraphQL unit test needs to initialize its own context for the request.
    @contextmanager
    def init_context_sync(self):
        yield {}

@pytest.fixture()
def graphql_client() -> GraphQLClient:
    """ Test client for GraphQL schema """
    with GraphQLClient() as c:
        yield c
```

When you run GraphQL queries with this test client, you can benefit from the augmented 
[`GraphQLResult`](apiens/tools/graphql/testing/query.py) result object:

```python
# tests/test_hello.py

from .conftest import GraphQLClient, ApiClient

def test_hello(graphql_client: GraphQLClient):
    q_hello = """
        query {
            hello
        }
    """

    # Execute operation, inspect response
    res = graphql_client.execute(q_hello)
    assert res.data['hello'] == 'Welcome'

    # Execute operation, inspect response, expect it to be successful.
    # This shortcut res['hello'] would raise any exceptions that may have happened.
    res = graphql_client.execute(q_hello)
    assert res['hello'] == 'Welcome'
```

In addition to this `res[fieldName]` shortcut, [`GraphQLResult`](apiens/tools/graphql/testing/query.py) result object
offers some more features:

* `data`: the dict with results
* `errors`: the list of reported errors (as JSON)
* `exceptions`: the list of original Python exception objects (not JSON). Useful for re-raising.
* `context`: the context used for the request. Useful for post-mortem inspection.
* `ok`: was the request successful (i.e. did it go without errors?)
* `raise_errors()`: raise any Python exceptions that may have happened.
* `app_error_name`: get the name of the application error (e.g. `"E_NOT_FOUND"`)
* Also see: `app_error`, `original_error`, `graphql_error` properties that help inspect the returned error:






### FastAPI client

Now we need another client that unit-tests APIs and involves the whole stack, i.e. the FastAPI application.
In fact, you can use the ordinary `fastapi.testing.TestClient`, but it will be quite inconvenient to use it 
for testing a GraphQL application: you'd have to prepare request dict every time, and you'll get errors
reported as JSON.

Apiens provides a [GraphQLClientMixin](apiens/tools/graphql/testing/test_client_api.py) mixin for your test class
that adds methods for executing GraphQL requests through FastAPI's test client's `post()`, 
and even uses a few tricks to make sure that you can get the original Python exception 
(rather than formatter exception JSON):

```python
# tests/conftest.py
from app.expose.graphql.schema import app_schema
from apiens.tools.graphql.testing import test_client_api


# FastAPI test client, with a mixin that supports GraphQL requests
class ApiClient(test_client_api.GraphQLClientMixin, TestClient):
    GRAPHQL_ENDPOINT = '/graphql/'

@pytest.fixture()
def api_client() -> ApiClient:
    """ Test client for FastAPI, with GraphQL capabilities """
    with ApiClient(asgi_app) as c:
        yield c
```

Here's how this client is used:

```python
# tests/test_hello.py

def test_hello_api(api_client: ApiClient):
    """ Test hello() on FastAPI GraphQL endpoint """
    #language=GraphQL
    q_hello = """
        query {
            hello
        }
    """

    res = api_client.graphql_sync(q_hello)
    assert res['hello'] == 'Welcome'
```











Special Tools
=============

We've built a FastAPI-GraphQL application with the tools from Apiens. 
As you see, it's not a framework, but a set of tools that address specific issues to make your API
a sweet solution to use :) 

The rest of the document will describe specific tools that you may find useful here and there.
Let's first see more unit-testing tools.






## Unit-Testing Tools






### Network Gag
Your application likely uses some network services, and it's important to make sure 
that in your unit-tests they all are properly mocked. That is, to make sure that your unit-tests
make no real network connections!

The [network_gag](apiens/testing/network_gag.py) provides a decorator (and a context manager)
that makes sure that your code does no network connections through urllib, aiohttp, or amazon client:

```python
with network_gag():
    ... # do your stuff without networking
```

If your code attempts to communicate with the Internet, the gag would give you an exception: 

> This unit-test has attempted to communicate with the Internet
> URL: http://service.mock/api/method
> Please use the `responses` library to mock HTTP in your tests. 
> Cheers!

With pytest it's more convenient to use [network_gag_conftest](apiens/testing/network_gag_conftest.py).
Just import this fixture into your `conftest.py`:

```python
# conftest.py

# Network gag
from apiens.testing.network_gag_conftest import stop_all_network, unstop_all_network
```

Now, if any unit-test attempts to communicate with the Internet, you'll get an exception.
However, if some specific test needs to allow networking, use this mark:

```python
import pytest

@pytest.mark.makes_real_network_connections
def test_something_with_networking():
  ...
```





### Object Match

Lets see a situation where simple `assert result == value` is not enough.

Suppose your unit-test verifies the response of some API:

```python
res = execute_api_request()
assert res == {
    'user': {
        'id': 19,
        'login': 'kolypto',
        'name': 'Mark',
    }
}
```

assertions work fine with static data like the `'login'` string there. 
But this `'id'` is a dynamic value likely returned from some database and you cannot really
check equality like that.

When a dynamic value is inserted into a static structure with nested fields, 
developers have to inspect the response key by key:

```python
res = execute_api_request()
assert res['user']['id'] > 0  # inspect the dynamic field
assert res['user']['login'] == 'kolypto'
assert res['user']['name'] == 'Mark'
```

or modify the response to keep it static:

```python
res = execute_api_request()
user_id = res['user'].pop('id')  # pop the dynamic field
assert res == {
  'user': {
    'login': 'kolypto',
    'name': 'Mark',
  }
}
assert user_id > 0
```

You've done this before, have you? :) 

Apiens offers several ways to unit-test dynamic values within complex structures.

In some cases, you don't really care which exact value is there. You just want to ignore it.
Use the [`Whatever`](apiens/testing/object_match/okok.py) object: when compared to anything,
it gives a `True`:

```python
res = execute_api_request()
assert res == {
    'user': {
        # Ignore the value: equality always give True
        'id': Whatever,
        'login': 'kolypto',
        'name': 'Mark',
    }
}
```

If you do actually care which value is there and want to inspect it, 
use [check()](apiens/testing/object_match/check.py) with a lambda function that will perform
the test when the two values are compared to one another:

```python
res = execute_api_request()
assert res == {
    'user': {
        # Use a lambda function to test the value
        'id': check(lambda v: v>0),
        'login': 'kolypto',
        'name': 'Mark',
    }
}
```

If you actually want to use the nested value in some more complicated context, you can actually
*capture the value* using [Parameter()](apiens/testing/object_match/parameter.py):
this object captures the value while being compared to it:

```python
res = execute_api_request()
assert res == {
    'user': {
        # Capture the value into a variable
        'id': (user_id := Parameter()),
        'login': 'kolypto',
        'name': 'Mark',
    }
}

# Use the value
assert user_id.value > 0
print(user_id.value)
```

If your trouble is not about one value but rather about ignoring a whole bunch of dict keys,
use [`DictMatch`](apiens/testing/object_match/dict_match.py) for partial dict matching:

```python
res = execute_api_request()
assert res == {
    # Partial dict match: only named keys are compared
    'user': DictMatch({
        'login': 'kolypto',
        'name': 'Mark',
    })
}
```

There also is [`ObjectMatch`](apiens/testing/object_match/object_match.py) for parial object matching:
it only inspects the attributes that you've named, ignoring all the rest:

```python
# Create an object with some attributes
from collections import namedtuple
Point = namedtuple('Point', ('x', 'y'))
point = Point(0, 100)

# Only inspect the 'x' attribute
assert point == ObjectMatch(x=0)
```






### Model Match
This module will help you test that your database models actually match your GraphQL definitions
and your Pydantic validation schemas. Turns out, it's so easy to make a typo in field names,
underscores, camel cases, and especially, nullable and non-nullable fields!

Suppose you have to models: a SqlAlchemy database model of a `User`:

```python
class User(Base):
    id = sa.Column(sa.Integer, primary_key=True)
    login = sa.Column(sa.String)
    password = sa.Column(sa.String)
```

and some Pydantic representation of this model, with one field missing:

```python
class UserSchema(pd.BaseModel):
    id: int 
    login: Optional[str]
    # password: not included!
```

Here's how you can compare such models to make sure you've made no typos.
First, convert every model to some intermediate shape for matching
using [`model_match.match()`](apiens/testing/model_match/match.py):

```python
# Convert every model to its intermediate shape
db_user = model_match.match(User)
pd_user = model_match.match(UserSchema)

print(str(db_user))
# -> id: !nullable required ; 
# -> login: !required nullable ; 
# -> password: !required nullable
```

You can immediately compare the two models, but note the missing field.
We need to exclude it first. This is achieved using the `select_fields()` helper 
that generates a new model:

```python
# Compare DB `User` model to Pydantic `UserSchema`    
assert pd_user == model_match.select_fields(
    # Exclude a few fields from comparison
    db_user,
    model_match.exclude('password'),
)
```

Now, if during development someone adds a field to the database model, your unit-tests would fail
and remind the developer that they need to update their pydantic schemas as well.

This is quite useful in large teams because keeping models up to date takes discipline,
and we humans always fail at discipline :) 

This [`model_match`](apiens/testing/model_match/) tool can also rewrite field names into,
say, camelCase, thus supporting your GraphQL models.
Have a look at the code: it has you covered.






## SqlAlchemy tools
This section of the docs is under development.
Please have a look at the [apiens.tools.sqlalchemy](apiens/tools/sqlalchemy/) module.

Undocumented features include:

* tools.sqlalchemy.testing, conftest
* tools.sqlalchemy.commit.commit.session_disable_commit, session_enable_commit, session_flush_instead_of_commit
* tools.sqlalchemy.commit.transaction.db_transaction
* tools.sqlalchemy.commit.save.db_flush(), db_save(), db_save_refresh(), session_safe_commit(), refresh_instances()
* tools.sqlalchemy.commit.expire.no_expire_on_commit(), commit_no_expire()
* tools.sqlalchemy.instance.instance_history_proxy
* tools.sqlalchemy.instance.modified_attrs: modified_attribute_names, modified_column_attribute_names
* tools.sqlalchemy.session.session_tracking, ssn_later
* tools.sqlalchemy.session.ssn_later
* tools.sqlalchemy.loadopt.raiseload_in_testing
* tools.sqlalchemy.types.enum
* error.converting.sqlalchemy






## Python Tools
This section of the docs is under development.
Please have a look at the [apiens.tools.python](apiens/tools/python/) module.

Undocumented features include:

* tools.python.lazy_init
* tools.python.named_exit_stack
* tools.python.threadpool






## Structuring Tools
This section of the docs is under development.
Please have a look at the [apiens.structure](apiens/structure/) module.

Undocumented features include:

* structure.titled enum
* structure.func.documented_errors
* structure.func.simple_function






## Pydantic Tools
This section of the docs is under development.
Please have a look at the [apiens.tools.pydantic](apiens/tools/pydantic/) module.

Undocumented features include:

* tools.pydantic.derive
* tools.pydantic.partial






## Web Tools
This section of the docs is under development.
Please have a look at the [apiens.tools.web](apiens/tools/web/) module.

Undocumented features include:

* tools.web.jwt_token
* tools.web.shortid






## Advanced GraphQL Tools
This section of the docs is under development.
Please have a look at the [apiens.tools.graphql](apiens/tools/graphql/) module.

Undocumented features include:

* tools.graphql.directives.*
* tools.graphql.resolver.resolve
* tools.graphql.scalars.date
* tools.graphql.schema.ast
* tools.graphql.schema.input_types
* tools.graphql.directives.*






## Advanced FastAPI Tools
This section of the docs is under development.
Please have a look at the [apiens.tools.fastapi](apiens/tools/fastapi/) module.

Undocumented features include:

* tools.fastapi.class_based_view






## Advanced Ariadne Tools
This section of the docs is under development.
Please have a look at the [apiens.tools.ariadne](apiens/tools/ariadne/) module.

Undocumented features include:

* tools.ariadne.directive
* tools.ariadne.errors
* tools.ariadne.resolver
* tools.ariadne.scalars
* tools.ariadne.schema
* tools.ariadne.testing






CRUD APIs
=========
This section of the docs is under development.
Please have a look at the [apiens.tools.crud](apiens/crud/) module.

Undocumented features include:

* crud.query
* crud.mutate
* crud.signals
* crud.settings
* error: converting jessiql, converting apiens
```
