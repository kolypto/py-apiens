class ObjectMatch:
    """ Unit test helper: an object for == comparisons with other objects field by field.

    Receives custom fields. When compared to another object, performs a field-by-field comparison.
    Only checks the fields from itself; any additional fields that the other object may contain are ignored.

    Example:
         models.User(...) == ObjectMatch(id=Parameter(), login='kolypto', ...)
    """
    __slots__ = '_fields',

    def __init__(self, **fields):
        self._fields = fields

    def __eq__(self, other: object):
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
            assert values_are_equal, f'{other!r} == {self!r} because of `{name}` {value!r} != {other_value}'

            # if value != getattr(other, name):
            #     return False

        return True

    def __repr__(self):
        return '{type}({fields})'.format(type='Object', fields=', '.join(f'{k}={v!r}' for k, v in self._fields.items()))
