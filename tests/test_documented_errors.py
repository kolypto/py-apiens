import pytest

from apiens.structure.func.documented_errors import documented_errors, ErrorDoc, UndocumentedError


def test_documented_errors():
    # === Test: empty
    @documented_errors()
    def f(): pass
    assert documented_errors.get_from(f).errors == {}

    # === Test: empty docstring
    @documented_errors()
    def f(): """"""
    assert documented_errors.get_from(f).errors == {}

    # === Test: args
    @documented_errors({
        KeyError: 'not found',
    })
    def f(): pass
    assert documented_errors.get_from(f).errors == {
        KeyError: ErrorDoc(KeyError, 'KeyError', 'not found', description=None),
    }

    # === Test: parse docstring
    @documented_errors()
    def f():
        """

        Raises:
            KeyError: not found
        """
    assert documented_errors.get_from(f).errors == {
        KeyError: ErrorDoc(KeyError, 'KeyError', 'not found', description=None),
    }

    # === Test: check
    @documented_errors({KeyError: ''})
    def f():
        raise ValueError

    with pytest.raises(UndocumentedError):
        f()
