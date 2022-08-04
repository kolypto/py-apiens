""" Tools to convert exceptions into Application API errors """

from .base import ConvertsToBaseApiExceptionInterface
from .exception import convert_unexpected_error, converting_unexpected_errors
from .apiens import convert_apiens_error, converting_apiens_error
from .sqlalchemy import convert_sa_error, converting_sa_errors

try:
    from .jessiql import convert_jessiql_error, converting_jessiql_errors
except ImportError as e:
    if e.name != 'jessiql':
        raise
