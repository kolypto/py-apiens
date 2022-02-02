from collections import abc

from typing import Optional
from jessiql import sainfo
from .defs import AUTOMATIC
from .crudfields import CrudFields


class CrudSettings:
    """ Crud Settings object: provides basic information about how to CRUD anything """
    # Debug mode?
    debug: bool = False

    # The SqlAlchemy model this settings object is made for
    Model: type

    # Primary key columns for the model.
    primary_key: tuple[str, ...] = AUTOMATIC  # type: ignore[assignment]

    # Is the class using natural primary keys?
    natural_primary_key: bool = False

    def __init__(self,
                 Model: type, *,
                 natural_primary_key: bool = False,
                 debug: bool = False
                 ):
        """
        Args:
            Model: the SqlAlchemy model to work with
            natural_primary_key: Are we using a natural primary key (i.e. writable)?
            debug: Debug mode (for testing and non-production instances)
        """
        self.debug = debug
        self.Model = Model
        self.natural_primary_key = natural_primary_key
        self.primary_key = sainfo.primary_key.primary_key_names(self.Model)

        self.crudfields = CrudFields(
            primary_key=self.primary_key,
            natural_primary_key=natural_primary_key,
            debug=debug,
        )

    # Methods to further refine the settings

    def debug_config(self, debug: bool):
        """ Enable debug mode?"

        In debug mode, Crud handlers may make additional checks and throw extra errors to make sure things add up.
        """
        self.debug = debug
        return self

    def primary_key_config(self, primary_key: abc.Iterable[str], *, natural_primary_key: bool = False):
        """ Customize the primary key settings.

        You will only need this with natural primary keys, or other really special cases.
        """
        self.primary_key = tuple(primary_key)
        self.natural_primary_key = natural_primary_key
        return self

    def exclude(self, *,
                exclude: abc.Sequence[str] = None,
                exclude_on_create: abc.Sequence[str] = (),
                exclude_on_update: abc.Sequence[str] = (),
                ):
        """ Exclude fields from the input object """
        self.crudfields.exclude(
            exclude=exclude,
            exclude_on_create=exclude_on_create,
            exclude_on_update=exclude_on_update)
        return self

    def fields(self,
               ro_fields: abc.Iterable[str] = (),
               ro_relations: abc.Iterable[str] = (),
               const_fields: abc.Iterable[str] = (),
               rw_fields: abc.Iterable[str] = (),
               rw_relations: abc.Iterable[str] = (),
               ):
        """ Configure fields: readonly, writable, constant fields """
        self.crudfields.fields(
            ro_fields=ro_fields,
            ro_relations=ro_relations,
            const_fields=const_fields,
            rw_fields=rw_fields,
            rw_relations=rw_relations,
        )
        return self
