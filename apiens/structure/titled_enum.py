from enum import Enum

from typing import Any, Optional, TypeVar


class TitledEnum(Enum):
    """ An Enum with both a value and a title """
    def __new__(cls, value: Any, title: str):
        v = object.__new__(cls)
        v._value_ = value
        v.title = title
        return v


def titled(title: str, *, description: str = ''):
    """ Give enumeration a title and a description

    Note that this can be used independently of `TitledEnum`

    Example:
        @titled(_('Message direction'))
        class Direction(TitledEnum):
            IN = -1, _('Incoming')
            OUT = +1, _('Outgoing')
    """
    def EnumClassWrapper(Enum: type[_EnumSubclass]) -> type[_EnumSubclass]:
        Enum.__title__ = title  # type: ignore[attr-defined]
        Enum.__description__ = description  # type: ignore[attr-defined]
        return Enum
    return EnumClassWrapper


def get_title(Enum: type[TitledEnum]) -> str:
    """ Get the title of a titled Enum """
    return getattr(Enum, '__title__', '(not set)')


def get_description(Enum: type[TitledEnum]) -> str:
    """ Get the description of a titled Enum """
    return getattr(Enum, '__description__', '')


def try_get_value_title_from(Enum: type[TitledEnum], value: Any) -> Optional[Any]:
    """ Try to get a translation from the enum. Do not fail.

    This function is especially useful for nullable values.
    """
    try:
        return Enum(value).title  # type: ignore[call-arg,attr-defined]
    except ValueError:
        return value

_EnumSubclass = TypeVar("_EnumSubclass", bound=Enum)
