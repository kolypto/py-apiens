from inspect import unwrap, isfunction, isclass

from functools import lru_cache

from typing import ClassVar, Callable, TypeVar, Optional, Sequence, Any, Type, Union

Cls_T = TypeVar('Cls_T')


class decomarker_meta(type):
    """ Metaclass that supports simple isinstance() checks for func decorators """

    def __instancecheck__(self: 'decomarker', instance: Any):
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
    """

    # Name of the custom attribute installed on decorated methods.
    # This marker is what makes them stand out.
    # You don't have to set it; it's automatically named after the class
    MARKER_ATTR: ClassVar[str]

    # Decorated func
    func: Callable = None
    func_name: str = None

    def __init__(self):  # override me to receive arguments
        pass

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        # Initialize the marker
        cls.MARKER_ATTR = cls.__name__

    def __call__(self, func):
        return self.decorator(func)

    def decorator(self, func: Union[Callable, type]):
        # Make sure this decorator is callable only once
        assert self.func is None

        # Use class.__init__ if a class is given
        f = func_or_class(func)

        # Mark the func. Use unwrap() to make sure we get to the meat.
        setattr(unwrap(f), self.MARKER_ATTR, self)

        # Remember & Return
        self.func = f
        self.func_name = f.__name__
        return func

    def __repr__(self):
        return f'@{self.__class__.__name__}({self.__dict__!r})'

    @classmethod
    def _has_marker(cls, func: Callable) -> bool:
        """ Is the given function decorated with this decorator """
        return hasattr(unwrap(func_or_class(func)), cls.MARKER_ATTR)

    # region Public API

    @classmethod
    def is_decorated(cls, func: Callable) -> bool:
        """ Check whether the given func is decorated with @cls()

        Works with re-decorated methods, but only if update_wrapper() was properly used
        """
        return isinstance(func, cls)

    @classmethod
    def get_from(cls: Type[Cls_T], func: Callable) -> Optional[Cls_T]:
        """ Get the @cls decorator object of the wrapped func """
        return getattr(unwrap(func_or_class(func)), cls.MARKER_ATTR, None)

    @classmethod
    @lru_cache()
    def all_decorated_from(cls: Type[Cls_T], class_: type, *, inherited: bool = False) -> Sequence[Cls_T]:
        """ Get all decorated methods from a class.

        This method can be used when decorated methods provide some sort of group behavior.

        Args:
            class_: the class to collect decorated methods from
            inherited: whether to include methods decorated on parent classes
        """
        assert isinstance(class_, type)

        if inherited:
            members = [getattr(class_, attr) for attr in dir(class_)]
        else:
            members = class_.__dict__.values()

        return tuple(cls.get_from(member)
                     for member in members
                     if isinstance(member, cls))

    # endregion


def func_or_class(func: Union[Callable, type]) -> Callable:
    """ Use class' __init__() if the whole class is given """
    # If we're given a class, take its __init__() instead
    if isclass(func):
        return func.__init__
    # Otherwise, use as is
    else:
        return func
