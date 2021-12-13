from collections import abc
from dataclasses import dataclass
from typing import ClassVar

import sqlalchemy as sa

from .crudsettings import CrudSettings


@dataclass
class CrudParams:
    """ Input parameters for CRUD operations (query, mutate)

    Example: model settings, custom filters

    When your API provides some input parameters that influence the way the API works, you pass it through params.
    For instance, if your custom `filter()` method filters users by age, then `age` would be a CrudParams field.

    Example:

        @dataclass
        class UserCrudParams(CrudParams):
            age: int
            crudsettings = CrudSettings(Model=User, debug=True)

            def filter(self):
                return (
                    User.age >= self.age,
                )
    """
    # CRUD settings: the static container for all the configuration of this CRUD handler.
    crudsettings: ClassVar[CrudSettings]

    def from_input_dict(self, input_dict: dict):
        """ Get some values from the input dict.

        Used with the update() method to extract the primary key.
        """
        # The default implementation covers the majority of use cases:
        # Pick primary key values by name
        for pk_field in self.crudsettings.primary_key:
            setattr(self, pk_field, input_dict[pk_field])

    # These methods customize how your CRUD operations find objects to work with
    # Implement the _filter() and _filter1() methods

    def filter(self) -> abc.Iterable[sa.sql.elements.BinaryExpression]:
        """ Filter expression for all methods. Controls which rows are visible to CRUD methods

        Override and customize to react to user-supplied `kwargs`: like `id` coming from the request
        """
        return ()

    def filter_one(self) -> abc.Iterable[sa.sql.elements.BinaryExpression]:
        """ Filter expression for get(), update(), delete()

        Controls which objects are visible when your CRUD wants exactly one object.

        NOTE: the default implementation already filters by the primary key and users _filter().
        You do not have to worry about those!
        """
        # The default implementation: _filter() + primary key filter
        return (
            *self.filter(),
            *self._filter_primary_key(),
        )

    def _filter_primary_key(self) -> abc.Iterable[sa.sql.elements.BinaryExpression]:
        """ Find an instance by its primary key values
        """
        return (
            getattr(self.crudsettings.Model, pk_field) == getattr(self, pk_field, None)
            for pk_field in self.crudsettings.primary_key
        )
