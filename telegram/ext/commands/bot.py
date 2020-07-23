from telegram.ext import Updater, CommandHandler

import sys
import importlib
import inspect
import traceback

from . import errors
from .core import command
from .cog import Cog
from .context import Context
from .view import StringView
from .help import HelpCommand, DefaultHelpCommand
from .errors import CommandError


class _DefaultRepr:
    def __repr__(self):
        return "<default-help-command>"


_default = _DefaultRepr()


class Bot:
    def __init__(
        self, token, owner_ids=None, *, help_command=_default, description=None
    ):
        # name: command
        self.commands = {}
        # command_name: handler
        self._handlers = {}
        # extension_name: extension
        self._extensions = {}
        # cog_name: cog
        self._cogs = {}
        self._checks = []
        self._check_once = []
        self._before_invoke = None
        self._after_invoke = None
        self.owner_ids = owner_ids or []
        self._help_command = None

        self.updater = Updater(token=token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.job_queue = self.updater.job_queue

        self.description = inspect.cleandoc(description) if description else ""

        if help_command is _default:
            self.help_command = DefaultHelpCommand()
        else:
            self.help_command = help_command

        if not self.owner_ids:
            print(
                "WARNING: owner_ids is not set. 'bot.is_owner()' will not work property."
            )

        self.dispatcher.add_error_handler(self.error_handler)

    @property
    def help_command(self):
        return self._help_command

    @help_command.setter
    def help_command(self, value):
        if value is not None:
            if not isinstance(value, HelpCommand):
                raise TypeError("help_command must be a subclass of HelpCommand")
            if self._help_command is not None:
                self._help_command._remove_from_bot(self)
            self._help_command = value
            value._add_to_bot(self)
        elif self._help_command is not None:
            self._help_command._remove_from_bot(self)
            self._help_command = None
        else:
            self._help_command = None

    def get_context(self, command, update, context, *, cls=Context):
        view = StringView(" ".join(context.args))
        ctx = cls(command, update, context, view=view)
        return ctx

    def get_commands(self):
        return [c for c in self.commands.values() if not c.parent and not c.cog]

    def add_command(self, command):
        if command.name in self.commands.keys():
            raise ValueError("There is already a command with that name")

        if not command.bot:
            command.bot = self

        self.commands[command.name] = command

        self._handlers[command.name] = CommandHandler(command.name, command)
        self.dispatcher.add_handler(self._handlers[command.name])

        if command.aliases:
            for alias in command.aliases:
                self._handlers[alias] = CommandHandler(alias, command)
                self.dispatcher.add_handler(self._handlers[alias])

    def remove_command(self, command_name):
        if command_name not in self.commands.keys():
            raise ValueError("There is no command with that name")

        command = self.commands.pop(command_name)
        self._handlers.pop(command_name)
        self.dispatcher.remove_handler(command_name)

        if command.aliases:
            for alias in command.aliases:
                self._handlers.pop(alias)
                self.dispatcher.remove_handler(alias)

    def command(self, *args, **kwargs):
        def decorater(func):
            kwargs.setdefault("parent", None)
            result = command(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorater

    def check(self, func):
        self.add_check(func)
        return func

    def add_check(self, func, *, call_once=False):
        if call_once:
            self._check_once.append(func)
        else:
            self._checks.append(func)

    def remove_check(self, func, *, call_once=False):
        l = self._check_once if call_once else self._checks

        try:
            l.remove(func)
        except ValueError:
            pass

    def before_invoke(self, func):
        self._before_invoke = func
        return func

    def after_invoke(self, func):
        self._after_invoke = func
        return func

    def check_once(self, func):
        self.add_check(func, call_once=True)
        return func

    def can_run(self, ctx, *, call_once=False):
        data = self._check_once if call_once else self._checks

        if len(data) == 0:
            return True

        passed = True
        gen = (f(ctx) for f in data)

        for elem in gen:
            if not elem:
                passed = False

        return passed

    def is_owner(self, user):
        return user.id in self.owner_ids

    @property
    def cogs(self):
        return {c.qualified_name: c for c in self._cogs.values()}

    def add_cog(self, cog):
        if not isinstance(cog, Cog):
            raise TypeError("cogs must subclass Cog")

        cog = cog._inject(self)
        self._cogs[cog.__cog_name__] = cog

    def get_cog(self, name):
        return self._cogs.get(name)

    def remove_cog(self, name):
        cog = self._cogs.pop(name, None)
        if cog is None:
            return

        cog._eject(self)

    def _is_submodule(self, parent, child):
        return parent == child or child.startswith(parent + ".")

    def _remove_module_references(self, name):
        # find all references to the module
        # remove the cogs registered from the module
        for cogname, cog in self._cogs.copy().items():
            if self._is_submodule(name, cog.__module__):
                self.remove_cog(cogname)

        # remove commands
        for cmd in self.commands.copy().values():
            if cmd.module is not None and self._is_submodule(name, cmd.module):
                self.remove_command(cmd.name)

    def _call_module_finalizers(self, lib, key):
        try:
            func = getattr(lib, "teardown")
        except AttributeError:
            pass
        else:
            try:
                func(self)
            except Exception:
                pass
        finally:
            self._extensions.pop(key, None)
            sys.modules.pop(key, None)
            name = lib.__name__
            for module in list(sys.modules.keys()):
                if self._is_submodule(name, module):
                    del sys.modules[module]

    def _load_from_module_spec(self, spec, key):
        # precondition: key not in self._extensions
        lib = importlib.util.module_from_spec(spec)
        sys.modules[key] = lib
        try:
            spec.loader.exec_module(lib)
        except Exception as e:
            del sys.modules[key]
            raise errors.ExtensionFailed(key, e) from e

        try:
            setup = getattr(lib, "setup")
        except AttributeError:
            del sys.modules[key]
            raise errors.NoEntryPointError(key)

        try:
            setup(self)
        except Exception as e:
            del sys.modules[key]
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, key)
            raise errors.ExtensionFailed(key, e) from e
        else:
            self._extensions[key] = lib

    def load_extension(self, name):
        if name in self._extensions:
            raise errors.ExtensionAlreadyLoaded(name)

        spec = importlib.util.find_spec(name)
        if spec is None:
            raise errors.ExtensionNotFound(name)

        self._load_from_module_spec(spec, name)

    def unload_extension(self, name):
        lib = self._extensions.get(name)
        if lib is None:
            raise errors.ExtensionNotLoaded(name)

        self._remove_module_references(lib.__name__)
        self._call_module_finalizers(lib, name)

    def reload_extension(self, name):
        lib = self._extensions.get(name)
        if lib is None:
            raise errors.ExtensionNotLoaded(name)

        # get the previous module states from sys modules
        modules = {
            name: module
            for name, module in sys.modules.items()
            if self._is_submodule(lib.__name__, name)
        }

        try:
            # Unload and then load the module...
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, name)
            self.load_extension(name)

        except Exception:
            # if the load failed, the remnants should have been
            # cleaned from the load_extension function call
            # so let's load it from our old compiled library.
            lib.setup(self)
            self.__extensions[name] = lib

            # revert sys.modules back to normal and raise back to caller
            sys.modules.update(modules)
            raise

    def on_command_error(self, ctx, error):
        """Global error handler that is called when
        an error is raised when invoking a command.

        The error is only printed if there is no error handler for
        the command or cog.
        """

        if hasattr(ctx.command, "on_error"):
            return

        cog = ctx.cog
        if cog:
            if Cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)
        traceback.print_exception(
            type(error), error, error.__traceback__, file=sys.stderr
        )

    def error_handler(self, update, error):
        """Error handler that is added via
        :meth:`telegram.ext.Dispatcher.add_error_handler`

        This error handler ignores errors that derive from
        CommandError, as those errors are handled by
        :meth:`on_command_error`
        """

        if isinstance(error, CommandError):
            return

        raise error

    def stop(self):
        self.updater.stop()

    def run(self, *, idle=True):
        self.updater.start_polling()

        if idle:
            self.updater.idle()

    def idle(self):
        self.updater.idle()

    def close(self):
        self.updater.stop()
        sys.exit()
