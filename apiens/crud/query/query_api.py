from __future__ import annotations

from collections import abc
from typing import Optional, Union

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.sql.elements

import jessiql
from ..base import ModelOperationBase, SAInstanceT
from ..crudparams import CrudParams


class QueryApi(ModelOperationBase[SAInstanceT]):
    # JessiQL Query Object
    query_object: jessiql.QueryObject

    def __init__(self,
                 ssn: sa.orm.Session,
                 params: CrudParams,
                 query_object: Union[jessiql.QueryObject, jessiql.QueryObjectDict] = None):
        super().__init__(ssn, params)
        self.query_object = jessiql.QueryObject.ensure_query_object(query_object)

        # Init JessiQL
        self.query = self.init_query()

    def list(self) -> list[dict]:
        self._filter_func = self.params.filter
        res = self.query.fetchall(self.ssn.get_bind())
        return res

    def get(self) -> Optional[dict]:
        self._filter_func = self.params.filter_one
        res = self.query.fetchone(self.ssn.get_bind())
        return res

    def count(self) -> int:
        self._filter_func = self.params.filter
        return self.query.count(self.ssn.get_bind())

    # The filter function that we decided to use
    _filter_func: abc.Callable[[], abc.Iterable[sa.sql.elements.BinaryExpression]]

    def init_query(self) -> jessiql.engine.QueryExecutor:
        """ Initialize JessiQL query """
        query = jessiql.QueryPage(self.query_object, self.params.crudsettings.Model)
        query.customize_statements.append(self._query_customize_statements)
        return query

    def _query_customize_statements(self, q: jessiql.Query, stmt: sa.sql.Select) -> sa.sql.Select:
        if q.query_level == 0:
            stmt = stmt.filter(*self._filter_func())
            return stmt
        else:
            return stmt
            # TODO: insert security hooks for deeper levels
            raise NotImplementedError
