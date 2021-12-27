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
        """ CRUD method: list, load a list of objects """
        self._filter_func = self.params.filter
        res = self.query.fetchall(self.ssn.connection())
        return res

    def get(self) -> Optional[dict]:
        """ CRUD method: get, load one object by primary key """
        self._filter_func = self.params.filter_one
        res = self.query.fetchone(self.ssn.connection())
        return res

    def count(self) -> int:
        """ CRUD method: count the number of matching objects """
        self._filter_func = self.params.filter
        return self.query.count(self.ssn.connection())

    # The filter function that we decided to use
    _filter_func: abc.Callable[[], abc.Iterable[sa.sql.elements.BinaryExpression]]  # TODO: implement some switch that toggles between self.params.filter/filter1. Perhaps, inside CrudParams: store the current API method?

    def init_query(self) -> jessiql.engine.QueryExecutor:
        """ Initialize JessiQL query """
        query = jessiql.QueryPage(self.query_object, self.params.crudsettings.Model)  # TODO: customize which class to use
        query.customize_statements.append(self._query_customize_statements)
        return query

    def _query_customize_statements(self, q: jessiql.Query, stmt: sa.sql.Select) -> sa.sql.Select:
        """ JessiQL query filter """
        if q.query_level == 0:
            stmt = stmt.filter(*self._filter_func())
            return stmt
        else:
            return stmt
            # TODO: insert security hooks for deeper levels
            raise NotImplementedError
