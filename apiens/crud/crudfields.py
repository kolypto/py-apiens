from __future__ import annotations

import typing
from collections import abc
from functools import cached_property
from typing import Optional


if typing.TYPE_CHECKING:
    from apiens.crud import MutateApiBase


class CrudFields:
    """ Crud fields: describes how to handle fields when doing CRUD """

    # Primary key field names
    primary_key: tuple[str]

    # Are we using natural primary keys? I.e. when the user can specify which primary key will the object have
    natural_primary_key: bool = False

    # Custom excluded fields
    extra_exclude_on_create: frozenset[str] = frozenset()
    extra_exclude_on_update: frozenset[str] = frozenset()

    # Detailed model fields info
    # ro:     can never be set by the user: they get values automatically.
    #         Example: primary key
    # rw:     can always be set by the user
    # const:  can only be set when the object is created, but not modified afterwards
    # ignore: fields that are simply skipped
    ro_fields: Optional[frozenset[str]] = None
    rw_fields: Optional[frozenset[str]] = None
    const_fields: Optional[frozenset[str]] = None

    # Is the model properly configured?
    # If so, then (ro | rw | const | ignore) must cover the model completely
    field_names_fully_configured: bool = False

    # Debug mode?
    debug: bool

    def __init__(self,
                 primary_key: abc.Sequence[str],
                 natural_primary_key: bool = False,
                 debug: bool = False,
                 ):
        self.primary_key = tuple(primary_key)
        self.natural_primary_key = natural_primary_key
        self.debug = debug

    # Configure

    def exclude(self, *,
                exclude: abc.Sequence[str] = None,
                exclude_on_create: abc.Sequence[str] = (),
                exclude_on_update: abc.Sequence[str] = (),
                ):
        """ Specify additional fields to be excluded when doing create() and update()

        Can be called multiple times.

        Args:
            exclude: Fields to exclude both when doing create() or update()
            exclude_on_create: Fields to exclude when doing create()
            exclude_on_update: Fields to exclude when doing update()
        """
        self.extra_exclude_on_create |= frozenset(exclude_on_create) | frozenset(exclude)
        self.extra_exclude_on_update |= frozenset(exclude_on_update) | frozenset(exclude)
        return self

    def fields(self,
               ro_fields: abc.Iterable[str] = (),
               ro_relations: abc.Iterable[str] = (),
               const_fields: abc.Iterable[str] = (),
               rw_fields: abc.Iterable[str] = (),
               rw_relations: abc.Iterable[str] = (),
               ):
        """ Configure fields for CRUD: readonly, writable, constant

        When used, every field will fall into one of the categoies:
        * ro: read-only fields
        * rw: readable-writable fields
        * const: fields whose values can only be set once
        """
        # Make sure that `exclude_on_update` did not cache anything yet.
        # Caching is done by putting the cached value inside the object's __dict__
        assert type(self).exclude_on_update.attrname not in self.__dict__
        assert type(self).exclude_on_create.attrname not in self.__dict__

        # Store
        self.ro_fields = frozenset(ro_fields) | frozenset(ro_relations)
        self.rw_fields = frozenset(rw_fields) | frozenset(rw_relations)
        self.const_fields = frozenset(const_fields)
        self.field_names_fully_configured = True

        return self

    # Usage

    @cached_property
    def exclude_on_create(self) -> frozenset[str]:
        """ Get the list of fields to exclude when create()ing an instance """
        exclude = set()
        exclude |= self.extra_exclude_on_create

        # ro/rw fields configured?
        if self.field_names_fully_configured:
            exclude |= self.ro_fields
        # if not, only exclude the PK
        else:
            exclude |= set() if self.natural_primary_key else set(self.primary_key)

        return frozenset(exclude)

    @cached_property
    def include_on_create(self) -> frozenset[str]:
        """ Get the list of fields to include when create()ing an instance """
        assert self.field_names_fully_configured  # include mode is only available when fields are fully configured

        include = set()
        include |= self.const_fields
        include |= self.rw_fields

        return frozenset(include)

    @cached_property
    def exclude_on_update(self) -> frozenset[str]:
        """ Get the list of fields to exclude when update()ing an instance """
        exclude = set()

        # Exclude fields that create() would exclude
        exclude |= self.exclude_on_create

        # ro/rw fields configured?
        if self.field_names_fully_configured:
            exclude |= self.const_fields
        # if not, there's nothing to add: exclude_on_create() has already done everything
        else:
            pass

        return frozenset(exclude)

    @cached_property
    def include_on_update(self) -> frozenset[str]:
        """ Get the list of fields to include when update()ing an instance """
        assert self.field_names_fully_configured  # include mode is only available when fields are fully configured

        include = set()
        include |= self.rw_fields

        return frozenset(include)

    def prepare_input_for_create(self, input_dict: dict, *, allow_extra_keys: bool):
        """ Given the input dict, drop the fields that we don't want """
        # Fully configured: whitelist keys
        if self.field_names_fully_configured and not allow_extra_keys:
            for key in input_dict:
                if key not in self.include_on_create:
                    input_dict.pop(key)
        # Else: blacklist keys
        else:
            for key in self.exclude_on_create:
                if key in input_dict:
                    input_dict.pop(key)

    def prepare_input_dict_for_update(self, input_dict: dict, *, allow_extra_keys: bool):
        """ Given the input dict, drop the fields that we don't want """
        # Fully configured: whitelist keys
        if self.field_names_fully_configured and not allow_extra_keys:
            for key in input_dict:
                if key not in self.include_on_update:
                    input_dict.pop(key)
        # Else: blacklist keys
        else:
            for key in self.exclude_on_update:
                if key in input_dict:
                    input_dict.pop(key)

    def test_crud_configuration(self, MutateApiCls: type['MutateApiBase']):
        """ Verify the configuration. Do this in unit-tests.

        Args:
            MutateApiCls: Your MutateApi class
        """
        validate_multiple(self, MutateApiCls, [
            validate_all_field_names_are_known_to_model,
            validate_saves_custom_fields_names_valid,
            validate_saves_custom_fields_handles_every_relationship,
            validate_saves_custom_fields_handles_every_relationship,
            validate_primary_key_is_not_writable,
        ])
        return self


# region Validation


def validate_multiple(crudfields: CrudFields, MutateApiCls: type['MutateApiBase'], validators: abc.Iterable[callable]):
    """ Run multiple validators and raise all results together

    This is convenient when multiple validation errors are present. If they were raised immediately,
    you would only get the first one, which is annoying.

    Raises:
        AssertionError, MultipleAssertionErrors
    """
    # Collect errors
    errors = []
    for validator in validators:
        try:
            validator(crudfields, MutateApiCls)
        except AssertionError as e:
            errors.append(e)

    # Report errors
    if len(errors) == 1:
        raise errors[0]
    elif len(errors) > 1:
        raise MultipleAssertionErrors(*errors)


def validate_all_field_names_are_known_to_model(crudfields: CrudFields, MutateApiCls: type['MutateApiBase']):
    """ Validate: all fields names exist in the model

    This helps prevent typos in field names.
    You may think you have excluded a field, but made a typo.
    """
    # Mentioned fields
    mentioned_fields = set()
    mentioned_fields |= set(crudfields.primary_key)
    mentioned_fields |= set(crudfields.extra_exclude_on_create)
    mentioned_fields |= set(crudfields.extra_exclude_on_update)

    if crudfields.field_names_fully_configured:
        mentioned_fields |= set(crudfields.ro_fields)
        mentioned_fields |= set(crudfields.rw_fields)
        mentioned_fields |= set(crudfields.const_fields)

    # Known fields
    known_fields = set(dir(MutateApiCls.params.crudsettings.Model))  # just any name will do

    # Unknown fields
    unknown_fields = mentioned_fields - known_fields
    assert not unknown_fields, (
        f'Unknown fields provided to crudfields: {unknown_fields!r}. '
        f'Probably, there has been a typo, or changes were made to the model.'
    )


def validate_field_names_valid(crudfields: CrudFields, MutateApiCls: type['MutateApiBase']):
    """ Validate: fields() covers the whole input model """
    if not crudfields.field_names_fully_configured:
        return

    # Field names
    all_input_fields = ... # TODO: get all field names from.. what? API model? DB model? Comparison model?
    all_ro_rw_fields = {
        *crudfields.ro_fields,
        *crudfields.rw_fields,
        *crudfields.const_fields,
        *crudfields.extra_exclude_on_create,
        *crudfields.extra_exclude_on_update,
    }

    # Compare
    uncovered_field_names = all_input_fields - all_ro_rw_fields

    # Check
    assert not uncovered_field_names, (
        f'fields() was used, but some fields have not been covered: {uncovered_field_names!r}. '
        f'Please specify whether they are: ro, const, rw, ignore, ...'
    )


def validate_field_names_cover_whole_model(crudfields: CrudFields, MutateApiCls: type['MutateApiBase']):
    if not crudfields.field_names_fully_configured:
        return

    # TODO: compare with .. what? API model? Comparison model?


def validate_saves_custom_fields_names_valid(crudfields: CrudFields, MutateApiCls: type['MutateApiBase']):
    """ Validate: @saves_custom_fields() is properly configured """
    from .mutate.saves_custom_fields import saves_custom_fields

    known_input_fields = ...  # TODO: get from the API
    custom_field_names = saves_custom_fields.all_field_names_from(MutateApiCls)
    unknown_fields = custom_field_names - known_input_fields
    assert not unknown_fields, (
        f'Unknown fields in @saves_custom_fields(): {unknown_fields}. '
        f'This is likely because you have a typo in the arguments provided to the decorator, or had a change in your models.'
    )


def validate_saves_custom_fields_handles_every_relationship(crudfields: CrudFields, MutateApiCls: type['MutateApiBase']):
    """ Validate: every writable relationship is covered by @saves_custom_fields()  """
    from .mutate.saves_custom_fields import saves_custom_fields

    input_relationship_names = ...

    # Mentioned relationships
    handled_relationship_names = set(saves_custom_fields.all_field_names_from(MutateApiCls))
    handled_relationship_names |= crudfields.exclude_on_create
    handled_relationship_names |= crudfields.exclude_on_update

    # Compare
    unhandled_relationships = input_relationship_names - handled_relationship_names
    assert not unhandled_relationships, (
        f'The following relationships have not been handled by @saves_custom_fields(): {unhandled_relationships!r}. '
        f'Either implement save handlers with @saves_custom_fields(), or exclude them explicitly (`ro_relations`).'
    )


def validate_primary_key_is_not_writable(crudfields: CrudFields, MutateApiCls: type['MutateApiBase']):
    """ Validate: primary key should not be writable, unless `natural_primary_key` is selected """
    pk_fields = set(crudfields.primary_key)
    # Two modes
    # If `natural_primary_key` is not set, create() and update() cannot contain any PK
    if not crudfields.natural_primary_key:
        # create() cannot contain the primary key. Otherwise, users would be able to book custom keys, which is not right
        # update() can contain the primary key, but only for searching purposes. It must be excluded anyway, because in this function,
        # we're only interested in the fields that get saved to the DB
        fields_create = pk_fields - crudfields.exclude_on_create
        fields_update = pk_fields - crudfields.exclude_on_update
        assert not fields_create and not fields_update, (
            f"Primary key fields not excluded for create(): {fields_create!r}, for update(): {fields_update}. "
            f"A user can choose any primary key they want. "
            f"If this is the desired behavior, set `natural_primary_key=True"
        )
    # If `natural_primary_key` is set, the requirement is the opposite: primary key must be fully present
    else:
        fields_create = pk_fields & crudfields.exclude_on_create
        fields_update = pk_fields & crudfields.exclude_on_update
        assert not fields_create and not fields_update, (
            f"Natural primary key fields are excluded for create(): {fields_create!r}, for update(): {fields_update}. "
            f"You have set `natural_primary_key=True`, but it does not make sense if primary key fields are being excluded."
        )


class MultipleAssertionErrors(AssertionError):
    errors: tuple[AssertionError]

    def __init__(self, *errors: AssertionError):
        self.errors = errors

        # Prepare the message
        bullet = '* ' if len(errors) > 1 else ''
        msg = '\n'.join(f'{bullet}{e}' for e in errors)

        # Done
        super().__init__(msg)

# endregion
