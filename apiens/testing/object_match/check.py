""" Check: use functions to test nested values of an object """ 

from collections import abc
from typing import Any


class check:
    """ Test equality with a value using a callable

    Example:
        assert result == {
            'user': {
                'login': 'admin',
                'age': check(lambda v: v > 0),
            }
        }
    """
    def __init__(self, check: abc.Callable[[Any], bool]):
        self.__check = check

    __slots__ = '__check'

    def __eq__(self, other):
        return self.__check(other)
