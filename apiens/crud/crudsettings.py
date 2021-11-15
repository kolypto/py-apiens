from collections import abc

from jessiql import sainfo
from .defs import AUTOMATIC


class CrudSettings:
    """ Crud Settings object """
    # Debug mode?
    debug: bool = False

    # The SqlAlchemy model this settings object is made for
    Model: type

    # Primary key columns for the model.
    primary_key: tuple[str] = AUTOMATIC

    # Is the class using natural primary keys?
    natural_primary_key: bool = False

    def __init__(self,
                 Model: type, *,
                 debug: bool = False
                 ):
        """
        Args:
            Model: the SqlAlchemy model to work with
            debug: Debug mode (for testing and non-production instances)
        """
        self.debug = debug
        self.Model = Model
        self.primary_key = sainfo.primary_key.primary_key_names(self.Model)

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
