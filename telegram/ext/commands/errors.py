class CommandError(Exception):
    pass


class ExtensionError(CommandError):
    def __init__(self, message=None, *args, name):
        self.name = name
        message = message or "Extension {!r} had an error.".format(name)
        # clean-up @everyone and @here mentions
        m = message.replace("@everyone", "@\u200beveryone").replace(
            "@here", "@\u200bhere"
        )
        super().__init__(m, *args)


class ExtensionAlreadyLoaded(ExtensionError):
    def __init__(self, name):
        super().__init__("Extension {!r} is already loaded.".format(name), name=name)


class ExtensionNotLoaded(ExtensionError):
    def __init__(self, name):
        super().__init__("Extension {!r} has not been loaded.".format(name), name=name)


class NoEntryPointError(ExtensionError):
    def __init__(self, name):
        super().__init__(
            "Extension {!r} has no 'setup' function.".format(name), name=name
        )


class ExtensionFailed(ExtensionError):
    def __init__(self, name, original):
        self.original = original
        fmt = "Extension {0!r} raised an error: {1.__class__.__name__}: {1}"
        super().__init__(fmt.format(name, original), name=name)


class ExtensionNotFound(ExtensionError):
    def __init__(self, name, original=None):
        self.original = None
        fmt = "Extension {0!r} could not be loaded."
        super().__init__(fmt.format(name), name=name)
