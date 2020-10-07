from enum import Enum

from typing import Type, Any


class TitledEnum(Enum):
    """ An Enum with both a value and a title """

    def __new__(cls, value: Any, title: str):
        v = object.__new__(cls)
        v._value_ = value
        v.title = title
        return v


def titled(title, *, description: str = ''):
    """ Give enumeration a title and a description

    Note that this can be used independently of `TitledEnum`

    Example:
        @titled(_('Message direction'))
        class Direction(TitledEnum):
            IN = -1, _('Incoming')
            OUT = +1, _('Outgoing')
    """
    def EnumClassWrapper(Enum: Type[Enum]):
        Enum.__title__ = title
        Enum.__description__ = description
        return Enum
    return EnumClassWrapper


def get_title(Enum: Type[Enum]) -> str:
    """ Get the title of a titled Enum """
    return getattr(Enum, '__title__', '(not set)')


def get_description(Enum: Type[Enum]) -> str:
    """ Get the description of a titled Enum """
    return getattr(Enum, '__description__', '')
