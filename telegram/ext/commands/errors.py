import telegram


class CommandError(telegram.TelegramError):
    pass


class BotException(telegram.TelegramError):
    pass


class ConversionError(CommandError):
    def __init__(self, converter, original):
        self.converter = converter
        self.original = original


class UserInputError(CommandError):
    pass


class MissingRequiredArgument(UserInputError):
    def __init__(self, param):
        self.param = param
        super().__init__(
            "{0.name} is a required argument that is missing.".format(param)
        )


class ExtensionError(BotException):
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


class TooManyArguments(UserInputError):
    pass


class BadArgument(UserInputError):
    pass


class BadUnionArgument(UserInputError):
    def __init__(self, param, converters, errors):
        self.param = param
        self.converters = converters
        self.errors = errors

        def _get_name(x):
            try:
                return x.__name__
            except AttributeError:
                return x.__class__.__name__

        to_string = [_get_name(x) for x in converters]
        if len(to_string) > 2:
            fmt = "{}, or {}".format(", ".join(to_string[:-1]), to_string[-1])
        else:
            fmt = " or ".join(to_string)

        super().__init__('Could not convert "{0.name}" into {1}.'.format(param, fmt))


class ArgumentParsingError(UserInputError):
    pass


class UnexpectedQuoteError(ArgumentParsingError):
    def __init__(self, quote):
        self.quote = quote
        super().__init__(
            "Unexpected quote mark, {0!r}, in non-quoted string".format(quote)
        )


class InvalidEndOfQuotedStringError(ArgumentParsingError):
    def __init__(self, char):
        self.char = char
        super().__init__(
            "Expected space after closing quotation but received {0!r}".format(char)
        )


class ExpectedClosingQuoteError(ArgumentParsingError):
    def __init__(self, close_quote):
        self.close_quote = close_quote
        super().__init__("Expected closing {}.".format(close_quote))
