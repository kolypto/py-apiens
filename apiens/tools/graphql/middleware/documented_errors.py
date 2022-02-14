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


def documented_errors_middleware(next, root, info: graphql.GraphQLResolveInfo, *args, ignore_errors: frozenset[str] = DEFAULT_IGNORE_ERRORS):
    """ Makes sure that every field documents application errors that it throws.

    Every application error must be documented either at the field level, or at its parent type's level.
    Documentation should look like this:

        Errors:
            E_AUTH_REQUIRED: you must be signed in in order to use this API.

    When an error is raised, this middleware would check whether docstring has it covered.
    If not, an UndocumentedError is raised instead.
    """
    # Run the handler
    try:
        return next(root, info, *args)
    # Check that the error is documented
    except exc.BaseApplicationError as e:
        error_name = e.name
        object = info.parent_type
        field = object.fields[info.field_name]

        # Ignored error?
        if error_name in ignore_errors:
            raise

        # Documented error?
        is_documented = (
            _is_error_documented_in_field(error_name, field) or
            _is_error_documented_in_object(error_name, object)
        )
        if is_documented:
            raise

        # Undocumented error
        raise UndocumentedError(
            f"Undocumented error '{e.name}' for field '{object.name}.{info.field_name}'!"
            f"This project requires that every field (or its parent type) contains documentation for every application error it raises. "
            f"Please add documentation either to the field, or to its parent type '{object.name}'!"
        ) from e



def _is_error_documented_in_field(error_name: str, field: graphql.GraphQLField) -> bool:
    # For now, it just checks whether the error name is mentioned in the field's docstring.
    # It's sufficient.
    return field.description is not None and error_name in field.description


def _is_error_documented_in_object(error_name: str, object: graphql.GraphQLObjectType) -> bool:
    return object.description is not None and error_name in object.description
