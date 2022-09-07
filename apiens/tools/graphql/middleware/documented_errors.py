""" A middleware that makes sure that every raised error is documented in the resolver docstring """

from collections import abc
from typing import Union
from inspect import isawaitable

import graphql

from apiens.error import exc
from apiens.structure.func.documented_errors import UndocumentedError


# Error names to ignore with this middleware.
# Some errors, like unexpected server errors, should not be documented because by their nature they are unexpected :)
DEFAULT_IGNORE_ERRORS: frozenset[str] = frozenset(cls.__name__ for cls in (
    exc.F_UNEXPECTED_ERROR,
    exc.F_FAIL,
    exc.F_NOT_IMPLEMENTED,
))


def documented_errors_middleware(*, ignore_errors: frozenset[str] = DEFAULT_IGNORE_ERRORS, exc=exc) -> abc.Callable:
    """ Makes sure that every field documents application errors that it throws.

    Every application error must be documented either at the field level, or at its parent type's level.
    Documentation should look like this:

        Errors:
            E_AUTH_REQUIRED: you must be signed in in order to use this API.

    When an error is raised, this middleware would check whether the docstring of the field, 
    or the docstring of the parent object, mentions this error by name.
    If not, an UndocumentedError is raised instead.

    NOTE: it's an async middleware. It won't work with GraphQL running in sync mode (i.e. using graphql_sync())!

    Args:
        ignore_errors: The list of error names to ignore.
    """
    async def middleware(*args, **kwargs):
        return await documented_errors_middleware_impl(exc, ignore_errors, *args, **kwargs)
    return middleware


async def documented_errors_middleware_impl(exc, ignore_errors: frozenset[str], next,
                                            root, info: graphql.GraphQLResolveInfo, /,
                                            *args, **kwargs):
    # Run the handler
    try:
        res = next(root, info, *args, **kwargs)
        if isawaitable(res):
            res = await res
        return res
    # Check that the error is documented
    except exc.BaseApplicationError as e:
        error_name = e.name
        schema = info.schema
        object = info.parent_type
        field = object.fields[info.field_name]

        # Ignored error?
        if error_name in ignore_errors:
            raise

        # Documented error?
        is_documented = (
            _is_error_documented_in_field(error_name, schema, field) or
            _is_error_documented_in_object(error_name, schema, object)
        )
        if is_documented:
            raise

        # Undocumented error
        raise UndocumentedError(
            f"Undocumented error '{e.name}' for field '{object.name}.{info.field_name}'!"
            f"This project requires that every application error is documented. "
            f"Please add documentation either to the field, or to its parent type '{object.name}', or to a directive on either!"
        ) from e


def _is_error_documented_in_field(error_name: str, schema: graphql.GraphQLSchema, field: graphql.GraphQLField) -> bool:
    # For now, it just checks whether the error name is mentioned in the field's docstring.
    # It's sufficient.
    return (
        error_name in (field.description or '') or
        _is_error_documented_in_directives(error_name, schema, field.ast_node)
    )


def _is_error_documented_in_object(error_name: str, schema: graphql.GraphQLSchema, object: graphql.GraphQLObjectType) -> bool:
    return (
        error_name in (object.description or '') or
        _is_error_documented_in_directives(error_name, schema, object.ast_node)
    )


def _is_error_documented_in_directives(error_name: str, schema: graphql.GraphQLSchema, node: Union[graphql.TypeDefinitionNode, graphql.FieldDefinitionNode, None]) -> bool:
    if not node or not node.directives:
        return False

    for directive in node.directives:
        directive_def = schema.get_directive(directive.name.value)
        assert directive_def is not None

        if error_name in (directive_def.description or ''):
            return True
    else:
        return False
