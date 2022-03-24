from collections import abc


class unsorted:
    """ A container for testing lists of unsorted objects

    This is useful in case your API returns [A,B,C,D] in random order, and you want to use a simple `==` check.

    Why would you need this? Just set() both and compare, right?
    Not quite. Sometimes you want to compare two nested dictionaries like this:

        assert results = {
            ...
            'roles': ['admin', 'employee'],
            ...
        }

    and because you have one unpredictable list, the whole assertion has to be rewritten.
    Unsorted to the resque:

        assert results = {
            ...
            'roles': unsorted(['admin', 'employee']),
            ...
        }
    """

    def __init__(self, sequence: abc.Iterable, key=None):
        # Don't use `set()` because otherwise duplicate items would be collapsed.
        self.__key = key
        self.__seq = sorted(sequence, key=key)

    __slots__ = '__seq', '__key'

    def __eq__(self, other: abc.Iterable):  # type: ignore[override]
        return self.__seq == sorted(other, key=self.__key)

    def __repr__(self):
        return repr(self.__seq)
