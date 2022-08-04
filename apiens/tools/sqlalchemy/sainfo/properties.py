""" SqlAlchemy model properties: annotate, list """

import dis
import inspect
from functools import lru_cache
from collections import abc
from typing import Optional, TypeVar

import sqlalchemy as sa
import sqlalchemy.ext.hybrid

from .models import unaliased_class
from .typing import SAModelOrAlias


SameFunction = TypeVar('SameFunction')

@lru_cache(typed=True)
def get_all_model_properties(Model: type) -> dict[str, property]:
    """ Get all model properties. Includes both plain properties and hybrid properties """
    mapper: sa.orm.Mapper = sa.orm.class_mapper(Model)

    # Find all attributes
    properties = {}
    for name in dir(Model):
        # Ignore all protected properties.
        # Nothing good may come by exposing them!
        if name.startswith('_'):
            continue

        # @hybrid_property are special. They're descriptors.
        # This means that if we just getattr() it, it will get executed and generate an expression for us.
        # This is now what we want: we want the `hybridproperty` object itself.
        # So we either have to get it from class __dict__, or use this:
        if isinstance(mapper.all_orm_descriptors.get(name), sa.ext.hybrid.hybrid_property):
            properties[name] = mapper.all_orm_descriptors[name]
            continue

        # Ignore all known SqlAlchemy attributes here: they can't be @property-ies.
        if name in mapper.all_orm_descriptors:
            continue

        # Get the value
        attr = getattr(Model, name)

        # @property? Go for it.
        # NOTE: if we don't check for isinstance(property), we'll get `metadata` and more
        if isinstance(attr, property):
            properties[name] = attr

    # Done
    return properties


def is_property(Model: SAModelOrAlias, attribute_name: str) -> bool:
    """ Is the provided value some sort of property (i.e. @property or a @hybrid_property)? """
    return attribute_name in get_all_model_properties(unaliased_class(Model))


def is_plain_property(Model: SAModelOrAlias, attribute_name: str) -> bool:
    """ Is the provided value a plain @property (i.e. not a @hybrid_property)? """
    all_props = get_all_model_properties(unaliased_class(Model))
    prop = all_props.get(attribute_name, None)
    return isinstance(prop, property)

def is_hybrid_property(Model: SAModelOrAlias, attribute_name: str) -> bool:
    """ Is the provided value a hybrid property (i.e. not a plain @property)? """
    all_props = get_all_model_properties(unaliased_class(Model))
    prop = all_props.get(attribute_name, None)
    return isinstance(prop, sa.ext.hybrid.hybrid_property)


def func_uses_attributes(func: abc.Callable) -> abc.Iterator[str]:
    """ Find all patterns of `self.attribute` and return those attribute names

    Supports both methods (`self`), class methods (`cls`), and weirdos (any name for `self`)
    """
    first_arg_name = next(iter(inspect.signature(func).parameters))
    return code_uses_attributes(func, first_arg_name)


def code_uses_attributes(code, object_name: str = 'self') -> abc.Iterator[str]:
    """ Find all patterns of `object_name.attribute` and return those attribute names """
    # Look for the following patterns:
    #   Instruction(opname='LOAD_FAST', argval='self') followed by
    #   Instruction(opname='LOAD_ATTR', argval='<attr-name>')
    # or
    #   Instruction(opname='LOAD_FAST', argval='self') followed by
    #   Instruction(opname='STORE_ATTR', argval='<attr-name>')
    prev_instruction: Optional[dis.Instruction] = None
    for instruction in dis.get_instructions(code):
        if (
            instruction.opname in ('LOAD_ATTR', 'STORE_ATTR') and
            prev_instruction and
            prev_instruction.opname == 'LOAD_FAST' and
            prev_instruction.argval == object_name
            ):
            yield instruction.argval
        prev_instruction = instruction
