from contextlib import contextmanager

import pydantic as pd
import sqlalchemy as sa
import sqlalchemy.orm
from typing import TypeVar, Generic, Iterable, Union, Mapping, Any, Generator, ClassVar, Set, Sequence, Type, ContextManager, Optional

from . import crud_signals
from .crud_settings import CrudSettings
from .defs import QueryObject
from .instance_history_proxy import get_history_proxy_for_instance

# SqlAlchemy model
from apiens.util import decomarker

ModelT = TypeVar("ModelT")

# Response object
ResponseValueT = TypeVar("ResponseValueT")

# Crud Handler
CrudHandlerT = TypeVar('CrudHandlerT')


# Values for an SqlAlchemy instance, in the form of a dictionary. Possibly, partial.
InstanceDict = Mapping[str, Any]
# User-supplied values for filtering objects
UserFilterValue = Any


class SimpleCrudBase(Generic[ModelT]):
    """ CRUD Handler: basic business-logic layer for your SqlAlchemy instances.

    Main features:

    * Independent from any web framework: works purely with data
    * Only implements operations on instances themselves. Does not save anything to a Session.
    * Uses Pydantic models for input data validation
    * Uses Pydantic models for output data modification
    * Supports any means of filtering/selection using *filter and **filter_by arguments
    * Sends CRUD signals. See `crud_signals.py`
    * Can save relationships (by using @saves_custom_fields)

    This object is supposed to be re-initialized for every request.

    For a more thorough implementation that is able to actually save objects, see `CrudBase` class.
    """
    # CRUD settings: the static container for all the configuration of this CRUD handler.
    crudsettings: ClassVar[CrudSettings]

    def __init__(self, ssn: sa.orm.Session, *, query_object: QueryObject = None):
        """ Initialize the Crud handler for one request

        Args:
            ssn: The Session to work with. This implementation only uses it for loading.
        """
        self.ssn = ssn
        self.query_object = query_object

    __slots__ = 'ssn', 'query_object'

    # Use deep copying for historical `prev` objects?
    # Set to `True` if your Crud handler requires accessing the historical value of a mutable field (dict, etc)
    # Technically, it will use InstanceHistoryProxy(copy=True)
    COPY_INSTANCE_HISTORY: bool = False


    # region CRUD Operations

    # Genus: _*_instance()
    # input: filter, Pydantic model
    # output: SqlAlchemy instance
    # Purpose: implement CRUD on instance level

    # These methods implement the basic features of CRUD operations: get the input, apply it, yield results.
    # Every method receives *filter and **filter_by arguments that let you apply custom filtering.
    # They all return SqlAlchemy models, or Query[ModelT] iterables
    # They do not flush() nor commit()
    # These are the basic building blocks for your application.

    def _get_instance(self, *filter: sa.sql.expression.BinaryExpression, **filter_by: Mapping[str, Any]) -> ModelT:
        """ get() method: load one instance

        Args:
            *filter: SqlAlchemy filter() expressions (Model.field == value)
            **filter_by: SqlAlchemy filter_by() expressions ( { 'field_name': value } )

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
        """
        # Raises: sqlalchemy.orm.exc.NoResultFound
        # Raises: sqlalchemy.orm.exc.MultipleResultsFound
        return self._query(*filter, **filter_by).one()

    def _list_instances(self, *filter: sa.sql.expression.BinaryExpression, **filter_by: Mapping[str, Any]) -> Union[sa.orm.Query, Iterable[ModelT]]:
        """ list() method: load multiple instances

        This method will ssn.query() them and return

        Returns:
            Query[ModelT] that can be iterated for models
        """
        return self._query(*filter, **filter_by)

    def _create_instance(self, input: pd.BaseModel) -> ModelT:
        """ create() method: create an instance

        This method will Model(**input.dict()) , do @saves_custom_fields(), but won't ssn.add() it
        Session operations are out of scope.

        Args:
            input: Input from the user.
                It is a validated Pydantic model and it will be used to create an SqlAlchemy model.
                NOTE: it has to be a Pydantic model.
                CrudBase.create() can also accept a dictionary, but it's a Pydantic model all the way down.

        Raises:
            sa.exc.IntegrityError
        """
        # Create
        instance = self._create_instance_from_input(input, exclude=self.crudsettings._exclude_on_create)

        # Hook
        self._instance_hook_presave(new=instance, prev=None)

        # Signals
        crud_signals.on_create_prepared.send(type(self), crud=self, new=instance)
        crud_signals.on_save_prepared.send(type(self), crud=self, new=instance, prev=None, action='create')

        # Done
        return instance

    def _update_instance(self, input: pd.BaseModel, *filter, **filter_by) -> ModelT:
        """ update() method: load an existing instance and modify it

        This method will ssn.query() it, setattr() changes, do @saves_custom_fields(), but won't ssn.flush() it.
        Session operations are out of scope.

        Args:
            input: Input from the user: a validated Pydantic model.

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
            sa.exc.IntegrityError
        """
        # Raises: sqlalchemy.orm.exc.NoResultFound
        # Raises: sqlalchemy.orm.exc.MultipleResultsFound
        instance = self._query(*filter, **filter_by).one()
        prev = get_history_proxy_for_instance(instance, copy=self.COPY_INSTANCE_HISTORY)

        # Update it
        instance = self._update_instance_from_input(instance, input, exclude=self.crudsettings._exclude_on_update)

        # Hook
        self._instance_hook_presave(new=instance, prev=prev)

        # Signals
        crud_signals.on_update_prepared.send(type(self), crud=self, new=instance, prev=prev)
        crud_signals.on_save_prepared.send(type(self), crud=self, new=instance, prev=prev, action='update')

        # Done
        return instance

    def _delete_instance(self, *filter, **filter_by) -> ModelT:
        """ delete() method: delete an existing instance and return it

        This method will ssn.query() it ... and nothing else.
        Session operations are out of scope.

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
        """
        # Raises: sqlalchemy.orm.exc.NoResultFound
        # Raises: sqlalchemy.orm.exc.MultipleResultsFound
        instance = self._query(*filter, **filter_by).one()

        # Hook
        self._instance_hook_presave(new=None, prev=instance)

        # Signals
        crud_signals.on_delete_prepared.send(type(self), crud=self, prev=instance)
        crud_signals.on_save_prepared.send(type(self), crud=self, new=None, prev=instance, action='delete')

        # Done
        return instance

    def _instance_hook_presave(self, new: Optional[ModelT] = None, prev: Optional[ModelT] = None):
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

    # region Low-Level: assign values to attributes

    # Genus: _*_instance_from_input()
    # Input: Pydantic model
    # Output: SqlAlchemy Model, created/modified
    # Purpose: apply input model to actual SqlAlchemy model

    # Methods that simply create/modify an instance from an input
    # Create/Update an instance using the input model

    def _create_instance_from_input(self, input: pd.BaseModel, *, exclude: Set[str]) -> ModelT:
        """ Given an `input` model, create a new SA Model, do @saves_custom_fields(), return """
        input_dict = input.dict(exclude_unset=True, exclude=exclude)

        # Save, wrapped with @saves_custom_fields() handler
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)
        instance = self._create_instance_from_input_dict(input_dict)
        saves_custom_fields.save(self, custom_fields, instance, None)

        return instance

    def _update_instance_from_input(self, instance: ModelT, input: pd.BaseModel, *, exclude: Set[str]) -> ModelT:
        """ Given an `input` and an `instance`, update it, do @saves_custom_fields(), return """
        input_dict = input.dict(exclude_unset=True, exclude=exclude)

        # Save, wrapped with @saves_custom_fields() handler
        custom_fields = saves_custom_fields.pluck_custom_fields(self, input_dict)
        instance = self._update_instance_from_input_dict(instance, input_dict)
        saves_custom_fields.save(self, custom_fields, instance, None)

        return instance

    # Create/Update an instance using the input dict

    def _create_instance_from_input_dict(self, input_dict: dict) -> ModelT:
        """ Given an `input_dict` dict, create a new Model """
        return self.crudsettings.Model(**input_dict)

    def _update_instance_from_input_dict(self, instance: ModelT, input_dict: dict) -> ModelT:
        """ Given an `input_dict` and an `instance`, update it """
        for name, value in input_dict.items():
            setattr(instance, name, value)  # triggers SqlAlchemy change detection logic
        return instance

    # endregion

    # endregion

    # region Querying

    def _query(self, *filter, **filter_by) -> Union[sa.orm.Query, Iterable[ModelT]]:
        """ Start a Query for loading instances of our Model

        Args:
            *filter: SqlAlchemy filter() expressions (Model.field == value)
            **filter_by: SqlAlchemy filter_by() expressions ( { 'field_name': value } )
        """
        # Query
        q = self.ssn.query(self.crudsettings.Model)

        # We have to apply our filtering in advance, because later on, someone (like MongoSQL) may put on a LIMIT,
        # and no filter() will be possible anymore
        if filter:
            q = q.filter(*filter)
        if filter_by:
            q = q.filter_by(**filter_by)

        # Customization
        q = self.crudsettings._crud_query_customize(self, q)

        # Done
        return q


    # endregion


class CrudBase(SimpleCrudBase[ModelT], Generic[ModelT, ResponseValueT]):
    """ Feature-complete Crud Handler for your application's business logic

    In addition to SimpleCrudBase, provides:

    * Customizable _filter() to specify which objects fall into the scope of this handler
    * Customizable _filter1() to specify how to find one particular entity.
      Initially, geared up to find objects by their primary key
    * Works with SqlAlchemy Session and actually stores objects into the database
    * Provides CRUD signals
    * Does not commit(). You have to commit() manually
    """

    def __init__(self, ssn: sa.orm.Session, *, query_object: QueryObject = None, **kwargs):
        """

        Args:
            **kwargs: Filtering values for filter() for every operation
        """
        super().__init__(ssn, query_object=query_object)
        self.kwargs = kwargs

    __slots__ = 'kwargs',

    # region Filtering

    # These methods customize how your CRUD operations find objects to work with
    # Implement the _filter() and _filter1() methods

    def _filter(self, **kwargs: UserFilterValue) -> Iterable[sa.sql.expression.BinaryExpression]:
        """ Filter expression for all methods. Override and customize to react to user-supplied `kwargs`

        Args:
            **kwargs: User-supplied input for filtering.
                For instance, these can be the arguments of your view.
        """
        return ()

    def _filter1(self, **kwargs: UserFilterValue) -> Iterable[sa.sql.expression.BinaryExpression]:
        """ Filter expression for get(), update(), delete()

        NOTE: the default implementation already filters by the primary key and users _filter().
        You do not have to worry about those!

        Args:
            **kwargs: User-supplied input that is supposed to identify the object, e.g., by primary key
        """
        # The default implementation: _filter() + primary key filter
        return (
            *self._filter(**kwargs),
            *self._filter_primary_key(kwargs),
        )

    def _filter_primary_key(self, kwargs: Mapping[str, UserFilterValue]):
        """ Find an instance by its primary key values

        Args:
            kwargs: User-supplied input for filtering. Must contain primary key { name => value } pairs
        """
        return (
            getattr(self.crudsettings.Model, pk_field) == kwargs.get(pk_field, None)
            for pk_field in self.crudsettings._primary_key
        )

    # endregion


    # region CRUD operations

    # Genus: CRUD() methods
    # input: **kwargs, Pydantic model or dict
    # output: Pydantic model or dict
    # They call: _session_*_instance()
    # Purpose: top-level CRUD methods that implement the full data cycle

    # TODO: optionally disable validation for response schemas (only in testing)

    # The final CRUD operations.
    # They transparently work with Pydantic models both on the input and on the output. SqlAlchemy is not visible.
    # Every method accepts **kwargs: the custom data received from the user for filtering. Typically, view arguments.

    def get(self, **kwargs: UserFilterValue) -> ResponseValueT:
        """ get() method: load a single object

        Args:
            **kwargs: filtering arguments

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
        """
        instance = self._session_get_instance(**kwargs)
        return self._instance_output(instance, self.crudsettings.GetResponseSchema)

    def list(self, **kwargs: UserFilterValue) -> Generator[ResponseValueT, None, None]:
        """ list() method: load multiple objects using criteria """
        instances = self._list_instances(**kwargs)
        return (
            self._instance_output(instance, self.crudsettings.ListResponseSchema)
            for instance in instances
        )

    # NOTE: create() and update() methods receive either a dict or a Pydantic model.
    # In both cases, the data will be validated.
    # Extra fields are ignored.

    def create(self, input: Union[InstanceDict, pd.BaseModel]) -> ResponseValueT:
        """ create() method: create a new object in the database

        Args:
            input: input values for the new object. A Pydantic model or a dict

        Raises:
            sa.exc.IntegrityError
        """
        input = self.crudsettings.CreateInputSchema.parse_obj(input) if not isinstance(input, self.crudsettings.CreateInputSchema) else input
        instance = self._session_create_instance(input)
        return self._instance_output(instance, self.crudsettings.CreateResponseSchema)

    def update(self, input: Union[InstanceDict, pd.BaseModel], **kwargs: UserFilterValue) -> ResponseValueT:
        """ update() method: load an existing object from the database and modify it

        Args:
            input: new values for the object. A Pydantic model or a dict.
                If it contains a primary key, it may be used instead of `kwargs`.
            **kwargs: filtering arguments

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
            sa.exc.IntegrityError
        """
        input = self.crudsettings.UpdateInputSchema.parse_obj(input) if not isinstance(input, self.crudsettings.UpdateInputSchema) else input
        instance = self._session_update_instance(input, **kwargs)
        return self._instance_output(instance, self.crudsettings.UpdateResponseSchema)

    def delete(self, **kwargs: UserFilterValue) -> ResponseValueT:
        """ delete() method: delete an existing object from the database

        Args:
            **kwargs: filtering arguments

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
        """
        instance = self._session_delete_instance(**kwargs)
        return self._instance_output(instance, self.crudsettings.DeleteResponseSchema)

    def create_or_update(self, input: Union[InstanceDict, pd.BaseModel], **kwargs: UserFilterValue) -> ResponseValueT:
        """ update() an object if a primary key was provided in the `input`, create() it otherwise

        This method may look a little odd, but the default policy of this CrudBase is to disallow customization of primary keys.
        That is, if you try to save User(id=100, ...), it will assume that you are updating an existing user.
        It will not let you choose `id=100` just because you like it: it will try to find such a user, and fail if there is none.

        Args:
            input: an object. If a primary key is set, update() will be performed. If not, create() will be done.

        Raises:
            sa.exc.NoResultFound
            sa.exc.MultipleResultsFound
            sa.exc.IntegrityError
        """
        assert self.crudsettings._create_or_update_enabled  # Must be enabled in the CrudSettings
        input = self.crudsettings.CreateOrUpdateInputSchema.parse_obj(input)
        instance = self._session_create_or_update_instance(input, **kwargs)
        return self._instance_output(instance, self.crudsettings.CreateOrUpdateResponseSchema)

    # endregion



    # region Low-level CRUD operations

    # These methods implement CRUD operations on SqlAlchemy instances.
    # This is unlike the get()/list()/create()/update()/delete() operations that work with Pydantic models.



    # region Session Operations

    # Genus: _session_*_instance() methods
    # input: **kwargs, Pydantic model
    # output: SqlAlchemy instance
    # They call: _*_instance()
    # Purpose: use Session to load/save things

    # These methods implement the SqlAlchemy Session saving logic

    def _session_get_instance(self, **kwargs: UserFilterValue) -> ModelT:
        """ Session support for get(): load an instance by filtering """
        return self._get_instance(**kwargs)

    def _session_list_instances(self, **kwargs: UserFilterValue) -> Iterable[ModelT]:
        """ Session support for list(): load instances by filtering """
        return self._list_instances(**kwargs)

    def _session_create_instance(self, input: pd.BaseModel) -> ModelT:
        """ Session support for create(): create an instance and flush() it """
        # Create
        instance = self._create_instance(input)

        # Flush
        self.ssn.add(instance)
        self.ssn.flush()

        # Signals
        crud_signals.on_create.send(type(self), crud=self, new=instance)
        crud_signals.on_save.send(type(self), crud=self, new=instance, prev=None, action='create')

        # Done
        return instance

    def _session_update_instance(self, input: pd.BaseModel, **kwargs: UserFilterValue) -> ModelT:
        """ Session support for update(): load an instance, modify it, flush() it """
        # Update
        instance = self._update_instance(input, **kwargs)
        prev = get_history_proxy_for_instance(instance)  # returns the proxy that has already been initialized by _update_instance()

        # Flush
        self.ssn.add(instance)
        self.ssn.flush()

        # Signals
        crud_signals.on_update.send(type(self), crud=self, new=instance, prev=prev)
        crud_signals.on_save.send(type(self), crud=self, new=instance, prev=prev, action='update')

        # Done
        return instance

    def _session_delete_instance(self, **kwargs: UserFilterValue) -> ModelT:
        """ Session support for delete(): load an instance, Session.delete() it, flush it  """
        # Delete
        instance = self._delete_instance(**kwargs)

        # Workaround: remove all possible lazy loads and raiseloads. raiseload() is especially harmful here:
        # SqlAlchemy will do cascade deletions, and it will need the values of foreign key fields.
        # See: https://github.com/sqlalchemy/sqlalchemy/issues/5398
        self.ssn.refresh(instance)

        # Flush
        self.ssn.delete(instance)
        self.ssn.flush()

        # Signals
        crud_signals.on_delete.send(type(self), crud=self, prev=instance)
        crud_signals.on_save.send(type(self), crud=self, new=None, prev=instance, action='delete')

        # Done
        return instance

    def _session_create_or_update_instance(self, input: pd.BaseModel, **kwargs) -> ModelT:
        """ Session support for create_or_update(): choose _create_instance() or _update_instance() """
        # Is there a primary key inside?
        pk_provided = self.crudsettings._primary_key_provided(input)

        # Update
        if pk_provided:
            return self._session_update_instance(input, **kwargs)
        else:
            return self._session_create_instance(input)

    # endregion


    # region CRUD operations

    # Genus: _*_instance() overrides
    # Purpose: implement CRUD on instance level
    # Twist: apply filter() and filter1()

    # These methods override SimpleCrudBase methods and add support for filter() & filter1()

    def _get_instance(self, **kwargs: UserFilterValue) -> ModelT:
        return super()._get_instance(*self._filter1(**{**self.kwargs, **kwargs}))

    def _list_instances(self, **kwargs: UserFilterValue) -> Iterable[ModelT]:
        return super()._list_instances(*self._filter(**{**self.kwargs, **kwargs}))

    def _update_instance(self, input: pd.BaseModel, **kwargs: UserFilterValue) -> ModelT:
        # Pull the primary key from the `input`, if provided
        pk_fields_in_input = set(self.crudsettings._primary_key) & input.__fields_set__
        kwargs.update({pk_field: getattr(input, pk_field)
                       for pk_field in pk_fields_in_input
                       if pk_field not in kwargs})

        # Update
        return super()._update_instance(input, *self._filter1(**{**self.kwargs, **kwargs}))

    def _delete_instance(self, **kwargs: UserFilterValue) -> ModelT:
        return super()._delete_instance(*self._filter1(**{**self.kwargs, **kwargs}))

    # endregion

    # region Output

    def _instance_output(self, instance: ModelT, schema: Type[pd.BaseModel]) -> ResponseValueT:
        """ Convert an SqlAlchemy instance to the final output value """
        # Use Pydantic to convert it
        return schema.from_orm(instance)

    # region

    # endregion


    # region Querying

    @contextmanager
    def transaction(self: Type[CrudHandlerT]) -> ContextManager[CrudHandlerT]:
        """ Wrap a section of code into a Crud transaction. commit() if everything goes fine; rollback() if not

        Example:
            with UserCrud(ssn, query_object=query).transaction() as crud:
                user = crud.update(user, id=id)
                return {'user': user}
        """
        try:
            yield self
        except Exception:
            self.rollback()
            raise
        else:
            self.commit()

    def commit(self) -> sa.orm.Session:
        """ Actually commit the changes.

        Note that no other place in this class performs a commit!
        You have to call it when you're done with this CRUD object.
        """
        # Send signals and commit
        crud_signals.on_commit_before.send(type(self), crud=self)
        self.ssn.commit()
        crud_signals.on_commit_after.send(type(self), crud=self)
        return self.ssn

    def rollback(self) -> sa.orm.Session:
        """ Send signals and Session.rollback() """
        # Send signals and rollback
        crud_signals.on_rollback_before.send(type(self), crud=self)
        self.ssn.rollback()
        crud_signals.on_rollback_after.send(type(self), crud=self)
        return self.ssn

    # endregion


    # TODO: _method_create_or_update_many() from MongoSQL 2.x


class saves_custom_fields(decomarker):
    """ A decorator that marks a method that customizes the saving of certain fields, e.g. relationships.

    It's not safe to *just* let users save relationships and some other fields.
    With the help of this decorator, they are plucked out of the input and handled manually by your function.

    Example:
        ABSENT = object()

        class UserCrud(CrudBase):
            ...
            @saves_custom_fields('articles')
            def save_articles(self, /, new: User, prev: User = None, *, articles = ABSENT):
                if articles is not ABSENT:
                    ...  # custom article-saving logic

    You can use it to save any attributes that require custom behavior, not just relationships.

    The arguments are:

    * new: The instance that is being created/modified
    * prev: The unmodified versions of this instance (only during update())
    * **fields: the values of the fields that you have asked for

    Note that this method is called always, even if no `**fields` have actually been provided.
    """
    # The list of fields that this method is capable of saving.
    field_names = Sequence[str]

    def __init__(self, *field_names: str):
        """ Decorate a method that can save custom fields

        Args:
            *field_names: List of field names that it handles
        """
        super().__init__()
        self.field_names = field_names

    @classmethod
    def save(cls, crud: SimpleCrudBase, plucked_data: Mapping['saves_custom_fields', dict], new: object, prev: object = None):
        for handler, kwargs in plucked_data.items():
            handler.func(crud, new, prev, **kwargs)

    @classmethod
    def pluck_custom_fields(cls, crud: SimpleCrudBase, input_dict: dict) -> Mapping['saves_custom_fields', dict]:
        """ Given an `input_dict`, pluck all custom fields and stash them

        Args:
            crud: The Crud handler
            input_dict: The input dictionary to pluck the values from

        Returns:
            a mapping that will soon be used to call custom fields' handlers.
            It contains: { saves_custom_fields handelr => method kwargs }
        """
        ret = {}
        remove_fields = set()

        # Go through every handler
        for handler in cls.all_decorated_from(type(crud)):
            # For every handler, collect arguments from the dict
            ret[handler] = {
                # NOTE: if an argument has not been provided, use `ABSENT`
                # We don't use `None` to differentiate from a `None` provided by the user
                field_name: input_dict.get(field_name)
                for field_name in handler.field_names
                if field_name in input_dict
            }

            # Remember the fields to remove
            remove_fields.update(handler.field_names)

        # Remove the fields from the dict
        for remove_field in remove_fields:
            if remove_field in input_dict:
                del input_dict[remove_field]

        # Done
        return ret

    @classmethod
    def all_field_names_from(cls, CrudClass: Type[SimpleCrudBase]) -> Set[str]:
        """ Get the names of all custom fields """
        return set().union(*(
            handler.field_names
            for handler in cls.all_decorated_from(CrudClass)
        ))
