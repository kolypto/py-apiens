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