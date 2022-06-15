""" Tools that enable rich user-friendly validation of input data

Usage:
    from apiens.tools.ariadne.schema import load_schema_from_module
    import apiens.tools.ariadne.scalars.date
    schema = ariadne.make_executable_schema([
            ariadne.load_schema_from_path(os.path.dirname(__file__)),
            load_schema_from_module(apiens.tools.ariadne, 'rich_validation.graphql'),
        ],
        apiens.tools.ariadne.scalars.date.definitions,
    )
"""

from typing import Any

import graphql.type.scalars
import graphql.type.definition

from apiens.tools.translate import _


# TODO: implement ariadne scalars as bindables


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
    'Bool': coerce_bool,
}
