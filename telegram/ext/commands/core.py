import inspect
import typing
import functools

from .context import Context
from .errors import (
    BadArgument,
    BadUnionArgument,
    BotException,
    ArgumentParsingError,
    ConversionError,
    CommandError,
    MissingRequiredArgument,
    CheckFailure,
    NotOwner,
    DisabledCommand,
)
from . import converter as converters
from .cog import Cog
from ._types import _BaseCommand


def _convert_to_bool(argument):
    lowered = argument.lower()
    if lowered in ("yes", "y", "true", "t", "1", "enable", "on"):
        return True
    elif lowered in ("no", "n", "false", "f", "0", "disable", "off"):
        return False
    else:
        raise BadArgument(lowered + " is not a recognised boolean option")


class Command(_BaseCommand):
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
        self.enabled = kwargs.get("enabled", True)
        self._before_invoke = None
        self._after_invoke = None

        help_doc = kwargs.get("help")
        if help_doc is not None:
            help_doc = inspect.cleandoc(help_doc)
        else:
            help_doc = inspect.getdoc(func)
            if isinstance(help_doc, bytes):
                help_doc = help_doc.decode("utf-8")

        self.help = help_doc

        self.brief = kwargs.get("brief")

        try:
            checks = func.__commands_checks__
            checks.reverse()
        except AttributeError:
            checks = kwargs.get("checks", [])
        finally:
            self.checks = checks

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

    def add_check(self, func):
        self.checks.append(func)

    def remove_check(self, func):
        try:
            self.checks.remove(func)
        except ValueError:
            pass

    def before_invoke(self, func):
        self._before_invoke = func
        return func

    def after_invoke(self, func):
        self._after_invoke = func
        return func

    @property
    def qualified_name(self):
        return self.name

    @property
    def clean_params(self):
        """Retrieves the parameter OrderedDict without the context or self parameters.

        Useful for inspecting signature.
        """
        result = self.params.copy()
        if self.cog is not None:
            # first parameter is self
            result.popitem(last=False)

        try:
            # first/second parameter is context
            result.popitem(last=False)
        except Exception:
            raise ValueError("Missing context parameter") from None

        return result

    @property
    def cog_name(self):
        """:class:`str`: The name of the cog this command belongs to. None otherwise."""
        return type(self.cog).__cog_name__ if self.cog is not None else None

    @property
    def short_doc(self):
        """:class:`str`: Gets the "short" documentation of a command.

        By default, this is the :attr:`brief` attribute.
        If that lookup leads to an empty string then the first line of the
        :attr:`help` attribute is used instead.
        """
        if self.brief is not None:
            return self.brief
        if self.help is not None:
            return self.help.split("\n", 1)[0]
        return ""

    @property
    def signature(self):
        """:class:`str`: Returns a POSIX-like signature useful for help command output."""
        if self.usage is not None:
            return self.usage

        params = self.clean_params
        if not params:
            return ""

        result = []
        for name, param in params.items():
            greedy = isinstance(param.annotation, converters._Greedy)

            if param.default is not param.empty:
                # We don't want None or '' to trigger the [name=value] case and instead it should
                # do [name] since [name=None] or [name=] are not exactly useful for the user.
                should_print = (
                    param.default
                    if isinstance(param.default, str)
                    else param.default is not None
                )
                if should_print:
                    result.append(
                        "[%s=%s]" % (name, param.default)
                        if not greedy
                        else "[%s=%s]..." % (name, param.default)
                    )
                    continue
                else:
                    result.append("[%s]" % name)

            elif param.kind == param.VAR_POSITIONAL:
                result.append("[%s...]" % name)
            elif greedy:
                result.append("[%s]..." % name)
            elif self._is_typing_optional(param.annotation):
                result.append("[%s]" % name)
            else:
                result.append("<%s>" % name)

        return " ".join(result)

    def _ensure_assignment_on_copy(self, other):
        other._before_invoke = self._before_invoke
        other._after_invoke = self._after_invoke
        if self.checks != other.checks:
            other.checks = self.checks.copy()

        try:
            other.on_error = self.on_error
        except AttributeError:
            pass
        return other

    def copy(self):
        ret = self.__class__(self.bot, self.callback, **self.__original_kwargs__)
        return self._ensure_assignment_on_copy(ret)

    def _update_copy(self, kwargs):
        if kwargs:
            kw = kwargs.copy()
            kw.update(self.__original_kwargs__)
            copy = self.__class__(self.bot, self.callback, **kw)
            return self._ensure_assignment_on_copy(copy)
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

    def can_run(self, ctx):
        if not self.enabled:
            raise DisabledCommand("{0.name} command is disabled".format(self))

        original = ctx.command
        ctx.command = self

        try:
            if not ctx.bot.can_run(ctx):
                raise CheckFailure(
                    "The global check functions for command {0.qualified_name} failed.".format(
                        self
                    )
                )

            cog = self.cog
            if cog is not None:
                local_check = Cog._get_overridden_method(cog.cog_check)
                if local_check is not None:
                    ret = local_check(ctx)
                    if not ret:
                        return False

            predicates = self.checks
            if not predicates:
                # since we have no checks, then we just return True.
                return True

            passed = True
            gen = (predicate(ctx) for predicate in predicates)

            for elem in gen:
                if not elem:
                    passed = False

            return passed
        finally:
            ctx.command = original

    def call_before_hooks(self, ctx):
        # now that we're done preparing we can call the pre-command hooks
        # first, call the command local hook:
        cog = self.cog
        if self._before_invoke is not None:
            try:
                instance = self._before_invoke.__self__
                # should be cog if @commands.before_invoke is used
            except AttributeError:
                # __self__ only exists for methods, not functions
                # however, if @command.before_invoke is used, it will be a function
                if self.cog:
                    self._before_invoke(cog, ctx)
                else:
                    self._before_invoke(ctx)
            else:
                self._before_invoke(instance, ctx)

        # call the cog local hook if applicable:
        if cog is not None:
            hook = Cog._get_overridden_method(cog.cog_before_invoke)
            if hook is not None:
                hook(ctx)

        # call the bot global hook if necessary
        hook = ctx.bot._before_invoke
        if hook is not None:
            hook(ctx)

    def call_after_hooks(self, ctx):
        cog = self.cog
        if self._after_invoke is not None:
            try:
                instance = self._after_invoke.__self__
            except AttributeError:
                if self.cog:
                    self._after_invoke(cog, ctx)
                else:
                    self._after_invoke(ctx)
            else:
                self._after_invoke(instance, ctx)

        # call the cog local hook if applicable:
        if cog is not None:
            hook = Cog._get_overridden_method(cog.cog_after_invoke)
            if hook is not None:
                hook(ctx)

        hook = ctx.bot._after_invoke
        if hook is not None:
            hook(ctx)

    def prepare(self, ctx):
        ctx.command = self

        self._parse_arguments(ctx)

        if not self.can_run(ctx):
            raise CheckFailure(
                "The check functions for command {0.qualified_name} failed.".format(
                    self
                )
            )

        self.call_before_hooks(ctx)

    def __call__(self, update, context):
        ctx = self.bot.get_context(self, update, context)

        self.prepare(ctx)

        ret = self.callback(*ctx.args, **ctx.kwargs)

        self.call_after_hooks(ctx)

        return ret


def command(*args, **kwargs):
    def decorator(func):
        if isinstance(func, Command):
            raise TypeError("Callback is already a command")

        command = Command(None, func, *args, **kwargs)
        # Bot will be set later (when the command is added to a bot)
        return command

    return decorator


# Checks


def check(predicate):
    def decorator(func):
        if isinstance(func, Command):
            func.checks.append(predicate)
        else:
            if not hasattr(func, "__commands_checks__"):
                func.__commands_checks__ = []

            func.__commands_checks__.append(predicate)

        return func

    decorator.predicate = predicate
    return decorator


def is_owner():
    def predicate(ctx):
        if not ctx.bot.is_owner(ctx.user):
            raise NotOwner("You do not own this bot.")
        return True

    return check(predicate)
