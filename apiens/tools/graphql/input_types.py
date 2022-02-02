from functools import wraps

import graphql
from collections import abc


def wraps_input_object_out_type(type_def: graphql.GraphQLInputObjectType):
    """ Conveniently wrap `GraphQLInputObjectType.out_type()` with a decorated function.

    This is used when implementing decorators for input types.

    Example:
        @wraps_input_object_out_type(type_def)
        def out_type(value: dict) -> dict:
            return value
    """
    def decorator(out_type_func: abc.Callable[[dict], dict]):
        wrap_input_object_out_type(type_def, out_type_func)
    return decorator


def wrap_input_object_out_type(type_def: graphql.GraphQLInputObjectType, out_type_func: abc.Callable[[dict], dict]):
    """ Conveniently wrap `GraphQLInputObjectType.out_type()` with a function """
    # If we still have the original `out_type`, then just replace it. It's a passthrough fucntion
    if type_def.out_type is graphql.GraphQLInputObjectType.out_type:
        new_out_type = out_type_func
    # Otherwise a function has to be wrapped
    else:
        @wraps(type_def.out_type)
        def new_out_type(value: dict, original_out_type=type_def.out_type) -> dict:
            return out_type_func(original_out_type(value))

    # Replace it
    type_def.out_type = new_out_type  # type: ignore[assignment]
