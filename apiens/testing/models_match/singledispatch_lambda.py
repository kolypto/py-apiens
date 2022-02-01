from .model_info import ModelInfo


class singledispatch_lambda:
    """ singledispatch, where every function has a custom lambda that checks whether it's applicable """
    def __init__(self):
        self.dispatchers = []

    def __call__(self, value, *args, **kwargs) -> ModelInfo:
        for check, cb in self.dispatchers:
            if check(value):
                return cb(value, *args, **kwargs)
        else:
            return self.default_callback(value, *args, **kwargs)

    def decorator(self, cb: callable):
        self.set_default_callback(cb)
        return self

    def register(self, check: callable):
        def decorator(cb: callable):
            self.set_callback(cb, check)
            return self
        return decorator

    def set_default_callback(self, cb: callable):
        self.default_callback = cb

    def set_callback(self, cb: callable, check: callable):
        self.dispatchers.append((check, cb))
