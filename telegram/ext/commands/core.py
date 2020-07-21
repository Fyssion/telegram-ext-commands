import inspect
import typing

from .context import Context
from .errors import (
    BadArgument,
    BadUnionArgument,
    BotException,
    ArgumentParsingError,
    ConversionError,
    CommandError,
    MissingRequiredArgument,
)
from . import converter as converters


def _convert_to_bool(argument):
    lowered = argument.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    elif lowered in ("no", "n", "false", "f", "0", "disable", "off"):
        return False
    else:
        raise BadArgument(lowered + " is not a recognised boolean option")


class Command:
    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        self.__original_kwargs__ = kwargs.copy()
        return self

    def __init__(self, bot, func, **kwargs):
        self.set_callback(func)
        self.bot = bot
        self.cog = None
        self.name = kwargs.get("name") or func.__name__
        self.description = kwargs.get("description")
        self.aliases = kwargs.get("aliases") or []
        self.usage = kwargs.get("usage")
        self.examples = kwargs.get("examples") or []
        self.hidden = kwargs.get("hidden") or False
        self.parent = kwargs.get("parent")
        self.rest_is_raw = kwargs.get("rest_is_raw", False)

    def set_callback(self, function):
        self.callback = function
        self.module = function.__module__

        signature = inspect.signature(function)
        self.params = signature.parameters.copy()

        # PEP-563 allows postponing evaluation of annotations with a __future__
        # import. When postponed, Parameter.annotation will be a string and must
        # be replaced with the real value for the converters to work later on
        for key, value in self.params.items():
            if isinstance(value.annotation, str):
                self.params[key] = value = value.replace(
                    annotation=eval(value.annotation, function.__globals__)
                )

            # fail early for when someone passes an unparameterized Greedy type
            if value.annotation is converters.Greedy:
                raise TypeError(
                    "Unparameterized Greedy[...] is disallowed in signature."
                )

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

    def _actual_conversion(self, ctx, converter, argument, param):
        if converter is bool:
            return _convert_to_bool(argument)

        try:
            module = converter.__module__
        except AttributeError:
            pass
        else:
            if module is not None and (
                module.startswith("discord.") and not module.endswith("converter")
            ):
                converter = getattr(
                    converters, converter.__name__ + "Converter", converter
                )

        try:
            if inspect.isclass(converter):
                if issubclass(converter, converters.Converter):
                    instance = converter()
                    ret = instance.convert(ctx, argument)
                    return ret
                else:
                    method = getattr(converter, "convert", None)
                    if method is not None and inspect.ismethod(method):
                        ret = method(ctx, argument)
                        return ret
            elif isinstance(converter, converters.Converter):
                ret = converter.convert(ctx, argument)
                return ret
        except CommandError:
            raise
        except Exception as exc:
            raise ConversionError(converter, exc) from exc

        try:
            return converter(argument)
        except CommandError:
            raise
        except Exception as exc:
            try:
                name = converter.__name__
            except AttributeError:
                name = converter.__class__.__name__

            raise BadArgument(
                'Converting to "{}" failed for parameter "{}".'.format(name, param.name)
            ) from exc

    def do_conversion(self, ctx, converter, argument, param):
        try:
            origin = converter.__origin__
        except AttributeError:
            pass
        else:
            if origin is typing.Union:
                errors = []
                _NoneType = type(None)
                for conv in converter.__args__:
                    # if we got to this part in the code, then the previous conversions have failed
                    # so we should just undo the view, return the default, and allow parsing to continue
                    # with the other parameters
                    if conv is _NoneType and param.kind != param.VAR_POSITIONAL:
                        ctx.view.undo()
                        return None if param.default is param.empty else param.default

                    try:
                        value = self._actual_conversion(ctx, conv, argument, param)
                    except CommandError as exc:
                        errors.append(exc)
                    else:
                        return value

                # if we're  here, then we failed all the converters
                raise BadUnionArgument(param, converter.__args__, errors)

        return self._actual_conversion(ctx, converter, argument, param)

    def _get_converter(self, param):
        converter = param.annotation
        if converter is param.empty:
            if param.default is not param.empty:
                converter = str if param.default is None else type(param.default)
            else:
                converter = str
        return converter

    def transform(self, ctx, param):
        required = param.default is param.empty
        converter = self._get_converter(param)
        consume_rest_is_special = (
            param.kind == param.KEYWORD_ONLY and not self.rest_is_raw
        )
        view = ctx.view
        view.skip_ws()

        # The greedy converter is simple -- it keeps going until it fails in which case,
        # it undos the view ready for the next parameter to use instead
        if type(converter) is converters._Greedy:
            if param.kind == param.POSITIONAL_OR_KEYWORD:
                return self._transform_greedy_pos(
                    ctx, param, required, converter.converter
                )
            elif param.kind == param.VAR_POSITIONAL:
                return self._transform_greedy_var_pos(ctx, param, converter.converter)
            else:
                # if we're here, then it's a KEYWORD_ONLY param type
                # since this is mostly useless, we'll helpfully transform Greedy[X]
                # into just X and do the parsing that way.
                converter = converter.converter

        if view.eof:
            if param.kind == param.VAR_POSITIONAL:
                raise RuntimeError()  # break the loop
            if required:
                if self._is_typing_optional(param.annotation):
                    return None
                raise MissingRequiredArgument(param)
            return param.default

        previous = view.index
        if consume_rest_is_special:
            argument = view.read_rest().strip()
        else:
            argument = view.get_quoted_word()
        view.previous = previous

        return self.do_conversion(ctx, converter, argument, param)

    def _transform_greedy_pos(self, ctx, param, required, converter):
        view = ctx.view
        result = []
        while not view.eof:
            # for use with a manual undo
            previous = view.index

            view.skip_ws()
            try:
                argument = view.get_quoted_word()
                value = self.do_conversion(ctx, converter, argument, param)
            except (CommandError, ArgumentParsingError):
                view.index = previous
                break
            else:
                result.append(value)

        if not result and not required:
            return param.default
        return result

    def _transform_greedy_var_pos(self, ctx, param, converter):
        view = ctx.view
        previous = view.index
        try:
            argument = view.get_quoted_word()
            value = self.do_conversion(ctx, converter, argument, param)
        except (CommandError, ArgumentParsingError):
            view.index = previous
            raise RuntimeError() from None  # break loop
        else:
            return value

    def _parse_arguments(self, ctx):
        ctx.args = [ctx] if self.cog is None else [self.cog, ctx]
        ctx.kwargs = {}
        args = ctx.args
        kwargs = ctx.kwargs

        view = ctx.view
        iterator = iter(self.params.items())

        if self.cog is not None:
            # we have 'self' as the first parameter so just advance
            # the iterator and resume parsing
            try:
                next(iterator)
            except StopIteration:
                fmt = 'Callback for {0.name} command is missing "self" parameter.'
                raise BotException(fmt.format(self))

        # next we have the 'ctx' as the next parameter
        try:
            next(iterator)
        except StopIteration:
            fmt = 'Callback for {0.name} command is missing "ctx" parameter.'
            raise BotException(fmt.format(self))

        for name, param in iterator:
            if param.kind == param.POSITIONAL_OR_KEYWORD:
                transformed = self.transform(ctx, param)
                args.append(transformed)
            elif param.kind == param.KEYWORD_ONLY:
                # kwarg only param denotes "consume rest" semantics
                if self.rest_is_raw:
                    converter = self._get_converter(param)
                    argument = view.read_rest()
                    kwargs[name] = self.do_conversion(ctx, converter, argument, param)
                else:
                    kwargs[name] = self.transform(ctx, param)
                break
            elif param.kind == param.VAR_POSITIONAL:
                while not view.eof:
                    try:
                        transformed = self.transform(ctx, param)
                        args.append(transformed)
                    except RuntimeError:
                        break

    def prepare(self, ctx):
        ctx.command = self

        self._parse_arguments(ctx)

    def __call__(self, update, context):
        ctx = self.bot.get_context(self, update, context)

        self.prepare(ctx)

        return self.callback(*ctx.args, **ctx.kwargs)


def command(*args, **kwargs):
    def decorator(func):
        if isinstance(func, Command):
            raise TypeError("Callback is already a command")

        command = Command(None, func, *args, **kwargs)
        # Bot will be set later (when the command is added to a bot)
        return command

    return decorator
