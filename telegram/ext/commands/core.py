from .context import Context


class Command:
    def __init__(self, bot, func, **kwargs):
        self.callback = func
        self.module = func.__module__
        self.bot = bot
        self.name = kwargs.get("name") or func.__name__
        self.description = kwargs.get("description")
        self.aliases = kwargs.get("aliases") or []
        self.examples = kwargs.get("examples") or []
        self.hidden = kwargs.get("hidden") or False
        self.parent = kwargs.get("parent")

    def __call__(self, update, context):
        ctx = Context(self, update, context)
        return self.callback(ctx)


def command(*args, **kwargs):
    def decorator(func):
        if isinstance(func, Command):
            raise TypeError("Callback is already a command")

        command = Command(bot=None, func=func, *args, **kwargs)
        # Bot will be set later (when the command is added to a bot)
        return command

    return decorator
