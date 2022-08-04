import pytest
from apiens.util.exception import exception_from
from apiens.util.magic_symbol import MISSING


def test_exception_from():
    # Create an error
    try:
        raise ValueError('A')
    except ValueError as value_error:
        # Use exception_from()
        new_error = RuntimeError('B')
        exception_from(new_error, value_error)

        # Try raising it
        try:
            raise new_error
        except Exception as e:
            assert e.__cause__ == value_error

def test_magic_symbol():
    # The only way to use it
    MISSING is not False
    MISSING is not None

    # No other operator is allowed
    with pytest.raises(AssertionError):
        MISSING != 0
    
    with pytest.raises(AssertionError):
        str(MISSING)
