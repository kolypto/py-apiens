import mongosql
import pydantic as pd
import sa2schema
import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.orm.attributes
import sqlalchemy.orm.base
from nplus1loader import raiseload_all
from sqlalchemy.orm import load_only, defaultload
from typing import Union, Iterable, ClassVar, Generic, Type

from apiens.views.crud import CrudBase, UserFilterValue, InstanceDict
from apiens.views.crud.crudbase import SAInstanceT
from apiens.views.mongoquery_crud.defs import QueryObject
from apiens.views.mongoquery_crud.mongocrud_settings import MongoCrudSettings


# Generic[SAInstanceT]: your SqlAlchemy model
class MongoCrudBase(CrudBase[SAInstanceT, dict], Generic[SAInstanceT]):
    """ MongoSQL-enabled CRUD

    Additional features:

    * Crud operations load that absolute minimum number of fields
    * MongoSQL performs an additional SELECT query with user-defined customizations
    * MongoSQL tries to make this query as fast as possible
    * Returns plain dicts, not Pydantic models
    """

    crudsettings: ClassVar[MongoCrudSettings]

    # A QueryObject from the request
    query_object: QueryObject

    def __init__(self, ssn: sa.orm.Session, *, query_object: QueryObject = None, **kwargs):
        super().__init__(ssn, **kwargs)
        self.query_object = query_object

    __slots__ = 'query_object',

    # region CRUD methods

    def get(self, **kwargs: UserFilterValue) -> dict:
        # Don't use CrudBase.get() because it will load ORM objects, which is suboptimal.
        # Use MongoQuery instead
        return self._result_fetch_one(self.crudsettings.GetResponseSchema, **kwargs)

    def list(self, **kwargs: UserFilterValue) -> Iterable[dict]:
        return self._result_fetch_many(self.crudsettings.ListResponseSchema, **kwargs)

    def create(self, input: Union[InstanceDict, pd.BaseModel]) -> dict:
        # create()
        instance: SAInstanceT = super().create(input)

        # re-load the instance with the user's projection
        result = self._result_refetch_instance(self.crudsettings.CreateResponseSchema, instance)

        # Done
        return result

    def update(self, input: Union[InstanceDict, pd.BaseModel], **kwargs: UserFilterValue) -> dict:
        # update() the instance
        instance: SAInstanceT = super().update(input, **kwargs)

        # re-load the instance with the user's projection
        result = self._result_refetch_instance(self.crudsettings.UpdateResponseSchema, instance)

        # Done
        return result

    def delete(self, **kwargs: UserFilterValue) -> dict:
        # load the instance with a custom projection before it is removed!
        # This is the only way we can fetch all those relationships and everything
        result = self._result_fetch_one(self.crudsettings.DeleteResponseSchema, **kwargs)

        # delete()
        super().delete(**kwargs)

        # Done
        return result

    # endregion

    # region MongoSql Query

    def _result_refetch_instance(self, response_schema: Type[pd.BaseModel], instance: SAInstanceT) -> dict:
        """ Fetch the instance again through a MongoQuery and return an object """
        mq = self._mongoquery_instance_by_primary_key(instance)
        result = self._one_result_from_mongoquery(mq, response_schema)
        return result

    def _result_fetch_one(self, /, response_schema: Type[pd.BaseModel], **kwargs) -> dict:
        """ Fetch one object through a MongoQuery """
        mq = self._mongoquery(*self._filter1(**{**self.kwargs, **kwargs}))
        result = self._one_result_from_mongoquery(mq, response_schema)
        return result

    def _result_fetch_many(self, /, response_schema: Type[pd.BaseModel], **kwargs) -> Iterable[dict]:
        """ Fetch many objects through a MongoQuery """
        mq = self._mongoquery(*self._filter(**{**self.kwargs, **kwargs}))
        results = self._many_results_from_mongoquery(mq, response_schema)
        return results

    def _mongoquery(self, *filter, **filter_by) -> mongosql.MongoQuery:
        """ Start a MongoQuery to load instance[s]

        This method is used in get() an list(): using the filter from the user-supplied query
        """
        query = super()._query(*filter, **filter_by)
        return self.crudsettings._mongoquery(query, self.query_object)

    # Override the CrudBase output and let the instance pass through
    # We do it like this because we don't need that instance at all.
    # Instead, we'll make another query and fetch it with MongoSQL using the custom projection from the QueryObject

    def _instance_output(self, instance: SAInstanceT, schema: Type[pd.BaseModel]) -> SAInstanceT:
        return instance

    # endregion

    # region Query

    def _query(self, *filter, **filter_by) -> Union[sa.orm.Query, Iterable[SAInstanceT]]:
        # Prepare the query
        query = super()._query(*filter, **filter_by)

        # In MongoCrudBase, self._query() only serves the update() and delete() operations.
        # The update() and delete() don't usually need many fields.
        # Put a load_only() on it, so that it does not load more that necessary.
        query = query.options(
            load_only(
                # undefer the primary key and all the foreign keys
                *primary_and_foreign_keys_from(self.crudsettings.Model),
                # custom fields
                *self.crudsettings._load_only,
            ),
            # Be strict
            raiseload_all('*') if self.crudsettings._debug else defaultload([]),
        )

        # Done
        return query

    # endregion

    # region Helpers

    def _mongoquery_instance_by_primary_key(self, instance: SAInstanceT):
        """ Start a MongoQuery to load a known instance by primary key """
        # Extract the primary key and build the condition
        filter = self._filter_primary_key(
            # Use the instance dict as the `kwargs`.
            # This will work because `kwargs` is expected to contain attribute name-value pairs anyway
            kwargs=sa.orm.base.instance_dict(instance)
        )

        # mongoquery
        return self._mongoquery(*filter)

    def _one_result_from_mongoquery(self, mq: mongosql.MongoQuery, response_schema: Type[pd.BaseModel]) -> dict:
        """ Prepare a singular result from a MongoQuery """
        # Query
        query = mq.end()
        mq_instance = query.one()

        # Pluck
        result = mq.pluck_instance(mq_instance)

        # Optionally, in debug mode, validate the response model
        if self.crudsettings._debug:
            response_schema.parse_obj(result)

        # Done
        return result

    def _many_results_from_mongoquery(self, mq: mongosql.MongoQuery, response_schema: Type[pd.BaseModel]) -> Iterable[dict]:
        """ Prepare a plural result from a MongoQuery """
        mq_instances: Union[sa.orm.Query, Iterable[SAInstanceT]] = mq.end()

        # Pluck
        results = (
            mq.pluck_instance(mq_instance)
            for mq_instance in mq_instances
        )

        # Validate
        if self.crudsettings._debug:
            results = list(results)  # otherwise the generator would be exhausted
            for item in results:
                response_schema.parse_obj(item)

        # Done
        return results

    # endregion


def primary_and_foreign_keys_from(model: type) -> Iterable[sa.orm.attributes.InstrumentedAttribute]:
    """ Get model attributes: primary and foreign keys """
    columns_info = sa2schema.sa_model_info(model, types=sa2schema.AttributeType.COLUMN)
    attr_info: sa2schema.info.ColumnInfo
    return [
        attr_info.attribute
        for attr_name, attr_info in columns_info.items()
        if attr_info.primary_key or attr_info.foreign_key
    ]
