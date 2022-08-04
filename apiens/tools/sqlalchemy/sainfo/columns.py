from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import TypeDecorator
from sqlalchemy.sql.elements import Label

from sqlalchemy.orm import (
    CompositeProperty,
    ColumnProperty,
)
from sqlalchemy.orm.interfaces import (
    MapperProperty,
)
from sqlalchemy.orm.attributes import (
    QueryableAttribute,
    InstrumentedAttribute,
)

try:
    # Python 3.9+
    from functools import cache
except ImportError:
    # Python 3.8
    from functools import lru_cache as cache

from .typing import SAAttribute


# region: Column Attribute types

@cache
def is_column(attribute: SAAttribute):
    return (
        is_column_property(attribute) or
        is_column_expression(attribute) or
        is_composite_property(attribute)
    )


@cache
def is_column_property(attribute: SAAttribute):
    return (
        isinstance(attribute, (InstrumentedAttribute, MapperProperty)) and
        isinstance(attribute.property, ColumnProperty) and
        isinstance(attribute.expression, sa.Column)  # not an expression, but a real column
    )


@cache
def is_column_expression(attribute: SAAttribute):
    return (
        isinstance(attribute, (InstrumentedAttribute, MapperProperty)) and
        isinstance(attribute.expression, Label)  # an expression, not a real column
    )


@cache
def is_composite_property(attribute: SAAttribute):
    return (
        isinstance(attribute, QueryableAttribute) and
        hasattr(attribute, 'property') and  # otherwise: exceptions on hybrid properties (they do not have this "property")
        isinstance(attribute.property, CompositeProperty)
    )

# endregion


# region Column Attribute info

@cache
def get_column_type(attribute: SAAttribute) -> sa.types.TypeEngine:
    """ Get column's SQL type """
    if isinstance(attribute.type, TypeDecorator):
        # Type decorators wrap other types, so we have to handle them carefully
        return attribute.type.impl
    else:
        return attribute.type


@cache
def is_array(attribute: SAAttribute) -> bool:
    """ Is the attribute a PostgreSql ARRAY column? """
    return isinstance(get_column_type(attribute), sa.ARRAY)


@cache
def is_json(attribute: SAAttribute) -> bool:
    """ Is the attribute a PostgreSql JSON column? """
    return isinstance(get_column_type(attribute), sa.JSON)

# endregion


# region Column Properties info

def is_column_property_nullable(column_property: sa.orm.ColumnProperty) -> bool:
    """ Check whether a column property is nullable """
    return column_property.expression.nullable


def is_column_property_unique(column_property: sa.orm.ColumnProperty) -> bool:
    """ Check whether a column property's value is unique """
    return column_property.expression.primary_key or column_property.expression.unique


# endregion
