import pydantic as pd
import sqlalchemy as sa
from functools import cached_property
from sqlalchemy.ext.declarative import DeclarativeMeta
from typing import Type, Optional, Tuple, Iterable, FrozenSet, Set, Mapping

import sa2schema
from . import crudbase
from apiens.views.mongoquery_crud.defs import AUTOMATIC

PydanticModelT = Type[pd.BaseModel]


class CrudSettings:
    """ Crud Settings object """
    # The SqlAlchemy model this settings object is made for
    Model: DeclarativeMeta

    # Primary key columns for the model.
    _primary_key: Tuple[str] = AUTOMATIC

    # Is the class using natural primary keys?
    _natural_primary_key: bool = False

    # Custom excluded fields
    _extra_exclude_on_create: FrozenSet[str] = frozenset()
    _extra_exclude_on_update: FrozenSet[str] = frozenset()

    # Detailed model fields info
    _field_names_configured: bool = False
    _ro_fields: Optional[FrozenSet[str]] = None
    _rw_fields: Optional[FrozenSet[str]] = None
    _const_fields: Optional[FrozenSet[str]] = None

    def __init__(self,
                 Model: DeclarativeMeta, *,
                 ResponseSchema: PydanticModelT,
                 CreateSchema: Optional[PydanticModelT],
                 UpdateSchema: Optional[PydanticModelT],
                 ):
        """
        Args:
            Model: the SqlAlchemy model to work with
            ResponseSchema: Pydantic model for returned objects
            CreateSchema: Pydantic input model for creating objects
            UpdateSchema: Pydantic input model for updating objects
        """
        # SqlAlchemy
        self.Model = Model

        # Pydantic schemas: input
        self.CreateInputSchema: Optional[PydanticModelT] = CreateSchema
        self.UpdateInputSchema: Optional[PydanticModelT] = UpdateSchema
        self.CreateOrUpdateInputSchema: Optional[PydanticModelT] = None

        # Pydantic schemas: output
        # NOTE: these schemas are all the same. If you need to customized them, use customize()
        self.ResponseSchema: PydanticModelT = ResponseSchema  # same for every response, unless overridden
        self.GetResponseSchema: PydanticModelT = ResponseSchema
        self.ListResponseSchema: PydanticModelT = ResponseSchema
        self.CreateResponseSchema: PydanticModelT = ResponseSchema
        self.UpdateResponseSchema: PydanticModelT = ResponseSchema
        self.DeleteResponseSchema: PydanticModelT = ResponseSchema
        self.CreateOrUpdateResponseSchema: Optional[PydanticModelT] = None

        # Primary key
        self._primary_key = sa2schema.sa_model_primary_key_names(self.Model)

    # region Settings

    # Methods to further refine the settings

    def primary_key_config(self, primary_key: Iterable[str], *, natural_primary_key: bool = False):
        """ Customize the primary key settings.

        You will only need this with natural primary keys, or other really special cases.
        """
        self._primary_key = tuple(primary_key)
        self._natural_primary_key = natural_primary_key
        return self

    def create_or_update_config(self, CreateOrUpdateSchema: PydanticModelT):
        """ Enable create_or_update() and provide a schema for it """
        self.CreateOrUpdateInputSchema = CreateOrUpdateSchema
        self.CreateOrUpdateResponseSchema = self.CreateResponseSchema
        return self

    def exclude_config(self, *,
                       create: Iterable[str] = (),
                       update: Iterable[str] = (),
                       create_and_update: Iterable[str] = ()):
        """ Specify additional fields to be excluded when doing create() an update() -- in addition to other exclusions.

        Can be called multiple times.

        Args:
            create: Fields to exclude when doing create()
            update: Fields to exclude when doing update()
            create_and_update: Fields to exclude both when doing create() or update()
        """
        self._extra_exclude_on_create |= frozenset(create) | frozenset(create_and_update)
        self._extra_exclude_on_update |= frozenset(update) | frozenset(create_and_update)
        return self

    def field_names_config(self, *,
                           ro_fields: Iterable[str] = (),
                           ro_relations: Iterable[str] = (),
                           const_fields: Iterable[str] = (),
                           rw_fields: Iterable[str] = (),
                           rw_relations: Iterable[str] = (),
                           ):
        """ Configure the behavior of individual fields

        No error is given if a field is marked as read-only, const, or ignored, and a value is provided by the UI.
        Why? Because the UI would often load values from the server and just post them back.
        It would have been a pain in the neck to remove those keys from the data before sending.
        Therefore, CrudBase will just ignore them.

        NOTE: if you use this method, you're supposed to mention every field, telling whether it's `ro` or `rw`.
        If a field should be ignored, use exclude_config()

        Args:
            ro_fields: Read-only field names. They can never be set or modified.
                Example: primary key, fields that get automatic values, etc
            ro_relations: Read-only field names. Same thing, but with a visual emphasis on relationships.
            rw_fields: Writable fields. They can always be set or modified.
                Example: all sorts of user input data
            rw_relations: Writable fields. Same thing, but with a visual emphasis on relationships.
            const_fields: Constant fields. They can only be provided when creating, but not when updating.
                Example: permanent data
        """
        # Make sure that `_exclude_on_update` did not cache anything yet.
        # Caching is done by putting the cached value inside the object's __dict__
        assert type(self)._exclude_on_update.attrname not in self.__dict__

        # remember
        self._field_names_configured = True
        self._ro_fields = frozenset(ro_fields) | frozenset(ro_relations)
        self._rw_fields = frozenset(rw_fields) | frozenset(rw_relations)
        self._const_fields = frozenset(const_fields)
        return self

    def customize(self, **overrides):
        """ Override arbitrary values within this class

        This is low-level customization.
        Use it in case you want, for instance, to have different response schemas for different methods.
        """
        self.__dict__.update(overrides)
        return self

    def test_crud_configuration(self, CrudHandler: Type['crudbase.SimpleCrudBase']):
        """ Test whether everything we've done so far makes sense. Do so in tests.

        Args:
            CrudHandler: Crud handler class
        """
        validate_multiple(self, CrudHandler, [
            validate_all_field_names_are_known,
            validate_every_copied_field_is_known,
            validate_saves_custom_fields,
            validate_saves_custom_fields_handles_every_relationship,
            validate_ro_rw_field_names_cover_whole_model,
            validate_primary_key_is_not_writable,
        ])
        return self

    # endregion

    # region Extensions

    def _crud_query_customize(self, crud: 'crudbase.SimpleCrudBase', query: sa.orm.Query) -> sa.orm.Query:
        """ Customize the ORM query

        This is a low-level method that lets you use a CrudSettings object with some query handler
        that may put additional filtering to the query and whatnot.

        For instance, MongoSQL uses this hook to inject its magic into the query.
        """
        return query

    # endregion

    # region Usage

    # Tell which options are configured

    @property
    def _create_or_update_enabled(self):
        """ Check: create_or_update() schemas configured and enabled? """
        return self.CreateOrUpdateInputSchema and self.CreateOrUpdateResponseSchema

    # Methods that help use these settings

    def _primary_key_provided(self, input: pd.BaseModel):
        """ Check whether the input contains a primary key

        This is necessary to determine whether we will create() or update()
        """
        return input.__fields_set__ >= set(self._primary_key)

    @cached_property
    def _exclude_on_create(self) -> FrozenSet[str]:
        """ Get the list of fields to exclude when creating an instance """
        exclude = set()

        # If ro/rw fields were configured
        if self._field_names_configured:
            exclude |= self._ro_fields
        # If not, only exclude the PKf
        else:
            exclude |= set() if self._natural_primary_key else set(self._primary_key)

        # Done
        return frozenset(exclude) | self._extra_exclude_on_create

    @cached_property
    def _exclude_on_update(self) -> FrozenSet[str]:
        """ Get the list of fields to exclude when updating an instance """
        exclude = set()
        exclude |= self._exclude_on_create
        exclude |= self._extra_exclude_on_update

        # If ro/rw fields were configured
        if self._field_names_configured:
            exclude |= self._const_fields
        # if not, there's nothing to add: _exclude_on_create() has already done everything
        else:
            pass

        return frozenset(exclude)

    # endregion


# region Validate


def validate_multiple(settings: CrudSettings, crud: type, validators: Iterable[callable]):
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
            validator(settings, crud)
        except AssertionError as e:
            errors.append(e)

    # Report errors
    if len(errors) == 1:
        raise errors[0]
    elif len(errors) > 1:
        raise MultipleAssertionErrors(*errors)


def validate_all_field_names_are_known(settings: CrudSettings, CrudHandler: type):
    """ Validate: all fields mentioned anywhere are actually known

    This is to prevent typos: you may think you have excluded a field properly, but made a typo.
    This test makes sure that every field you exclude is actually known to a model.
    """
    mentioned_fields = set()
    mentioned_fields |= set(settings._primary_key)
    mentioned_fields |= set(settings._extra_exclude_on_create)
    mentioned_fields |= set(settings._extra_exclude_on_update)
    if settings._field_names_configured:
        mentioned_fields |= set(settings._ro_fields)
        mentioned_fields |= set(settings._rw_fields)
        mentioned_fields |= set(settings._const_fields)

    # known fields
    known_fields = set(dir(settings.Model))

    # Unknown fields
    unknown_fields = mentioned_fields - known_fields
    assert not unknown_fields, (
        f'Unknown fields provided to crudsettings: {unknown_fields!r}. '
        f'Probably, there has been a typo, or changes were made to the model.'
    )


def validate_ro_rw_field_names_cover_whole_model(settings: CrudSettings, CrudHandler: type):
    """ Validate: field_names_config() has covered the whole input model """
    if settings._field_names_configured:
        # Field names
        all_input_fields = _all_input_field_names(settings)
        all_ro_rw_fields = settings._ro_fields | settings._rw_fields | settings._const_fields | settings._extra_exclude_on_update | settings._extra_exclude_on_create

        # Compare
        uncovered_field_names = all_input_fields - all_ro_rw_fields

        # Check
        assert not uncovered_field_names, (
            f'field_names_config() was used, but some fields have not been covered: {uncovered_field_names!r}. '
            f'The main idea of field_names_config() is that you have to specify for every field whether it is writable or not.'
        )


def validate_saves_custom_fields(settings: CrudSettings, CrudHandler: type):
    """ Validate: @saves_custom_fields() is properly configured """
    known_input_fields = _all_input_field_names(settings)
    custom_field_names = crudbase.saves_custom_fields.all_field_names_from(CrudHandler)
    unknown_fields = custom_field_names - known_input_fields
    assert not unknown_fields, (
        f'Unknown fields in @saves_custom_fields(): {unknown_fields}. '
        f'This is likely because you have a typo in the arguments provided to the decorator, or had a change in your models.'
    )


def validate_saves_custom_fields_handles_every_relationship(settings: CrudSettings, CrudHandler: type):
    """ Validate: every writable relationship is covered by @saves_custom_fields()  """
    # Only validate if going to do saving
    if any([settings.CreateInputSchema, settings.UpdateInputSchema, settings.CreateOrUpdateInputSchema]):
        # Get all relationships
        relationship_names = set(sa2schema.sa_model_info(settings.Model, types=sa2schema.AttributeType.RELATIONSHIP))

        # Get relationship names covered by somethind
        handled_relationships = set()
        # @saves_custom_fields
        handled_relationships |= crudbase.saves_custom_fields.all_field_names_from(CrudHandler)
        # exclude
        handled_relationships |= settings._exclude_on_create | settings._exclude_on_update

        # Compare
        unhandled_relationships = relationship_names - handled_relationships
        assert not unhandled_relationships, (
            f'The following relationships have not been handled by @saves_custom_fields(): '
            f'{unhandled_relationships!r}. '
            f'Either implement save handlers with @saves_custom_fields(), '
            f'or exclude them explicitly (`ro_relations`).'
        )


def validate_every_copied_field_is_known(settings: CrudSettings, CrudHandler: type):
    """ Validate: every un-excluded field is known to a model

    This is to make sure that there are no custom fields in Pydantic models that will be copied over to Sqlalchemy models.
    """
    # Collect fields that are ok to be present in the input
    known_fields = set()
    # Model fields
    known_fields.update(dir(settings.Model))
    # excluded fields: are okay because they are excluded for a reason
    known_fields.update(settings._exclude_on_update)
    known_fields.update(settings._exclude_on_create)
    # @saves_custom_fields fields
    known_fields.update(crudbase.saves_custom_fields.all_field_names_from(CrudHandler))

    # Collect fields mentioned in schemas
    pydantic_schemas = _all_input_pydantic_schemas_from_crudsettings(settings)

    # Collect unknown fields
    unknown_fields = []
    for schema_name, schema in pydantic_schemas.items():
        unknown_fields.extend((
            f'{schema_name}.{field_name}'
            for field_name in set(schema.__fields__) - known_fields
        ))

    # Report
    assert not unknown_fields, (
        f"Unknown fields used in schemas: {', '.join(unknown_fields)}. "
        f"This may mean that your Pydantic schemas contain custom fields that you have forgotten to exclude or process manually with @saves_custom_fields"
    )


def validate_primary_key_is_not_writable(settings: CrudSettings, CrudHandler: type):
    """ Validate: primary key should not be writable, unless `natural_primary_key` is selected """
    pk_fields = set(settings._primary_key)
    # Two modes
    # If `natural_primary_key` is not set, create() and update() cannot contain any PK
    if not settings._natural_primary_key:
        # create() cannot contain the primary key. Otherwise, users would be able to book custom keys, which is not right
        # update() can contain the primary key, but only for searching purposes. It must be excluded anyway, because in this function,
        # we're only interested in the fields that get saved to the DB
        fields_create = pk_fields - settings._exclude_on_create
        fields_update = pk_fields - settings._exclude_on_update
        assert not fields_create and not fields_update, (
            f"Primary key fields not excluded for create(): {fields_create!r}, for update(): {fields_update}. "
            f"A user can choose any primary key they want. "
            f"If this is the desired behavior, set `crudsettings.primary_key_config(..., natural_primary_key=True)"
        )
    # If `natural_primary_key` is set, the requirement is the opposite: primary key must be fully present
    else:
        fields_create = pk_fields & settings._exclude_on_create
        fields_update = pk_fields & settings._exclude_on_update
        assert not fields_create and not fields_update, (
            f"Natural primary key fields are excluded for create(): {fields_create!r}, for update(): {fields_update}. "
            f"You have set `natural_primary_key=True`, but it does not make sense if primary key fields are being excluded."
        )


def _all_input_pydantic_schemas_from_crudsettings(settings: CrudSettings) -> Mapping[str, PydanticModelT]:
    """ All input schemas """
    schemas = {
        'CreateInputSchema': settings.CreateInputSchema,
        'UpdateInputSchema': settings.UpdateInputSchema,
        'CreateOrUpdateInputSchema': settings.CreateOrUpdateInputSchema,
    }
    return {
        name: schema
        for name, schema in schemas.items()
        if schema is not None
    }


def _all_input_field_names(settings: CrudSettings) -> Set[str]:
    return set().union(*[
        set(schema.__fields__)
        for schema in _all_input_pydantic_schemas_from_crudsettings(settings).values()
    ])


class MultipleAssertionErrors(AssertionError):
    errors: Tuple[AssertionError]

    def __init__(self, *errors: AssertionError):
        self.errors = errors

        # Prepare the message
        bullet = '* ' if len(errors) > 1 else ''
        msg = '\n'.join(f'{bullet}{e}' for e in errors)

        # Done
        super().__init__(msg)


# endregion
