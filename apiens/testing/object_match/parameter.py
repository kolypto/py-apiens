""" Parameter: capture a value of a nested field in a complex object """ 

class Parameter:
    """ Grab a parameter during comparison: e.g. a dynamic primary key

    Example:
        assert result == {
            'id': (id := Parameter()),
            'login': 'kolypto',
        }
        assert id.value is not None
    """
    __slots__ = '_grabbed_value',

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
