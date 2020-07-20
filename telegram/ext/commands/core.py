from .context import Context


class Command:
    def __init__(self, bot, func, **kwargs):
        self.callback = func
        self.bot = bot
        self.name = kwargs.get("name") or func.__name__
        self.description = kwargs.get("description")
        self.aliases = kwargs.get("aliases") or []
        self.examples = kwargs.get("examples") or []
        self.hidden = kwargs.get("hidden") or False

    def __call__(self, update, context):
        ctx = Context(self, update, context)
        return self.callback(ctx)
