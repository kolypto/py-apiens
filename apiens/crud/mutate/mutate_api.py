from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.orm.base

from .mutate_base import MutateApiBase, SAInstanceT
from .saves_custom_fields import saves_custom_fields
from ..defs import PrimaryKeyDict


class MutateApi(MutateApiBase[SAInstanceT]):
    # TODO: mutation signals?

    # TODO: catch SqlAlchemy errors and rethrow them as Apiens errors?

    def create(self, input_dict: dict) -> PrimaryKeyDict:
        # Prepare
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)

        # Create
        instance = self._create_instance(input_dict)
        instance = self._session_create_instance_impl(instance)

        # Finish, after flush
        saves_custom_fields.save(self, custom_fields, instance, None)
        return self._get_primary_key_dict(instance)

    def create_or_update(self, input_dict: dict) -> PrimaryKeyDict:
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
        self.params.from_input_dict(input_dict)
        return self.update_id(input_dict)

    def update_id(self, input_dict: dict) -> PrimaryKeyDict:
        # Prepare
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)

        # Load
        instance = self._find_instance()

        # Update
        instance = self._update_instance(instance, input_dict)
        instance = self._session_update_instance_impl(instance)

        # Finish, after flush
        saves_custom_fields.save(self, custom_fields, instance, None)  # TODO: give it a `prev` from `_update_instance()`
        return self._get_primary_key_dict(instance)

    def delete(self) -> PrimaryKeyDict:
        # Load, extract PK early
        instance = self._find_instance()
        pk = self._get_primary_key_dict(instance)

        # Delete
        instance = self._delete_instance(instance)
        instance = self._session_delete_instance_impl(instance)

        # Finish
        return pk

    # region Helpers

    def _get_primary_key_dict(self, instance: SAInstanceT) -> PrimaryKeyDict:
        return dict(
            zip(
                self.params.crudsettings.primary_key,
                sa.orm.base.instance_state(instance).identity,
            )
        )

    # endregion
