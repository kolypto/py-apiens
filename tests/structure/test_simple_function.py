import pytest

from apiens.structure.func.simple_function import simple_function, LongFunctionError


def test_simple_function():
    @simple_function(maxlines=1)
    def f():
        """
        Long docstring
        """

        # only a real line of code counts

        a = 1

    with pytest.raises(LongFunctionError):
        @simple_function(maxlines=1)
        def f():
            """
            Long docstring
            """

            # comment

            a = 1

            b = 2
