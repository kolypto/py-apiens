from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.orm.base
from collections import abc

from apiens.tools.sqlalchemy import get_history_proxy_for_instance
from apiens.crud.crudsettings import CrudSettings
from .mutate_base import MutateApiBase, SAInstanceT
from .saves_custom_fields import saves_custom_fields
from ..defs import PrimaryKeyDict


class MutateApi(MutateApiBase[SAInstanceT]):
    """ CRUD API implementation: mutations

    Implements write methods: create, update, delete. They only return the primary key
    """
    # TODO: mutation signals?

    def create(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: create a new object """
        # Prepare
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)

        # Create
        if not self.params.crudsettings.natural_primary_key:
            drop_pk_fields(input_dict, self.params.crudsettings.primary_key)
        # TODO: pluck ro fields
        # NOTE: the instance object is created and discarded. If you need it, override the `_create_instance()` method.
        instance = self._create_instance(input_dict)
        instance = self._session_create_instance_impl(instance)

        # Finish, after flush
        saves_custom_fields.save(self, custom_fields, instance, None)
        res = self._format_result_dict(instance)
        return res

    def create_or_update(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: save, create an object if it's missing, update it if it exists """
        # Is the primary key provided?
        pk_provided = set(input_dict) >= set(self.params.crudsettings.primary_key)

        # Yes? Update.
        # TODO: handle natural primary keys here. If PK provided, but entry does not exist, that's "create"
        if pk_provided:
            return self.update(input_dict)
        # No? Create.
        else:
            return self.create(input_dict)

    def update(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: update, modify an existing object, find by primary key fields' """
        self.params.from_input_dict(input_dict)
        return self.update_id(input_dict)

    def update_id(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: update, modify an existing object, by params id """
        # Prepare
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)

        # Load
        # NOTE: the instance object is loaded and discarded. If you need it, override the `_find_instance()` method.
        instance = self._find_instance()

        # Update
        if not self.params.crudsettings.natural_primary_key:
            drop_pk_fields(input_dict, self.params.crudsettings.primary_key)
        # TODO: pluck ro and const fields
        instance = self._update_instance(instance, input_dict)
        instance = self._session_update_instance_impl(instance)

        # Finish, after flush
        prev = get_history_proxy_for_instance(instance)
        saves_custom_fields.save(self, custom_fields, instance, prev)
        res = self._format_result_dict(instance)
        return res

    def delete(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: delete, find by primary key fields """
        self.params.from_input_dict(input_dict)
        return self.delete_id()

    def delete_id(self) -> PrimaryKeyDict:
        """ CRUD method: delete, remove an object from the database, by params id"""
        # Load, extract PK early, before the instance is removed
        instance = self._find_instance()
        res = self._format_result_dict(instance)

        # Delete
        # NOTE: the instance object is loaded and discarded. If you need it, override the `_find_instance()` method
        instance = self._delete_instance(instance)
        instance = self._session_delete_instance_impl(instance)

        # Finish
        return res

    # TODO: implement soft-delete

    def _format_result_dict(self, instance: SAInstanceT) -> PrimaryKeyDict:
        """ Format the result that create()/update()/delete() methods produce

        For create() and update(), it's called after the instance is flushed
        For delete(), it's called before it's removed
        """
        return get_primary_key_dict(self.params.crudsettings, instance)


def get_primary_key_dict(crudsettings: CrudSettings, instance: SAInstanceT) -> PrimaryKeyDict:
    """ Extract a dict() from an instance to represent its primary key

    This is used by mutation methods to return a minimally informative object: primary key dict
    """
    identity = sa.orm.base.instance_state(instance).identity

    if not identity:
        raise ValueError('The provided instance has no identity. Is it saved?')

    return dict(
        zip(crudsettings.primary_key, identity)
    )


def drop_pk_fields(input: dict, pk_fields: abc.Itera) -> dict:
    for key in pk_fields:
        input.pop(key, None)
