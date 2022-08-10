from __future__ import annotations

from collections import abc
from typing import Optional, Union, TypeVar, Generic

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.sql.elements

import jessiql
from jessiql.util.sacompat import stmt_filter
from ..base import ModelOperationBase, SAInstanceT
from ..crudparams import CrudParams
from .. import exc


QueryT = TypeVar('QueryT', bound=jessiql.Query)


class QueryApi(ModelOperationBase[SAInstanceT], Generic[SAInstanceT, QueryT]):
    """ CRUD API implementation: queries

    Implements read methods for CRUD: list, get, count
    """
    # JessiQL Query Object
    query_object: jessiql.QueryObject

    # JessiQL Query
    query: QueryT

    def __init__(self,
                 ssn: sa.orm.Session,
                 params: CrudParams,
                 query_object: Union[jessiql.QueryObject, jessiql.QueryObjectDict] = None):
        super().__init__(ssn, params)
        self.query_object = jessiql.QueryObject.ensure_query_object(query_object)

        # Init JessiQL
        self.query = self.init_query()

    def list(self) -> list[dict]:
        """ CRUD method: list, load a list of objects """
        self._filter_func = self.params.filter  # type: ignore[assignment,misc]
        res = self.query.fetchall(self.ssn.connection())
        return res

    def get(self) -> Optional[dict]:
        """ CRUD method: get, load one object by primary key """
        self._filter_func = self.params.filter_one  # type: ignore[assignment,misc]

        with exc.converting_sa_errors(Model=self.query.Model):
            res = self.query.fetchone(self.ssn.connection())

        return res

    def count(self) -> int:
        """ CRUD method: count the number of matching objects """
        self._filter_func = self.params.filter  # type: ignore[assignment,misc]
        return self.query.count(self.ssn.connection())

    # The filter function that we decided to use
    _filter_func: abc.Callable[[], abc.Iterable[sa.sql.elements.BinaryExpression]]

    # Which JessiQL Query class to use: Query, QueryPage, etc
    QUERY_CLS: type[QueryT] = jessiql.Query  # type: ignore[assignment]

    def init_query(self) -> QueryT:
        """ Initialize JessiQL query """
        query = self.QUERY_CLS(self.query_object, self.params.crudsettings.Model, self.params.crudsettings.query_settings)
        query.customize_statements.append(self._query_customize_statements)  # type: ignore[arg-type]
        return query

    def _query_customize_statements(self, q: jessiql.Query, stmt: sa.sql.Select) -> sa.sql.Select:
        """ JessiQL query filter """
        if q.query_level == 0:
            stmt = stmt_filter(stmt, *self._filter_func())  # type: ignore[misc]
            return stmt
        else:
            return stmt
            # TODO: insert security hooks for deeper levels. Perhaps, use a mapping of `q.path` chains? Involve CrudParams with a callback? provide multiple ways with mixins/decorators?
            raise NotImplementedError
