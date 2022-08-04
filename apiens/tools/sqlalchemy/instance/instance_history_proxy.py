from copy import deepcopy
from typing import TypeVar

from sqlalchemy.orm.attributes import InstrumentedAttribute, ScalarObjectAttributeImpl
from sqlalchemy.orm.base import instance_state, DEFAULT_STATE_ATTR
from sqlalchemy.orm.state import InstanceState
from apiens.tools.sqlalchemy.sainfo.properties import is_property


SAInstanceT = TypeVar('SAInstanceT')


class InstanceHistoryProxy:
    """ Proxy object to access historical model attributes' values.

    This lets the API save hook compare values of the modified instance to the values of an unmodified one.

    Example:
        # Load, back-up
        instance = ssn.query(...).one()
        prev = InstanceHistoryProxy(instance)

        # Modify
        instance.field = 'value'

        # ... somewhere inside a save hook ...
        # Compare
        assert prev.field != instance.field
    """
    def __init__(self, instance: object, *, copy: bool = False):
        """ Make a lightweight snapshot of an instance.

        Be sure to do it before flush(), because flush() will erase all in-memory changes.

        Args:
            instance: The instance to get the historical values for.
            copy: Copy every mutable value.
                Useful for embedded dictionaries, but it a bit more expensive, so disabled by default.
        """
        # Remember the historical values
        self.__state: InstanceState = instance_state(instance)
        self.__dict = {
            # Merging dictionaries is very cheap
            **self.__state.dict,  # current values
            **self.__state.committed_state,  # overwritten with DB values
        }

        # Make a deep copy to preserve embedded dictionaries
        if copy:
            self.__dict = deepcopy(self.__dict)

    def __getattr__(self, attr_name):
        # `_sa_instance_state` may be requested when accessing relationships (because they are descriptors)
        # Install the internal SqlAlchemy's property on our ModelHistoryProxy to mimic the original object.
        # This is necessary for relationship attributes to work, because they are descriptors
        # Thanks @vihtinsky for this magic
        if attr_name == DEFAULT_STATE_ATTR:
            # Initialize it lazily and only once
            state = self._make_instance_state()
            setattr(self, DEFAULT_STATE_ATTR, state)
            return state

        mapper = self.__state.mapper

        # Relationships
        if attr_name in mapper.relationships:
            # Relationships are descriptors, and so they need to be called properly
            attr: InstrumentedAttribute = getattr(mapper.class_, attr_name)
            rel: ScalarObjectAttributeImpl = attr.impl

            # This is what SqlAlchemy does on real attributes:
            #   return attr.__get__(self, self.__state.class_)
            # But we cannot do it because it would modify the original instance dict
            state = getattr(self, DEFAULT_STATE_ATTR)
            return rel.get(state, self.__dict)
            # return rel.get_committed_value(state, self.__historical)
        # @property
        elif is_property and is_property(mapper.class_, attr_name):
            # Because properties may use other columns,
            # we have to run it against our`self`, because only then it'll be able to get the original values.
            prop: property = getattr(mapper.class_, attr_name)
            return prop.fget(self)
        # Loaded columns
        elif attr_name in self.__dict:
            return self.__dict[attr_name]
        # Unloaded columns
        else:
            # Get directly from the instance.
            # May trigger lazy loads. If this is undesirable, you should have used raiseload()
            return getattr(self.__state.object, attr_name)

    def _make_instance_state(self) -> InstanceState:
        """ Create an InstanceState that behaves just like a real one

        The key difference is that its `dict` points to `self.__dict`.
        This means that any modifications we do (e.g. population with lazy loading) will not affect the original instance.

        That is, if a relationship is loaded, it's loaded into `self.__dict` instead of the original instance's dict
        """
        # Return a fake object
        state = InstanceStateCopy(self.__state)
        state.dict = self.__dict  # type: ignore[attr-defined]
        state.committed_state = {}  # type: ignore[attr-defined]
        return state  # type: ignore[return-value]


def get_history_proxy_for_instance(instance: SAInstanceT, copy: bool = False) -> SAInstanceT:
    """ Get a permanent InstanceHistoryProxy for an instance.

    Every time this function is called on an instance, even after flush, the very same InstanceHistoryProxy will be returned.
    Be careful with long-living instances: they will remember their original values the whole time.
    """
    state: InstanceState = instance_state(instance)

    # Create a new one
    if InstanceHistoryProxy not in state.info:
        state.info[InstanceHistoryProxy] = InstanceHistoryProxy(instance, copy=copy)

    # Done
    return state.info[InstanceHistoryProxy]


class InstanceStateCopy:
    def __init__(self, state: InstanceState):
        self.__state = state

    __slots__ = '__state', 'dict', 'committed_state',

    def __getattr__(self, name):
        return getattr(self.__state, name)


