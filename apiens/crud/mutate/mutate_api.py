from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.orm.base

from .mutate_base import MutateApiBase, SAInstanceT
from ..defs import PrimaryKeyDict


class MutateApi(MutateApiBase[SAInstanceT]):
    # TODO: mutation signals?

    # TODO: catch SqlAlchemy errors and rethrow them as Apiens errors?

    # TODO: @saves_custom_fields

    def create(self, input_dict: dict) -> PrimaryKeyDict:
        instance = self._create_instance(input_dict)
        instance = self._session_create_instance_impl(instance)
        return self._get_primary_key_dict(instance)

    def create_or_update(self, input_dict: dict) -> PrimaryKeyDict:
        pk_provided = set(input_dict) >= set(self.params.crudsettings.primary_key)
        if pk_provided:
            return self.update(input_dict)
        else:
            return self.create(input_dict)

    def update(self, input_dict: dict) -> PrimaryKeyDict:
        self.params.from_input_dict(input_dict)
        return self.update_id(input_dict)

    def update_id(self, input_dict: dict) -> PrimaryKeyDict:
        instance = self._find_instance()
        instance = self._update_instance(instance, input_dict)
        instance = self._session_update_instance_impl(instance)
        return self._get_primary_key_dict(instance)

    def delete(self) -> PrimaryKeyDict:
        instance = self._find_instance()
        pk = self._get_primary_key_dict(instance)
        instance = self._delete_instance(instance)
        instance = self._session_delete_instance_impl(instance)
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
