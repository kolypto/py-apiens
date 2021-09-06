from collections import abc


class unsorted:
    """ A container for testing lists of unsorted objects

    This is useful in case your API returns [A,B,C,D] in random order, and you want to use a simple `==` check.

    Example:
        response['roles'] == unsorted(['admin', 'employee'])

    Why would you need this? Just set() both and compare, right?
    Not quite. Sometimes you want to compare two nested dictionaries like this:

        assert results = {
            ...
            ...
            ...
        }

    and this works, but a single unpredictable list would ruin this idea.
    Do you really have to replace the whole thing with a list of assertions because of this one value?

        assert results[...] == [...]
        assert results[...] == [...]
        assert results[...] == [...]

    No. Just use unsorted() and let it do the comparison for you :)
    """

    def __init__(self, sequence: abc.Sequence[abc.Hashable]):
        self.__seq = set(sequence)

    __slots__ = '__seq',

    def __eq__(self, other: abc.Iterable[abc.Hashable]):
        return self.__seq == set(other)

    def __repr__(self):
        return repr(self.__seq)
