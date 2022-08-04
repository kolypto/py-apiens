import pytest
from apiens.util.magic_symbol import MISSING


def test_magic_symbol():
    # The only way to use it
    MISSING is not False
    MISSING is not None

    # No other operator is allowed
    with pytest.raises(AssertionError):
        MISSING != 0
    
    with pytest.raises(AssertionError):
        str(MISSING)
