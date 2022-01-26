""" Inspect which attributes has been modified """

from sqlalchemy.orm import Mapper
from sqlalchemy.orm.base import instance_state
from sqlalchemy.orm.state import InstanceState


def modified_attributes_names(instance: object) -> set[str]:
    """ Get names of the modified attributes of an instance """
    return set(instance_state(instance).committed_state)


def modified_column_attribute_names(instance: object) -> set[str]:
    """ Get names of the modified column attributes of an instance

    This function will resolve relationships to column attributes' values
    """
    state: InstanceState = instance_state(instance)
    mapper: Mapper = state.mapper
    attr_names = set(state.committed_state)

    # Remove relationship attribute names
    rel_names = set(mapper.relationships.keys()) & attr_names
    column_attr_names = attr_names - rel_names

    # Replace relationship attribute names with their underlying column names
    for rel_name in rel_names:
        local_columns = mapper.relationships[rel_name].local_columns
        assert all(c.foreign_keys for c in local_columns), f'Cannot translate {rel_names} to attributes: not a foreign key'
        column_attr_names.update(c.key for c in local_columns)

    # Done
    return column_attr_names
