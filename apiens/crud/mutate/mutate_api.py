from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.orm.base

from apiens.tools.sqlalchemy import get_history_proxy_for_instance
from apiens.crud.crudsettings import CrudSettings
from .mutate_base import MutateApiBase, SAInstanceT
from .saves_custom_fields import saves_custom_fields
from ..defs import PrimaryKeyDict


class MutateApi(MutateApiBase[SAInstanceT]):
    # TODO: mutation signals?

    # TODO: catch SqlAlchemy errors and rethrow them as Apiens errors?

    def create(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: create a new object """
        # Prepare
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)

        # Create
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
        # TODO: handle natural primary keys here
        if pk_provided:
            return self.update(input_dict)
        # No? Create.
        else:
            return self.create(input_dict)

    def update(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: update, modify an existing object, finding it by its primary key fields' """
        self.params.from_input_dict(input_dict)
        return self.update_id(input_dict)

    def update_id(self, input_dict: dict) -> PrimaryKeyDict:
        """ CRUD method: update, modify an existing object, by id """
        # Prepare
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)

        # Load
        # NOTE: the instance object is loaded and discarded. If you need it, override the `_find_instance()` method.
        instance = self._find_instance()

        # Update
        instance = self._update_instance(instance, input_dict)
        instance = self._session_update_instance_impl(instance)

        # Finish, after flush
        prev = get_history_proxy_for_instance(instance)
        saves_custom_fields.save(self, custom_fields, instance, prev)
        res = self._format_result_dict(instance)
        return res

    def delete(self) -> PrimaryKeyDict:
        """ CRUD method: delete, remove an object from the database """
        # Load, extract PK early, before the instance is removed
        instance = self._find_instance()
        res = self._format_result_dict(instance)

        # Delete
        # NOTE: the instance object is loaded and discarded. If you need it, override the `_find_instance()` method
        instance = self._delete_instance(instance)
        instance = self._session_delete_instance_impl(instance)

        # Finish
        return res

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
    return dict(
        zip(
            crudsettings.primary_key,
            sa.orm.base.instance_state(instance).identity,
        )
    )
