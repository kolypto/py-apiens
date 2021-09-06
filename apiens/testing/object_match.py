

class ObjectMatch:
    """ Unit test helper: an object for == comparisons with other objects field by field.

    Receives custom fields. When compared to another object, performs a field-by-field comparison.
    Only checks the fields from itself; any additional fields that the other object may contain are ignored.

    Example:
         models.User(...) == ObjectMatch(models.User, id=Parameter(), login='kolypto', ...)
    """
    __slots__ = ('_type', '_fields')

    def __init__(self, /, type, **fields):
        self._type = type
        self._fields = fields

    def __eq__(self, other: object):
        assert isinstance(other, self._type), f'{type(other)!r} is not an instance of {self._type}'

        # Iterate our fields only. This will provide the "partial matching" behavior
        for name, value in self._fields.items():
            # will recurse into ObjectMatch.__eq__ if one is encountered
            other_value = getattr(other, name)

            # Compare
            # Catch errors in case subsequent checks fail
            try:
                values_are_equal = value == other_value
            except Exception as e:
                raise
                # raise AssertionError(f'Error comparing values of attribute {name!r}') from e  # too much nesting

            # Finally, assert
            assert values_are_equal, f'{other!r} == {self!r} because of {value!r} != {other_value}'

            # if value != getattr(other, name):
            #     return False

        return True

    def __repr__(self):
        return '{type}({fields})'.format(type=self._type.__name__, fields=', '.join(f'{k}={v!r}' for k, v in self._fields.items()))


class DictMatch(dict):
    """ Partial match of a dictionary to another one, with nice diffs

    Example:
        assert DictMatch({'praenomen': 'Gaius'}) == {'praenomen': 'Gaius', 'nomen': 'Julius', 'cognomen': 'Caesar'}
    """
    def __eq__(self, other: dict):
        # Only equal if have the same type
        if not isinstance(other, dict):
            return False

        # Copy the missing values from another dict (in order to have nice diffs)
        self.update({k: v for k, v in other.items() if k not in self})

        # Compare
        return all(other[name] == value for name, value in self.items())


class Parameter:
    """ A parameter that, when compared, grabs the value. Useful for grabbing primary keys.

    Example:
        assert result == {
            'id': (id := Parameter()),
            'login': 'kolypto',
        }
        assert id.value is not None
    """
    __slots__ = ('_grabbed_value',)

    def __init__(self):
        self._grabbed_value = self.NO_VALUE

    @property
    def value(self):
        """ Get the grabbed value """
        assert self._grabbed_value is not self.NO_VALUE, 'NO_VALUE'
        return self._grabbed_value

    def __eq__(self, other):
        # Parameter resolved. Compare. Return result.
        if self._grabbed_value is not self.NO_VALUE:
            assert self._grabbed_value == other
            return self._grabbed_value == other
        # Parameter unresolved. Got a new value. Remember. Compare.
        elif self._grabbed_value is self.NO_VALUE and not isinstance(other, Parameter):
            self._grabbed_value = other
            return True
        # Parameter unresolved. Comparing to another parameter. Ouch.
        else:
            raise AssertionError

    def __repr__(self):
        if self._grabbed_value is self.NO_VALUE:
            return '<NO VALUE>'
        return repr(self._grabbed_value)

    NO_VALUE = object()
