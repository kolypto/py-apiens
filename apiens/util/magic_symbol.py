class MagicSymbol:
    """ A named symbol that prevents any other comparison but the `is` operator

    Because developers may accidentally forget to check for the `value is NOT_SET` case,
    we will throw exceptions in case the object is used for anything else but the `is` comparison.

    Example:
        MISSING = MagicSymbol('MISSING')

        def myfunction(param1, param2=None, param3=MISSING):
            if param3 is MISSING:
                ...
    """
    __slots__ = ('_name',)

    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return self._name

    def useless(self, *args):
        raise AssertionError(
            f'You are trying to use the symbol `{self!r}` as a value. Probably, you didn\'t expect to get it here. '
            f'Please make sure that your code supports `{self!r}` by using the `is` comparison: the only operator it supports.'
        )

    __lt__ = __le__ = __eq__ = __ne__ = __ge__ = __gt__ = useless  # type: ignore[assignment]
    __bool__ = __str__ = __int__ = useless  # type: ignore[assignment]
    __add__ = __sub__ = __mul__ = useless
    __and__ = __or__ = __rand__ = __ror__ = useless


# MISSING - a placeholder for a missing value.
#
# Needed when you want to distinguish two cases:
#   1. value is set to None
#   2. value is not set at all
#
# For example, that may be a function parameter:
#
#     def update_user(user, new_login=MISSING, new_password=MISSING):
#        if new_login is not MISSING:
#            user.login = new_login
#        if new_password is not MISSING:
#            user.password = new_password
#
# That is, it allows to distinguish "don't touch this value" from "set this value to None".
MISSING = MagicSymbol('MISSING')
