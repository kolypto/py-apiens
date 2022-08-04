import jessiql
from contextlib import contextmanager

from apiens.util.exception import exception_from
from apiens.error import exc


@contextmanager  # and a decorator
def converting_jessiql_errors(*, exc=exc, _=exc._):
    """ Handle JessiQL errors

    Convert JessiQL errors into readable application errors

    Raises:
        exc.E_API_ARGUMENT: query object failures: invalid columns and relationships
        exc.F_BAD_API_REQUEST: other query errors, e.g. wrong use of cursors
    """
    try:
        yield
    except jessiql.exc.BaseJessiqlException as e:
        new_error = convert_jessiql_error(e, exc=exc, _=exc._)
        raise new_error or e


def convert_jessiql_error(error: jessiql.exc.BaseJessiqlException, *, exc=exc, _=exc._):
    """ Given a JessiQL exception, convert it into a `exc` API exception """
    if isinstance(error, jessiql.exc.QueryObjectError):
        e = exc.E_API_ARGUMENT(
            _('Query Object error: {message}').format(message=str(error)),
            _('Report this issue to the developer in order to have this query fixed'),
            name='query',
        )
        return exception_from(e, error)

    elif isinstance(error, jessiql.exc.InvalidColumnError):
        e = exc.E_API_ARGUMENT(
            _('Invalid column "{column_name}" for "{model}" specified in {where}'),
            _('Report this issue to the developer in order to have this query fixed'),
            name=error.where,
        ).format(
            column_name=error.column_name,
            model=error.model,
            where=error.where,
        )
        return exception_from(e, error)
    elif isinstance(error, jessiql.exc.InvalidRelationError):
        e = exc.E_API_ARGUMENT(
            _('Invalid relation "{column_name}" for "{model}" specified in {where}'),
            _('Report this issue to the developer in order to have this query fixed'),
            name=error.where,
        ).format(
            column_name=error.column_name,
            model=error.model,
            where=error.where,
        )
        return exception_from(e, error)
    elif isinstance(error, jessiql.exc.RuntimeQueryError):
        e = exc.F_BAD_API_REQUEST(
            _('JessiQL failed: {message}'),
            _('Report this issue to the developer in order to have this query fixed'),
        ).format(message=str(error))
        return exception_from(e, error)
