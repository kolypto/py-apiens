import dataclasses
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
        """ Populate values from a dict received from the user. Used with update()

        This method will populate `self.<pk-field-name>` from an instance dictionary.

        Used with the update() method to extract the primary key and pass it to update_id().
        """
        # The default implementation covers the majority of use cases:
        self.from_primary_key_dict(input_dict)

    def from_primary_key_dict(self, pk_dict: dict):
        """ Populate values from an instance dict where only primary keys are set.

        This method will populate `self.<pk-field-name>` from an instance dictionary.

        Used when:
        * A returning mutation needs to load an object (e.g. create())
        * Through from_input_dict()
        """
        # Refuse to set attributes if they're not defined as @dataclass fields
        self._assert_primary_key_attributes_defined()

        # Pick primary key values by name
        for pk_field in self.crudsettings.primary_key:
            setattr(self, pk_field, pk_dict[pk_field])

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
        """ Find an instance by its primary key values """
        # Refuse to get attributes if they're not defined as @dataclass fields
        self._assert_primary_key_attributes_defined()

        # Primary key names: from `self.crudsettings`
        # Primary key values: from `self.*`
        return (
            getattr(self.crudsettings.Model, pk_field) == getattr(self, pk_field, None)
            for pk_field in self.crudsettings.primary_key
        )

    def _assert_primary_key_attributes_defined(self):
        """ Check that primary key attributes are defined. Once. """
        missing_fields = set(self.crudsettings.primary_key) - set(field.name for field in dataclasses.fields(self))
        assert not missing_fields, f'Primary key not represented in {type(self)}. Missing fields: {missing_fields}'

        # Once. Replace this method with a dummy
        self._assert_primary_key_attributes_defined = lambda: None
