from __future__ import annotations

from typing import Optional

from apiens.tools.sqlalchemy import get_history_proxy_for_instance
from ..base import ModelOperationBase, SAInstanceT


class MutateApiBase(ModelOperationBase[SAInstanceT]):
    # Use deep copying for historical `prev` objects?
    # Set to `True` if your Crud handler requires accessing the historical value of a mutable field (dict, etc)
    # Technically, it will use InstanceHistoryProxy(copy=True)
    COPY_INSTANCE_HISTORY: bool = False

    def _instance_hook_presave(self, new: Optional[SAInstanceT] = None, prev: Optional[SAInstanceT] = None):
        """ A hook called when an instance is going to be saved. Pre-flush, before signals.

        This hook is called before_flush:
        * on create(), after an instance has been constructed from the input
        * on update(), after an instance has been modified from the input
        * on delete(), after it has been loaded, before it's marked for deletion

        In all cases, this hook is called before any other signal is sent.
        Use it for fine-tuning created objects.

        Features:
        * The instance has just been modified
        * No other signal handlers have been fired
        * It is before-flush, so all the changes are still visible

        Here's how you know what's going on:
        * new and not old: create()
        * new and old: update()
        * not new and old: delete()

        Args:
            new: The instance being saved. `None` when delete()
            prev: The unmodified version of the instance. `None` when create()
        """

    # region Instance lookup & mutation

    def _find_instance(self) -> SAInstanceT:
        """ Get exactly one SqlAlchemy instance

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
        """
        q = self.ssn.query(self.params.crudsettings.Model)
        q = q.filter(*self.params.filter_one())
        return q.one()

    def _create_instance(self, input_dict: dict) -> SAInstanceT:
        """ Create an SqlAlchemy instance """
        # Create
        instance = self._create_instance_from_input_dict(input_dict)

        # Hook
        self._instance_hook_presave(new=instance, prev=None)

        # Done
        return instance

    def _update_instance(self, instance: SAInstanceT, input_dict: dict) -> SAInstanceT:
        # Update
        instance = self._update_instance_from_input_dict(instance, input_dict)

        # Hook
        prev = get_history_proxy_for_instance(instance, copy=self.COPY_INSTANCE_HISTORY)
        self._instance_hook_presave(new=instance, prev=prev)

        # Done
        return instance

    def _delete_instance(self, instance: SAInstanceT) -> SAInstanceT:
        # Hook
        self._instance_hook_presave(new=None, prev=instance)

        # Done
        return instance

    # TODO: implement soft-delete
    # TODO: create_or_update_many() from MongoSQL 2.x

    # endregion

    # region Input dict handling for create & update

    def _create_instance_from_input_dict(self, input_dict: dict) -> SAInstanceT:
        """ Create a new SqlAlchemy instance from an `input_dict` fields

        Override to customize how new instances are created
        """
        # TODO: pick only known kwargs, and fail on all others in testing? See `writable_field_names`
        return self.params.crudsettings.Model(**input_dict)

    def _update_instance_from_input_dict(self, instance: SAInstanceT, input_dict: dict) -> SAInstanceT:
        """ Modify an existing SqlAlchemy instance using field values from `input_dict`

        Override to customize how instances are updated
        """
        # TODO: pick only known kwargs, and fail on all others in testing? See `writable_field_names`
        for key, value in input_dict.items():
            # Only update attributes that have actually changed.
            if value != getattr(instance, key):
                # Use setattr() to make sure that SqlAlchemy change-detection logic is triggered.
                # This fires events & stuff
                setattr(instance, key, value)
        return instance

    # endregion

    # region Mutated instance handling with SqlAlchemy Session

    def _session_create_instance_impl(self, instance: SAInstanceT) -> SAInstanceT:
        """ Session support for create() instance """
        self.ssn.add(instance)
        self.ssn.flush()
        return instance

    def _session_update_instance_impl(self, instance: SAInstanceT) -> SAInstanceT:
        """ Session support for update() instance """
        self.ssn.flush()
        return instance

    def _session_delete_instance_impl(self, instance: SAInstanceT) -> SAInstanceT:
        """ Session support for update() instance """
        # Workaround: remove all possible lazy loads and raiseloads. raiseload() is especially harmful here:
        # SqlAlchemy will do cascade deletions, and it will need the values of foreign key fields.
        # See: https://github.com/sqlalchemy/sqlalchemy/issues/5398
        self.ssn.refresh(instance)

        # Flush
        self.ssn.delete(instance)
        self.ssn.flush()

        # Done
        return instance

    # endregion
