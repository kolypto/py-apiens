from collections import abc
from typing import Union

import graphql

from apiens.structure.error import exc
from apiens.structure.func import UndocumentedError


# Error names to ignore with this middleware.
# Some errors, like unexpected server errors, should not be documented because by their nature they are unexpected :)
DEFAULT_IGNORE_ERRORS: frozenset[str] = frozenset(cls.__name__ for cls in (
    exc.F_UNEXPECTED_ERROR,
    exc.F_FAIL,
    exc.F_NOT_IMPLEMENTED,
))


def documented_errors_middleware(*, ignore_errors: frozenset[str] = DEFAULT_IGNORE_ERRORS) -> abc.Callable:
    """ Makes sure that every field documents application errors that it throws.

    Every application error must be documented either at the field level, or at its parent type's level.
    Documentation should look like this:

        Errors:
            E_AUTH_REQUIRED: you must be signed in in order to use this API.

    When an error is raised, this middleware would check whether docstring has it covered.
    If not, an UndocumentedError is raised instead.
    """
    def middleware(*args, **kwargs):
        return documented_errors_middleware_impl(ignore_errors, *args, **kwargs)
    return middleware


def documented_errors_middleware_impl(ignore_errors: frozenset[str], next, root, info: graphql.GraphQLResolveInfo, /, *args, **kwargs):
    # Run the handler
    try:
        return next(root, info, *args, **kwargs)
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
