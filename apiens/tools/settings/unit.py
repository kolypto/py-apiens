from __future__ import annotations

import pint  # type: ignore[import]
from typing import Optional


class unit:
    """ Convert quantities from one unit to another to make configurations more readable

    The purpose of this class is purely decorative :)

    Example:
        from apiens.tools.settings.unit import unit

        s = unit('s')
        ms = unit('ms')

        timeout = 1 * s
        timeout_ms = timeout >> ms

    This works because:
    * Multiplication `*` is overridden to combine values with units
    * Comparison `>` is overridden to convert to other units
    """
    units: pint.Unit
    quantity: Optional[pint.Quantity]
    input_type: Optional[type]

    def __init__(self, units: str):
        """ Constructor: only get the unit name """
        self.units = pint.Unit(units)
        self.quantity = None
        self.input_type = None

    __slots__ = 'units', 'quantity', 'input_type'

    def __rmul__(self, value: float):
        """ Operator `*`: combine a value with a unit

        Example:
            1 * unit('min')
        """
        self.quantity = pint.Quantity(value, self.units)
        self.input_type = type(value)
        return self

    def __rshift__(self, convert_into: unit):
        """ Operator `>>`: convert to another quantity

        Example:
            1 * unit('min') >> unit('s')
        """
        assert self.quantity is not None
        assert self.input_type is not None

        converted_quantity = self.quantity.to(convert_into.units)
        return self.input_type(converted_quantity.magnitude)  # use the same type
