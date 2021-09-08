import dis
from collections import abc


def simple_function(maxlines: int = 20, check: bool = True):
    """ Assert: keep your functions simple """
    def decorator(func):
        # Check disabled? Short-circuit
        if not check:
            return func

        # Use a set() to count the number of meaningful lines.
        # This ignores comments and docstrings!
        total_lines = len({
            instruction.starts_line
            for instruction in dis.Bytecode(func)
            if instruction.starts_line is not None
        })

        # Assert
        if total_lines > maxlines:
            raise LongFunctionError(func, total_lines, maxlines)

        # Done
        return func
    return decorator


class LongFunctionError(Exception):
    NAME = 'function'

    def __init__(self, func: abc.Callable, lines: int, maxlines: int):
        super().__init__(
            f'Function {func} has too many lines of code: {lines} > max {maxlines}. '
            f'Style guide for "{self.NAME}" only allows {maxlines} lines of code per {self.NAME}'
        )
        self.func = func
        self.maxlines = maxlines
