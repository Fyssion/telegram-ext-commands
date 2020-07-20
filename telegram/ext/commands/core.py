from .context import Context


class Command:
    def __init__(self, func, **kwargs):
        self.callback = func
        self.desciption = kwargs.pop("description")

    def __call__(self, update, context):
        ctx = Context(self, update, context)
        return self.callback(ctx)