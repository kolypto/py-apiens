from __future__ import annotations

from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.dynamic import DynaLoader

try:
    # Python 3.9+
    from functools import cache
except ImportError:
    # Python 3.8
    from functools import lru_cache as cache

from .typing import SAAttribute

# region: Relation Attribute types

@cache
def is_relation(attr: SAAttribute):
    return (
        is_relation_relationship(attr) or
        is_relation_dynamic_loader(attr)
    )


@cache
def is_relation_relationship(attribute: SAAttribute):
    return (
        isinstance(attribute, InstrumentedAttribute) and
        isinstance(attribute.property, RelationshipProperty) and
        not isinstance(attribute.property.strategy, DynaLoader)
    )


@cache
def is_relation_dynamic_loader(attribute: SAAttribute):
    return (
        isinstance(attribute, InstrumentedAttribute) and
        isinstance(attribute.property, RelationshipProperty) and
        isinstance(attribute.property.strategy, DynaLoader)
    )

# endregion

# region Relation Attribute info

@cache
def is_array(attribute: SAAttribute) -> bool:
    return attribute.property.uselist


@cache
def target_model(attribute: SAAttribute) -> type:
    return attribute.property.mapper.class_

# endregion
