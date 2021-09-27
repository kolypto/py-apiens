from __future__ import annotations

from typing import TypedDict, Optional


class ErrorResponse(TypedDict):
    """ Error response, as returned by the API """
    error: ErrorObject


class ErrorObject(TypedDict):
    """ JSON Error: JSON representation of an application error """
    # Error name: E_* or F_*
    name: str

    # Generic error title. Comes from the error class
    title: str

    # HTTP code for the error
    httpcode: int

    # Error description: what went wrong
    error: str

    # Error suggestion: what can you do to fix it
    fixit: str

    # Additional data
    info: dict

    # Debug data. Not available in production.
    debug: Optional[dict]


class GraphqlResponseErrorObject(TypedDict):
    """ JSON Error: JSON representation of a GraphQL error.

    These errors are normally GraphQL-related: structural failures within the request or the response.
    """
    # Error message, string
    message: str

    # Error path: the field that has raised it
    path: Optional[list[str]]

    # Error locations: ?
    locations: Optional[str]

    # Extra information
    extensions: GraphqlErrorExtensionsObject


class GraphqlErrorExtensionsObject(TypedDict):
    """ GraphQL errors[*].extensions

    Every GraphQL error can have additional fields, but there are all in a so-called "json junk drawer":
    a special attribute that holds all of them.

    Prevent uses this attribute, "extensions", to store additional information about a Python exception,
    such as: exception stack trace, exception context ("pre-request", "post-request", ...)
    """
    # (only in debug mode) Python exception: context, stacktrace
    exception: Optional[dict]

    # (optionally) set when the error happened outside of GraphQL: in pre-request and post-request hooks
    # Examples include: "before-request", "clean-up", ...
    where: Optional[str]

    # Prevent Error Object: the error itself, with its name, error message, fixit, and informational data
    error: Optional[ErrorObject]
