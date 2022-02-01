from __future__ import annotations

from collections import abc
import dataclasses
from copy import copy
from dataclasses import dataclass
from typing import Optional

from .predicates import filter_by_predicate


# Model info
@dataclass
class ModelInfo:
    """ Model information """
    fields: dict[str, FieldInfo]

    def jsonable(self):
        return {
            'fields': {
                name: field.jsonable()
                for name, field in self.fields.items()
            }
        }

    def __copy__(self):
        return ModelInfo(fields={
            name: copy(field)
            for name, field in self.fields.items()
        })

    def required(self, required: Optional[bool], filter: callable = None):
        """ Get a copy of self, with every matching field's `required` value changed """
        model = copy(self)
        for field in applicable_fields(self, filter):
            field.required = required
        return model

    def nullable(self, nullable: Optional[bool], filter: callable = None):
        """ Get a copy of self, with every matching field's `nullable` value changed """
        model = copy(self)
        for field in applicable_fields(self, filter):
            field.nullable = nullable
        return model

    def __repr__(self):
        return ' ; '.join(repr(field) for field in self.fields.values())



def applicable_fields(model: ModelInfo, filter: callable = None) -> abc.Iterable[FieldInfo]:
    """ Iterate over model fields filtered by `filder` """
    for name, field in model.fields.items():
        if filter_by_predicate(name, filter):
            yield field


# A field definition: tuple (name, extra info)
@dataclass
class FieldInfo:
    """ Basic, uniform, field information

    Basic information about a certain field that does not depend on the source:
    it looks the same for Python classes, SqlAlchemy models, GraphQL types, etc.

    This property enables us to compare fields across types.
    """
    # Name of the field
    name: str

    # Field type. Using Python names
    type: Optional[str]

    # Is the field required? I.e. a value must be provided.
    # If not, the field is "skippable": i.e. can be omitted
    required: Optional[bool]

    # Is `null` a valid value?
    # If not, a non-null value must be set.
    nullable: Optional[bool]

    # Additional names, a/k/a for the field
    aliases: set[str] = dataclasses.field(default_factory=set)

    @property
    def labels(self) -> set[str]:
        """ Get the properties of this field as a set of string labels

        This is useful for display and diffing purposes

        Example:
            login: ['str', 'required', '!nullable', 'aka: "Login"']
        """
        labels = set()

        if self.type is not None:
            labels.add(self.type)

        if self.required is not None:
            labels.add(
                'required' if self.required else '!required'
            )

        if self.nullable is not None:
            labels.add(
                'nullable' if self.nullable else '!nullable'
            )

        if self.aliases:
            akas = '/'.join(sorted(self.aliases))
            labels.add(f'aka: {akas}')

        return labels

    def jsonable(self):
        return {
            'name': self.name,
            'type': self.type or None,
            'required': self.required,
            'nullable': self.nullable,
            'aliases': set(self.aliases),
        }

    def __repr__(self):
        labels = ' '.join(sorted(self.labels))
        return f'{self.name}: {labels}'

    def __eq__(self, other: FieldInfo):
        assert isinstance(other, FieldInfo)
        return (
                # At least one name in common
                ({self.name, *self.aliases} & {other.name, *other.aliases} ) and
                # Fields will only be compared when both are not `None`: that is, information is available.
                (not CHECK_TYPES or (self.type is None or other.type is None) or self.type == other.type) and
                ((self.required is None or other.required is None) or self.required == other.required) and
                ((self.nullable is None or other.nullable is None) or self.nullable == other.nullable)
        )

# We do not support types yet
CHECK_TYPES = False
