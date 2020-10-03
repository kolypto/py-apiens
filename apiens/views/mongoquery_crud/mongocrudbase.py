import mongosql
import sqlalchemy as sa
import sqlalchemy.orm
from typing import Union, Iterable, ClassVar, Generic

from apiens.views.crud import CrudBase
from apiens.views.crud.crudbase import ModelT, ResponseValueT
from apiens.views.mongoquery_crud.defs import QueryObject
from apiens.views.mongoquery_crud.mongocrud_settings import MongoCrudSettings


class MongoCrudBase(CrudBase[ModelT, ResponseValueT], Generic[ModelT, ResponseValueT]):
    """ MongoSQL-enabled CRUD """

    crudsettings: ClassVar[MongoCrudSettings]

    # A QueryObject from the request
    query_object: QueryObject

    def __init__(self, ssn: sa.orm.Session, *, query_object: QueryObject = None, **kwargs):
        super().__init__(ssn, **kwargs)
        self.query_object = query_object

    __slots__ = 'query_object',

    def _mongoquery(self, mq: mongosql.MongoQuery) -> mongosql.MongoQuery:
        """ Customize the MongoQuery that this Crud Handler is going to use

        This hook is called right before the MongoQuery is finalized with .end()
        """
        return mq

    def _query(self, *filter, **filter_by) -> Union[sa.orm.Query, Iterable[ModelT]]:
        query = super()._query(*filter, **filter_by)

        if self.crudsettings._mongoquery_enabled:
            # Init MongoQuery
            mq = self.crudsettings._mongoquery_for_crud(self, query)

            # crud._mongoquery() hook
            mq = self._mongoquery(mq)

            # Finish
            query = mq.end()

        return query
