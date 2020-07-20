class CommandError(Exception):
    pass


class ExtensionFailed(CommandError):
    pass


class NoEntryPointError(ExtensionFailed):
    pass


class ExtensionAlreadyLoaded(ExtensionFailed):
    pass
