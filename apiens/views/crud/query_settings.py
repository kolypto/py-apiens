import sqlalchemy as sa
from typing import Type, Optional, ClassVar

import mongosql
from . import crudbase
from .crud_settings import CrudSettings
from .defs import QueryObject


class MongoSqlCrudMixin:
    """ A mixin for CrudBase that lets it customize a mongoquery """

    def _mongoquery(self, mq: mongosql.MongoQuery) -> mongosql.MongoQuery:
        """ Customize the MongoQuery that this Crud Handler is going to use

        This hook is called right before the MongoQuery is finalized with .end()
        """
        raise NotImplementedError


class MongoSqlCrudSetttings(CrudSettings):
    """ Settings object that enables MongoSql for a Crud Handler.

    Expectations:
    * crud.query_object: MongoSql query object
    * (optional) crud._mongoquery(_mongoquery: MongoQuery): a hook to customize the MongoQuery before it's finalized
    """
    # MongoQuery class to use for queries. Possible to customize.
    MONGOQUERY_CLASS: ClassVar[Type[mongosql.MongoQuery]] = mongosql.MongoQuery

    # MongoSQL default query object
    _query_defaults: Optional[dict] = None

    # The MongoQuery object that's going to be used for new queries
    _reusable_mongoquery: Optional[mongosql.MongoQuery] = None

    # Configure

    def mongosql_config(self, *,
                        query_defaults: dict = None,
                        **mongoquery_settings):
        """ Configure MongoSQL auerying

        Args:
            query_defaults: MongoSQL query defaults
            **mongoquery_settings: Settings for MongoQuery.
                Example: **mongosql.MongoQuerySettingsDict(...)
        """
        self._query_defaults = query_defaults or {}
        self._reusable_mongoquery = mongosql.Reusable(  # noqa
            self.MONGOQUERY_CLASS(self.Model, mongoquery_settings)
        )
        return self

    # Is configured?

    @property
    def _mongoquery_enabled(self):
        """ Check: MongoQuery configured and enabled? """
        return self._reusable_mongoquery is not None

    # Extension

    def _crud_query_customize(self, crud: 'crudbase.SimpleCrudBase', query: sa.orm.Query) -> sa.orm.Query:
        """ Add MongoSQL features to the Query.

        This one function gives you the full support for selection of fields, filtering, sorting, etc.
        Override it to customize.
        """
        if self._mongoquery_enabled:
            # Init MongoQuery
            mq = self._mongoquery_for_crud(crud, query)

            # crud._mongoquery() hook
            if hasattr(crud, '_mongoquery'):
                # See: MongoSqlCrudMixin._mongoquery
                mq = crud._mongoquery(mq)

            # Finish
            query = mq.end()

        # Done
        return query

    # Query

    def _mongoquery(self, query_object: QueryObject = None, from_query: Optional[sa.orm.Query] = None):
        """ Start a MongoSql query using the provided QueryObject and Query

        Args:
            query_object: MongoSql Query Object
            from_query: SqlAlchemy Query to start a MongoSql query from
        """
        # Merge the defaults
        query_obj = {**self._query_defaults, **(query_object or {})}

        # Go
        return self._reusable_mongoquery.from_query(from_query).query(**query_obj)

    def _mongoquery_for_crud(self, crud: 'crudbase.SimpleCrudBase', query: sa.orm.Query) -> mongosql.MongoQuery:
        """ Initialize a MongoQuery for a Crud Handler and its query object """
        # Initialize
        query_object = {**self._query_defaults, **(crud.query_object or {})}
        mq = self._mongoquery(query_object, query)

        # Done
        return mq
