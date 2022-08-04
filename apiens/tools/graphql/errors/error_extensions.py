
import re
import graphql

from apiens.error import exc
from apiens.error.error_object.python import ErrorObject
from .error_convert import unwrap_graphql_error


def add_graphql_error_extensions(error: graphql.GraphQLError, debug: bool = False, BaseApplicationError = exc.BaseApplicationError) -> dict:
    """ Add extensions to a GraphQL error. Use it before returning the error to the user.
    
    This is what gets added:
    * "error" for Application Errors
    * "validation" for query schema validation errors
    """
    # Make sure it's a dict. Otherwise we wouldn't be able to add anything there.
    if not error.extensions:
        error.extensions = {}

    # Augmentations: add extensions to the error message
    # TODO: should these be implemented as extensions?
    augment_application_error(error, debug=debug, BaseApplicationError=BaseApplicationError)
    augment_validation_error(error)

    return error


def augment_application_error(error: graphql.GraphQLError, *, debug: bool = False, BaseApplicationError=exc.BaseApplicationError):
    """ Augment GraphQL error: when it's an Application Error, add the "error" extension field """
    assert error.extensions is not None

    # Only once
    if 'error' in error.extensions:
        return

    # Get the application error
    original_error = unwrap_graphql_error(error)
    if isinstance(original_error, BaseApplicationError):
        # Augment
        error.extensions['error'] = _export_jsonable_application_error_object(original_error, include_debug_info=debug)


def augment_validation_error(error: graphql.GraphQLError):
    """ Augment GraphQL error: if it's a validation error (i.e. standard GraphQL schema validation message), make sure its structured
    
    This function takes messages like "Variable <x> got invalid value <y>"
    And adds the following key to the extensions: 
        {
            "validation": {
                variable: "x", 
                path: ["x"], 
                message: "Invalid value"
            }
        }

    See error_extensions.graphql
    """
    assert error.extensions is not None

    # Only once
    if 'validation' in error.extensions:  # type: ignore[operator]
        return

    # Is it a validation error?
    # NOTE: this is a horrible pattern-matching solution, but currently the only way to properly implement this behavior would be
    # to hack `coerce_input_value`, because that's the only place where `path` is still available as a structure,
    # and then hack into graphql `coerce_variable_values` to make sure that extra information is not lost as it is passed
    # upwards to the graphql `get_variable_values`.
    # When graphql library stops using hidden closures, we can stop parsing the error message.
    m = VALIDATION_ERROR_REX.fullmatch(error.message)
    if m is None:
        return

    # Augment
    # NOTE: $variable name can be extracted from `node.variable.name.value` if isinstance(error.nodes[i], graphql.VariableDefinitionNode)
    path = m['path'].split('.') if m['path'] else (m['var'],)
    error.extensions['validation'] = {
        'variable': m['var'],
        'path': tuple(path),
        'message': m['msg'],
    }


# Test: GraphQL is a validation error message.
# Example: when the variable itself fails validation:
#     "Variable '$age' got invalid value 'INVALID'; Not a valid number"
# Example: when a nested field fails validation.
#     "Variable '$user' got invalid value 'INVALID' at 'user.age'; Not a valid number"
# Example: when a custom validator throws a Python error
#     "Variable '$user' got invalid value -1 at 'user.positiveAge'; Expected type 'PositiveInt'. Must be positive"
VALIDATION_ERROR_REX = re.compile(
    r"Variable '\$(?P<var>.+)' "
    r"got invalid value (?:.* at '(?P<path>[^']+)'|.*)"
    r"; (?:Expected type '[^']+'\. )?(?P<msg>.*)"
)


def _export_jsonable_application_error_object(e: exc.BaseApplicationError, *, include_debug_info: bool) -> ErrorObject:
    """ Convert an Application Error to a jsonable dict """
    error_object = e.dict(include_debug_info=include_debug_info)

    # NOTE: error objects may contain references to: dates, enums, etc. These have to be jsonable encoded.
    # TODO: it's probably not a good idea to invoke FastAPI here thus adding it as a dependency, but at the moment, I've found no better way to do this.
    #   Perhaps, have it as an optional dependency, with a fallback to pydantic, and json?
    if fastapi is not None:
        error_object = fastapi.encoders.jsonable_encoder(error_object)

    return error_object


try:
    import fastapi.encoders
except ImportError:
    fastapi = None  # type: ignore[assignment]
