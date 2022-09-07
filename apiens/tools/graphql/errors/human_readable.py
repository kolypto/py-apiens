""" Make GraphQL errors more human-readable.

This module improves the way Int, Float and Bool objects report errors.
The new error message is human-readable and can be reported to the end-user.

Before: 

> 'message': "Int cannot represent non-integer value: 'INVALID'",

After:

> 'message': "Not a valid number",  # Improved, human-readable
"""

from typing import Any

import graphql.type.scalars
import graphql.type.definition

from apiens.translate import _


def install_types_to_schema(schema: graphql.GraphQLSchema):
    """ Augment built-in types with user-friendly error messages

    This function will replace parsers for: Int, Float, Bool, etc
    with an alternative version that returns better, user-friendly, and structured, error messages.
    """
    for type_name, parse_value_func in SCALAR_PARSE_VALUE_MAP.items():
        type: graphql.GraphQLScalarType = schema.type_map.get(type_name)  # type: ignore[assignment]
        if type is not None:
            type.parse_value = parse_value_func  # type: ignore[assignment]


def coerce_int(input_value: Any) -> int:
    try:
        return graphql.type.scalars.coerce_int(input_value)
        # return pydantic.validators.int_validator(input_value)
    except graphql.GraphQLError as e:
        raise graphql.GraphQLError(_('Not a valid number')) from e


def coerce_float(input_value: Any) -> float:
    try:
        return graphql.type.scalars.coerce_float(input_value)
        # return pydantic.validators.float_validator(input_value)
    except graphql.GraphQLError as e:
        raise graphql.GraphQLError(_('Not a valid number')) from e


def coerce_bool(input_value: Any) -> bool:
    try:
        return graphql.type.scalars.coerce_boolean(input_value)
    except graphql.GraphQLError as e:
        raise graphql.GraphQLError(_('Not a valid yes/no value')) from e


SCALAR_PARSE_VALUE_MAP = {
    'Int': coerce_int,
    'Float': coerce_float,
    'Boolean': coerce_bool,
}
