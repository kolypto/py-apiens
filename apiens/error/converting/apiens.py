from contextlib import contextmanager
import apiens.crud.exc

from apiens.util.exception import exception_from
from apiens.error import exc


@contextmanager  # and a decorator
def converting_apiens_error(*, exc=exc, _=exc._):
    """ Handle apiens errors

    Convert our errors into readable application errors
    """
    try:
        yield
    except apiens.crud.exc.BaseCrudError as e:
        new_error = convert_apiens_error(e, exc=exc, _=_)
        raise new_error or e


def convert_apiens_error(error: apiens.crud.exc.BaseCrudError, *, exc=exc, _=exc._):
    if isinstance(error, apiens.crud.exc.NoResultFound):
        e = exc.E_NOT_FOUND(
            _('Object not found'),
            _('Please check if your URL and input are correct')
        )
        return exception_from(e, error)
    elif isinstance(error, apiens.crud.exc.ValueConflict):
        e = exc.E_CONFLICT_DUPLICATE(
            _('Conflicting object found for {failed_columns}').format(failed_columns=', '.join(error.column_names)),
            _('Provide a unique value for {failed_columns}'),
            failed_columns=error.column_names,
        )
        return exception_from(e, error)
