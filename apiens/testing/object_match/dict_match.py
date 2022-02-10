from collections import abc


class DictMatch(dict):
    """ Partial match of a dictionary to another one, with nice diffs

    NOTE: it won't work with dict subclasses! Convert them to pure `dict` first :)

    Example:
        assert DictMatch({'praenomen': 'Gaius'}) == {'praenomen': 'Gaius', 'nomen': 'Julius', 'cognomen': 'Caesar'}
    """
    def __eq__(self, other):
        # Only equal if have the same type
        if not isinstance(other, abc.Mapping):
            return False

        # for key, value in self.items():
        #     other_value = other[key]
        #     values_are_equal = key in other and other_value == value
        #     assert values_are_equal, f'{other!r} == {self!r} because of `{key}` {value!r} != {other_value}'

        # Compare
        equal = all(other[name] == value for name, value in self.items())

        # Copy the missing values from another dict (in order to have nice diffs)
        if not equal:
            self.update({k: v for k, v in other.items() if k not in self})

        # Done
        return equal
