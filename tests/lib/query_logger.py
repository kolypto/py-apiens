import re

from sqlalchemy import event
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import Query


def _insert_query_params(statement_str, parameters, dialect):
    """ Compile a statement by inserting *unquoted* parameters into the query """
    return statement_str % parameters


def stmt2sql(stmt):
    """ Convert an SqlAlchemy statement into a string """
    # See: http://stackoverflow.com/a/4617623/134904
    # This intentionally does not escape values!
    dialect = pg.dialect()
    query = stmt.compile(dialect=dialect)
    return _insert_query_params(query.string, query.params, pg.dialect())


def q2sql(q):
    """ Convert an SqlAlchemy query to string """
    return stmt2sql(q.statement)


class QueryCounter:
    """ Counts the number of queries """

    def __init__(self, engine):
        super(QueryCounter, self).__init__()
        self.engine = engine
        self.n = 0

    def start_logging(self):
        event.listen(self.engine, "after_cursor_execute", self._after_cursor_execute_event_handler, named=True)

    def stop_logging(self):
        event.remove(self.engine, "after_cursor_execute", self._after_cursor_execute_event_handler)
        self._done()

    def _done(self):
        """ Handler executed when logging is stopped """

    def _after_cursor_execute_event_handler(self, **kw):
        self.n += 1

    def print_log(self):
        pass  # nothing to do

    # Context manager

    def __enter__(self):
        self.start_logging()
        return self

    def __exit__(self, *exc):
        self.stop_logging()
        if exc != (None, None, None):
            self.print_log()
        return False


class QueryLogger(QueryCounter, list):
    """ Log raw SQL queries on the given engine """

    def _after_cursor_execute_event_handler(self, **kw):
        super(QueryLogger, self)._after_cursor_execute_event_handler()
        # Compile, append
        self.append(_insert_query_params(kw['statement'], kw['parameters'], kw['context']))

    def print_log(self):
        for i, q in enumerate(self):
            print('=' * 5, ' Query #{}'.format(i))
            print(q)


class ExpectedQueryCounter(QueryLogger):
    """ A QueryLogger that expects a certain number of queries, raises an error otherwise """

    def __init__(self, engine, expected_queries, comment):
        super(ExpectedQueryCounter, self).__init__(engine)
        self.expected_queries = expected_queries
        self.comment = comment

    def _done(self):
        if self.n != self.expected_queries:
            self.print_log()
            raise AssertionError('{} (expected {} queries, actually had {})'
                                 .format(self.comment, self.expected_queries, self.n))
