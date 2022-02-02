from collections import abc
from .model_info import ModelInfo


class singledispatch_lambda:
    """ singledispatch, where every function has a custom lambda that checks whether it's applicable

    Here, you register functions together with a `check` function that decides whether it's applicable.
    It enables you to work with complicated types, like types themselves.
    """
    def __init__(self):
        self.dispatchers = []

    def __call__(self, value, *args, **kwargs) -> ModelInfo:
        for check, cb in self.dispatchers:
            if check(value):
                return cb(value, *args, **kwargs)
        else:
            return self.default_callback(value, *args, **kwargs)

    def decorator(self, cb: abc.Callable):
        self.set_default_callback(cb)
        return self

    def register(self, check: abc.Callable):
        """ Register an implementation that kicks in only when `check` gives `True` """
        def decorator(cb: abc.Callable):
            self.set_callback(cb, check)
            return self
        return decorator

    def set_default_callback(self, cb: abc.Callable):
        self.default_callback = cb

    def set_callback(self, cb: abc.Callable, check: abc.Callable):
        self.dispatchers.append((check, cb))
