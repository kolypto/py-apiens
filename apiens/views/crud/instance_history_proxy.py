from copy import deepcopy
from typing import TypeVar

from sqlalchemy.orm.attributes import InstrumentedAttribute, ScalarObjectAttributeImpl
from sqlalchemy.orm.base import instance_state, DEFAULT_STATE_ATTR
from sqlalchemy.orm.state import InstanceState

from sa2schema import sa_model_info, AttributeType
from sa2schema.info import RelationshipInfo, PropertyInfo, HybridPropertyInfo


ModelT = TypeVar('ModelT')


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
        # Model info
        self.__model_info = sa_model_info(type(instance), types=AttributeType.ALL)

        # Remember the historical values
        self.__state: InstanceState = instance_state(instance)
        self.__historical = {
            # Merging dictionaries is very cheap
            **self.__state.dict,  # current values
            **self.__state.committed_state,  # overwritten with DB values
        }

        # Make a deep copy to preserve embedded dictionaries
        if copy:
            self.__historical = deepcopy(self.__historical)

    def __getattr__(self, attr_name):
        # _sa_instance_state() may be requested when accessing relatipnships (because they are descriptors)
        if attr_name == DEFAULT_STATE_ATTR:
            # Initialize it lazily and only once
            return self.__enable_relationships_access()

        # Attribute info
        try:
            attr_info = self.__model_info[attr_name]
        except KeyError as e:
            raise AttributeError(attr_name) from e

        # Relationships
        if isinstance(attr_info, RelationshipInfo):
            # Relationships are descriptors, and so they need to be called properly
            attr: InstrumentedAttribute = getattr(self.__state.class_, attr_name)
            #return attr.__get__(self, self.__state.class_)  # cannot do it because it tries to use the self.__dict__ which is empty
            rel: ScalarObjectAttributeImpl = attr.impl
            return rel.get_committed_value(self.__state, self.__historical)
        # @property
        elif isinstance(attr_info, (PropertyInfo, HybridPropertyInfo)):
            # Because properties may use other columns,
            # we have to run it against our`self`, because only then it'll be able to get the original values.
            prop: property = getattr(self.__state.class_, attr_name)
            return prop.fget(self)
        # Loaded columns
        elif attr_name in self.__historical:
            return self.__historical[attr_name]
        # Unloaded columns
        else:
            # Get directly from the instance.
            # May trigger lazy loads. If this is undesirable, you should have used raiseload()
            return getattr(self.__state.object, attr_name)

    def __enable_relationships_access(self) -> InstanceState:
        # Install the internal SqlAlchemy's property on our ModelHistoryProxy to mimic the original object.
        # This is necessary for relationship attributes to work, because they are descriptors
        # Thanks @vihtinsky for this magic
        new_state = InstanceState(self, self.__state.manager)
        new_state.key = self.__state.key
        new_state.session_id = self.__state.session_id
        setattr(self, DEFAULT_STATE_ATTR, new_state)
        return new_state


def get_history_proxy_for_instance(instance: ModelT, copy: bool = False) -> ModelT:
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
