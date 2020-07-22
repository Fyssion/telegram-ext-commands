from ._types import _BaseCommand


class CogMeta(type):
    def __new__(cls, *args, **kwargs):
        name, bases, attrs = args
        attrs["__cog_name__"] = kwargs.pop("name", name)
        attrs["__cog_hidden__"] = kwargs.pop("hidden", False)
        attrs["__cog_settings__"] = command_attrs = kwargs.pop("command_attrs", {})

        commands = {}
        no_bot_cog = (
            "Commands must not start with cog_ or bot_ (in method {0.__name__}.{1})"
        )

        new_cls = super().__new__(cls, name, bases, attrs, **kwargs)
        for base in reversed(new_cls.__mro__):
            for elem, value in base.__dict__.items():
                if elem in commands:
                    del commands[elem]

                is_static_method = isinstance(value, staticmethod)
                if is_static_method:
                    value = value.__func__
                if isinstance(value, _BaseCommand):
                    if is_static_method:
                        raise TypeError(
                            f"Command in method {base}.{elem!r} must not be staticmethod."
                        )
                    if elem.startswith(("cog_", "bot_")):
                        raise TypeError(no_bot_cog.format(base, elem))
                    commands[elem] = value

        new_cls.__cog_commands__ = list(
            commands.values()
        )  # this will be copied in Cog.__new__

        return new_cls


def _cog_special_method(func):
    func.__cog_special_method__ = None
    return func


class Cog(metaclass=CogMeta):
    def __new__(cls, *args, **kwargs):
        # We need to store a copy of the command objects
        # since we modify them to inject `self` to them.
        # To do this, we need to interfere with the Cog creation process.
        self = super().__new__(cls)
        cmd_attrs = cls.__cog_settings__

        # Either update the command with the cog provided defaults or copy it.
        self.__cog_commands__ = tuple(
            c._update_copy(cmd_attrs) for c in cls.__cog_commands__
        )

        lookup = {cmd.qualified_name: cmd for cmd in self.__cog_commands__}

        # Update the Command instances dynamically as well
        for command in self.__cog_commands__:
            setattr(self, command.callback.__name__, command)
            parent = command.parent
            if parent is not None:
                # Get the latest parent reference
                parent = lookup[parent.qualified_name]

                # Update our parent's reference to our self
                removed = parent.remove_command(command.name)
                parent.add_command(command)

        return self

    @classmethod
    def _get_overridden_method(cls, method):
        """Return None if the method is not overridden. Otherwise returns the overridden method."""
        return getattr(method.__func__, '__cog_special_method__', method)

    def get_commands(self):
        return [c for c in self.__cog_commands__ if not c.parent]

    @property
    def qualified_name(self):
        return self.__cog_name__

    @_cog_special_method
    def cog_unload(self):
        pass

    @_cog_special_method
    def cog_before_invoke(self, ctx):
        pass

    @_cog_special_method
    def cog_after_invoke(self, ctx):
        pass

    @_cog_special_method
    def cog_check(self, ctx):
        pass

    def _inject(self, bot):
        # realistically, the only thing that can cause loading errors
        # is essentially just the command loading, which raises if there are
        # duplicates. When this condition is met, we want to undo all what
        # we've added so far for some form of atomic loading.
        for index, command in enumerate(self.__cog_commands__):
            command.cog = self
            if command.parent is None:
                try:
                    bot.add_command(command)
                except Exception as e:
                    # undo our additions
                    for to_undo in self.__cog_commands__[:index]:
                        bot.remove_command(to_undo)
                    raise e

        return self

    def _eject(self, bot):
        try:
            for command in self.__cog_commands__:
                if command.parent is None:
                    bot.remove_command(command.name)
        finally:
            self.cog_unload()
