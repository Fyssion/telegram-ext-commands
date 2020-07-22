import functools
import itertools
import copy
import unicodedata
import re

from .core import Command
from .errors import CommandError


# help -> shows info of bot on top/bottom and lists subcommands
# help command -> shows detailed info of command

# <description>

# <command signature with aliases>

# <long doc>

# Cog:
#   /<command> <shortdoc>
#   /<command> <shortdoc>
# Other Cog:
#   /<command> <shortdoc>
# No Category:
#   /<command> <shortdoc>

# Type /help <command> for more info on a command.
# You can also type /help <category> for more info on a category.


def _not_overriden(f):
    f.__help_command_not_overriden__ = True
    return f


class _HelpCommandImpl(Command):
    def __init__(self, inject, *args, **kwargs):
        super().__init__(None, inject.command_callback, *args, **kwargs)
        self._original = inject
        self._injected = inject

    def prepare(self, ctx):
        self._injected = injected = self._original.copy()
        injected.context = ctx
        self.callback = injected.command_callback

        on_error = injected.on_help_command_error
        if not hasattr(on_error, "__help_command_not_overriden__"):
            if self.cog is not None:
                self.on_error = self._on_error_cog_implementation
            else:
                self.on_error = on_error

        super().prepare(ctx)

    def _parse_arguments(self, ctx):
        # Make the parser think we don't have a cog so it doesn't
        # inject the parameter into `ctx.args`.
        original_cog = self.cog
        self.cog = None
        try:
            super()._parse_arguments(ctx)
        finally:
            self.cog = original_cog

    def _on_error_cog_implementation(self, dummy, ctx, error):
        self._injected.on_help_command_error(ctx, error)

    @property
    def clean_params(self):
        result = self.params.copy()
        try:
            result.popitem(last=False)
        except Exception:
            raise ValueError("Missing context parameter") from None
        else:
            return result

    def _inject_into_cog(self, cog):
        # Warning: hacky

        # Make the cog think that get_commands returns this command
        # as well if we inject it without modifying __cog_commands__
        # since that's used for the injection and ejection of cogs.
        def wrapped_get_commands(*, _original=cog.get_commands):
            ret = _original()
            ret.append(self)
            return ret

        # Ditto here
        def wrapped_walk_commands(*, _original=cog.walk_commands):
            yield from _original()
            yield self

        functools.update_wrapper(wrapped_get_commands, cog.get_commands)
        functools.update_wrapper(wrapped_walk_commands, cog.walk_commands)
        cog.get_commands = wrapped_get_commands
        cog.walk_commands = wrapped_walk_commands
        self.cog = cog

    def _eject_cog(self):
        if self.cog is None:
            return

        # revert back into their original methods
        cog = self.cog
        cog.get_commands = cog.get_commands.__wrapped__
        cog.walk_commands = cog.walk_commands.__wrapped__
        self.cog = None


class HelpCommand:
    def __new__(cls, *args, **kwargs):
        # To prevent race conditions of a single instance while also allowing
        # for settings to be passed the original arguments passed must be assigned
        # to allow for easier copies (which will be made when the help command is actually called)
        # see issue 2123
        self = super().__new__(cls)

        # Shallow copies cannot be used in this case since it is not unusual to pass
        # instances that need state, e.g. Paginator or what have you into the function
        # The keys can be safely copied as-is since they're 99.99% certain of being
        # string keys
        deepcopy = copy.deepcopy
        self.__original_kwargs__ = {k: deepcopy(v) for k, v in kwargs.items()}
        self.__original_args__ = deepcopy(args)
        return self

    def __init__(self, **options):
        self.show_hidden = options.pop("show_hidden", False)
        self.verify_checks = options.pop("verify_checks", True)
        self.command_attrs = attrs = options.pop("command_attrs", {})
        attrs.setdefault("name", "help")
        self.command_name = attrs["name"]
        attrs.setdefault("aliases", ["start"])
        attrs.setdefault("help", "Shows this message")
        self.context = None
        self._command_impl = None

    def copy(self):
        obj = self.__class__(*self.__original_args__, **self.__original_kwargs__)
        obj._command_impl = self._command_impl
        return obj

    def _add_to_bot(self, bot):
        command = _HelpCommandImpl(self, **self.command_attrs)
        bot.add_command(command)
        self._command_impl = command

    def _remove_from_bot(self, bot):
        bot.remove_command(self._command_impl.name)
        self._command_impl._eject_cog()
        self._command_impl = None

    def get_bot_mapping(self):
        """Retrieves the bot mapping passed to :meth:`send_bot_help`."""
        bot = self.context.bot
        mapping = {cog: cog.get_commands() for cog in bot.cogs.values()}
        mapping[None] = [c for c in bot.commands.values() if c.cog is None]
        return mapping

    def remove_mentions(self, string):
        string = list(string)

        for i, letter in enumerate(string):
            if letter == "@":
                string[i] = "@\N{ZERO WIDTH JOINER}"

        return "".join(string)

    def get_command_signature(self, command):
        """Retrieves the signature portion of the help page.

        Parameters
        ------------
        command: :class:`Command`
            The command to get the signature of.

        Returns
        --------
        :class:`str`
            The signature for the command.
        """

        alias = command.name

        return "/%s %s" % (alias, command.signature)

    @property
    def cog(self):
        """A property for retrieving or setting the cog for the help command.

        When a cog is set for the help command, it is as-if the help command
        belongs to that cog. All cog special methods will apply to the help
        command and it will be automatically unset on unload.

        To unbind the cog from the help command, you can set it to ``None``.

        Returns
        --------
        Optional[:class:`Cog`]
            The cog that is currently set for the help command.
        """
        return self._command_impl.cog

    @cog.setter
    def cog(self, cog):
        # Remove whatever cog is currently valid, if any
        self._command_impl._eject_cog()

        # If a new cog is set then inject it.
        if cog is not None:
            self._command_impl._inject_into_cog(cog)

    def command_not_found(self, string):
        """A method called when a command is not found in the help command.
        This is useful to override for i18n.

        Defaults to ``No command called {0} found.``

        Parameters
        ------------
        string: :class:`str`
            The string that contains the invalid command. Note that this has
            had mentions removed to prevent abuse.

        Returns
        ---------
        :class:`str`
            The string to use when a command has not been found.
        """
        return 'No command called "{}" found.'.format(string)

    def filter_commands(self, commands, *, sort=False, key=None):
        """Returns a filtered list of commands and optionally sorts them.

        This takes into account the :attr:`verify_checks` and :attr:`show_hidden`
        attributes.

        Parameters
        ------------
        commands: Iterable[:class:`Command`]
            An iterable of commands that are getting filtered.
        sort: :class:`bool`
            Whether to sort the result.
        key: Optional[Callable[:class:`Command`, Any]]
            An optional key function to pass to :func:`py:sorted` that
            takes a :class:`Command` as its sole parameter. If ``sort`` is
            passed as ``True`` then this will default as the command name.

        Returns
        ---------
        List[:class:`Command`]
            A list of commands that passed the filter.
        """

        if sort and key is None:
            key = lambda c: c.name

        iterator = (
            commands if self.show_hidden else filter(lambda c: not c.hidden, commands)
        )

        if not self.verify_checks:
            # if we do not need to verify the checks then we can just
            # run it straight through normally without using await.
            return sorted(iterator, key=key) if sort else list(iterator)

        # if we're here then we need to check every command if it can run
        def predicate(cmd):
            try:
                return cmd.can_run(self.context)
            except CommandError:
                return False

        ret = []
        for cmd in iterator:
            valid = predicate(cmd)
            if valid:
                ret.append(cmd)

        if sort:
            ret.sort(key=key)
        return ret

    def get_destination(self):
        return self.context

    def send_error_message(self, error):
        """Handles the implementation when an error happens in the help command.
        For example, the result of :meth:`command_not_found` or
        :meth:`command_has_no_subcommand_found` will be passed here.

        You can override this method to customise the behaviour.

        By default, this sends the error message to the destination
        specified by :meth:`get_destination`.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

        Parameters
        ------------
        error: :class:`str`
            The error message to display to the user. Note that this has
            had mentions removed to prevent abuse.
        """
        destination = self.get_destination()
        destination.send(error)

    @_not_overriden
    def on_help_command_error(self, ctx, error):
        """The help command's error handler, as specified by :ref:`ext_commands_error_handler`.

        Useful to override if you need some specific behaviour when the error handler
        is called.

        By default this method does nothing and just propagates to the default
        error handlers.

        Parameters
        ------------
        ctx: :class:`Context`
            The invocation context.
        error: :class:`CommandError`
            The error that was raised.
        """
        pass

    def send_bot_help(self, mapping):
        """Handles the implementation of the bot command page in the help command.
        This function is called when the help command is called with no arguments.

        It should be noted that this method does not return anything -- rather the
        actual message sending should be done inside this method. Well behaved subclasses
        should use :meth:`get_destination` to know where to send, as this is a customisation
        point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

            Also, the commands in the mapping are not filtered. To do the filtering
            you will have to call :meth:`filter_commands` yourself.

        Parameters
        ------------
        mapping: Mapping[Optional[:class:`Cog`], List[:class:`Command`]]
            A mapping of cogs to commands that have been requested by the user for help.
            The key of the mapping is the :class:`~.commands.Cog` that the command belongs to, or
            ``None`` if there isn't one, and the value is a list of commands that belongs to that cog.
        """
        return None

    def send_cog_help(self, cog):
        """Handles the implementation of the cog page in the help command.
        This function is called when the help command is called with a cog as the argument.

        It should be noted that this method does not return anything -- rather the
        actual message sending should be done inside this method. Well behaved subclasses
        should use :meth:`get_destination` to know where to send, as this is a customisation
        point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

            To get the commands that belong to this cog see :meth:`Cog.get_commands`.
            The commands returned not filtered. To do the filtering you will have to call
            :meth:`filter_commands` yourself.

        Parameters
        -----------
        cog: :class:`Cog`
            The cog that was requested for help.
        """
        return None

    def send_command_help(self, command):
        """Handles the implementation of the single command page in the help command.

        It should be noted that this method does not return anything -- rather the
        actual message sending should be done inside this method. Well behaved subclasses
        should use :meth:`get_destination` to know where to send, as this is a customisation
        point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

        .. admonition:: Showing Help
            :class: helpful

            There are certain attributes and methods that are helpful for a help command
            to show such as the following:

            - :attr:`Command.help`
            - :attr:`Command.brief`
            - :attr:`Command.short_doc`
            - :attr:`Command.description`
            - :meth:`get_command_signature`

            There are more than just these attributes but feel free to play around with
            these to help you get started to get the output that you want.

        Parameters
        -----------
        command: :class:`Command`
            The command that was requested for help.
        """
        return None

    def prepare_help_command(self, ctx, command=None):
        """A low level method that can be used to prepare the help command
        before it does anything. For example, if you need to prepare
        some state in your subclass before the command does its processing
        then this would be the place to do it.

        The default implementation does nothing.

        .. note::

            This is called *inside* the help command callback body. So all
            the usual rules that happen inside apply here as well.

        Parameters
        -----------
        ctx: :class:`Context`
            The invocation context.
        command: Optional[:class:`str`]
            The argument passed to the help command.
        """
        pass

    def command_callback(self, ctx, *, command=None):
        """The actual implementation of the help command.

        It is not recommended to override this method and instead change
        the behaviour through the methods that actually get dispatched.

        - :meth:`send_bot_help`
        - :meth:`send_cog_help`
        - :meth:`send_group_help`
        - :meth:`send_command_help`
        - :meth:`get_destination`
        - :meth:`command_not_found`
        - :meth:`subcommand_not_found`
        - :meth:`send_error_message`
        - :meth:`on_help_command_error`
        - :meth:`prepare_help_command`
        """
        self.prepare_help_command(ctx, command)
        bot = ctx.bot

        if command is None:
            mapping = self.get_bot_mapping()
            return self.send_bot_help(mapping)

        # Check if it's a cog
        cog = bot.get_cog(command)
        if cog is not None:
            return self.send_cog_help(cog)

        # If it's not a cog then it's a command.
        # Since we want to have detailed errors when someone
        # passes an invalid subcommand, we need to walk through
        # the command group chain ourselves.
        keys = command.split(" ")
        cmd = bot.commands.get(keys[0])
        if cmd is None:
            string = self.command_not_found(self.remove_mentions(keys[0]))
            return self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.commands.get(key)
            except AttributeError:
                string = self.subcommand_not_found(cmd, self.remove_mentions(key))
                return self.send_error_message(string)
            else:
                if found is None:
                    string = self.subcommand_not_found(cmd, self.remove_mentions(key))
                    return self.send_error_message(string)
                cmd = found

        return self.send_command_help(cmd)


_IS_ASCII = re.compile(r"^[\x00-\x7f]+$")


def _string_width(string, *, _IS_ASCII=_IS_ASCII):
    """Returns string's width."""
    match = _IS_ASCII.match(string)
    if match:
        return match.endpos

    UNICODE_WIDE_CHAR_TYPE = "WFA"
    width = 0
    func = unicodedata.east_asian_width
    for char in string:
        width += 2 if func(char) in UNICODE_WIDE_CHAR_TYPE else 1
    return width


class DefaultHelpCommand(HelpCommand):
    """The implementation of the default help command.

    This inherits from :class:`HelpCommand`.

    It extends it with the following attributes.

    Attributes
    ------------
    sort_commands: :class:`bool`
        Whether to sort the commands in the output alphabetically. Defaults to ``True``.
    commands_heading: :class:`str`
        The command list's heading string used when the help command is invoked with a category name.
        Useful for i18n. Defaults to ``"Commands:"``
    no_category: :class:`str`
        The string used when there is a command which does not belong to any category(cog).
        Useful for i18n. Defaults to ``"No Category"``
    title: :class:`str`
        The title of the help command to be displayed at the top. Defaults to None
    """

    def __init__(self, **options):
        self.sort_commands = options.pop("sort_commands", True)
        self.commands_heading = options.pop("commands_heading", "Commands:")
        self.no_category = options.pop("no_category", "No Category")
        self.title = options.pop("title", None)

        super().__init__(**options)

    def get_ending_note(self):
        """Returns help command's ending note. This is mainly useful to override for i18n purposes."""
        command_name = self.command_name
        return (
            "Type /{0} [command] for more info on a command.\n"
            "You can also type /{0} [category] for more info on a category.".format(
                command_name
            )
        )

    def get_destination(self):
        return self.context

    def prepare_help_command(self, ctx, command):
        super().prepare_help_command(ctx, command)

    def format_commands(self, commands, *, heading, max_size=None):
        if not commands:
            return []

        formatted = []

        formatted.append(heading)

        for command in commands:
            name = command.name
            entry = "/{0} - {1}".format(name, command.description)
            formatted.append(entry)

        return formatted

    def send_help_text(self, help_text):
        destination = self.get_destination()

        message = "\n".join(help_text)

        destination.send(message, parse_mode="HTML")

    def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        help_text = []

        if bot.description:
            # <description> portion
            help_text.append(bot.description)

        no_category = "<b>{0.no_category}:</b>".format(self)

        def get_category(command, *, no_category=no_category):
            cog = command.cog
            return (
                "<b>{}:</b>".format(cog.qualified_name)
                if cog is not None
                else no_category
            )

        filtered = self.filter_commands(bot.commands.values(), sort=True, key=get_category)
        to_iterate = itertools.groupby(filtered, key=get_category)

        # Now we can add the commands to the page.
        for category, commands in to_iterate:
            commands = (
                sorted(commands, key=lambda c: c.name)
                if self.sort_commands
                else list(commands)
            )
            added = self.format_commands(commands, heading=category)
            if added:
                help_text.extend(added)
                help_text.append("")  # blank line

        note = self.get_ending_note()
        if note:
            help_text.append("")  # blank line
            help_text.append(note)

        self.send_help_text(help_text)

    def format_command(self, command):
        """A utility function to format the non-indented block of commands and groups.

        Parameters
        ------------
        command: :class:`Command`
            The command to format.
        """

        help_text = []

        if command.description:
            help_text.append(command.description)

        signature = self.get_command_signature(command)
        help_text.append(signature)

        return help_text

    def send_command_help(self, command):
        self.send_help_text(self.format_command(command))

    def send_cog_help(self, cog):
        help_text = []

        if cog.description:
            help_text.append(cog.description)

        filtered = self.filter_commands(cog.get_commands(), sort=self.sort_commands)
        help_text.extend(self.format_commands(filtered, heading=self.commands_heading))

        note = self.get_ending_note()
        if note:
            help_text.append("")  # blank line
            help_text.append(note)

        self.send_help_text(help_text)
