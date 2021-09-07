from __future__ import annotations

from collections import abc
from typing import ClassVar, TypeVar, Optional, Any, Union
from functools import cache
from inspect import unwrap, isfunction


T = TypeVar('T')


class decomarker_meta(type):
    """ Metaclass that supports simple isinstance() checks for func decorators """

    def __instancecheck__(self: decomarker, instance: Any):  # type: ignore[misc]
        return isfunction(instance) and self._has_marker(instance)


class decomarker(metaclass=decomarker_meta):
    """ A transparent decorator that adds metainformation to a function.

    Features:
    * Add information to a callable
    * instanceof() check lets you check whether a function has been decorated or not
    * Completely transparent: a decorator that does not wrap
    * When used on class methods, allows you to collect all marked methods from that class

    Use it to implement custom behaviors on top of other methods.

    Example:

        class known_errors(decomarker):
            known_errors: dict

            def __init__(self, known_errors: dict):
                super().__init__()
                self.known_errors = known_errors

        @known_errors({
            Exception: 'just happens from time to time',
        })
        def func():
            raise Exception('Oops')

        func_errors = known_errors.get_from(func)

    You can even decorate classes:

        @known_errors({ ... })
        class UserVew:
            ...

    But in this case, you have to consistently decide whether you decorate the class itself, or its constructor.
    """

    # Name of the custom attribute installed on decorated methods.
    # This marker is what makes them stand out.
    # You don't have to set it; it's automatically named after the class
    MARKER_ATTR: ClassVar[str]

    # Decorated func
    func: Optional[abc.Callable] = None
    func_name: Optional[str] = None

    def __init__(self):  # override me to receive arguments
        pass

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # Initialize the marker if not already:
        if getattr(cls, 'MARKER_ATTR', None) is None:
            cls.MARKER_ATTR = '::' + cls.__name__

    def __call__(self, func):
        return self.decorator(func)

    def decorator(self, func: Union[abc.Callable, type]):
        # Make sure this decorator is callable only once
        assert self.func is None

        # Function decorated multiple times? Merge.
        prev_marker = self.get_from(func)
        if prev_marker is not None:
            self._merge(prev_marker)

        # Mark the func. Use unwrap() to make sure we get to the meat.
        setattr(unwrap(func), self.MARKER_ATTR, self)

        # Remember & Return
        self.func = func
        self.func_name = func.__name__
        return func

    def _merge(self: T, another: T):
        cls_name = self.__class__.__name__
        raise NotImplementedError(f'@{cls_name} does not support re-decoration')

    def __repr__(self):
        return f'@{self.__class__.__name__}({self.__dict__!r})'

    @classmethod
    def _has_marker(cls, func: abc.Callable) -> bool:
        """ Is the given function decorated with this decorator """
        return hasattr(unwrap(func), cls.MARKER_ATTR)

    # region Public API

    @classmethod
    def is_decorated(cls, func: abc.Callable) -> bool:
        """ Check whether the given func is decorated with @cls()

        Works with re-decorated methods, but only if update_wrapper() was properly used
        """
        return isinstance(func, cls)

    @classmethod
    def get_from(cls: type[T], func: abc.Callable) -> Optional[T]:
        """ Get the @cls decorator object of the wrapped func """
        return getattr(unwrap(func), cls.MARKER_ATTR, None)  # type: ignore[attr-defined]

    @classmethod
    @cache
    def all_decorated_from(cls: type[T], class_: type, *, inherited: bool = False) -> abc.Sequence[T]:
        """ Get all decorated methods from a class.

        This method can be used when decorated methods provide some sort of group behavior.

        Args:
            class_: the class to collect decorated methods from
            inherited: whether to include methods decorated on parent classes
        """
        assert isinstance(unwrap(class_), type)

        members: abc.Iterable
        if inherited:
            members = (getattr(class_, attr) for attr in dir(class_))
        else:
            members = class_.__dict__.values()

        return tuple(cls.get_from(member)  # type: ignore[attr-defined]
                     for member in members
                     if isinstance(member, cls) and type(member) != cls)

    # endregion
