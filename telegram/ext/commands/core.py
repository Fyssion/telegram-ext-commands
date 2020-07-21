from .context import Context


class Command:
    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        self.__original_kwargs__ = kwargs.copy()
        return self

    def __init__(self, bot, func, **kwargs):
        self.callback = func
        self.module = func.__module__
        self.bot = bot
        self.cog = None
        self.name = kwargs.get("name") or func.__name__
        self.description = kwargs.get("description")
        self.aliases = kwargs.get("aliases") or []
        self.usage = kwargs.get("usage")
        self.examples = kwargs.get("examples") or []
        self.hidden = kwargs.get("hidden") or False
        self.parent = kwargs.get("parent")

    @property
    def qualified_name(self):
        return self.name

    def copy(self):
        ret = self.__class__(self.bot, self.callback, **self.__original_kwargs__)
        return ret

    def _update_copy(self, kwargs):
        if kwargs:
            kw = kwargs.copy()
            kw.update(self.__original_kwargs__)
            copy = self.__class__(self.bot, self.callback, **kw)
            return copy
        else:
            return self.copy()

    def __call__(self, update, context):
        ctx = Context(self, update, context)

        if self.cog is not None:
            return self.callback(self.cog, ctx)

        return self.callback(ctx)


def command(*args, **kwargs):
    def decorator(func):
        if isinstance(func, Command):
            raise TypeError("Callback is already a command")

        command = Command(None, func, *args, **kwargs)
        # Bot will be set later (when the command is added to a bot)
        return command

    return decorator
