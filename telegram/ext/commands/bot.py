from telegram.ext import Updater, CommandHandler

from .core import Command


class Bot:
    def __init__(self, token):
        self.commands = {}
        self._handlers = {}
        self.updater = Updater(token=token, use_context=True)
        self.dispatcher = self.updater.dispatcher

    def add_command(self, command):
        if command.name in self.commands.keys():
            raise ValueError("There is already a command with that name")

        self.commands[command.name] = command

        self._handlers[command.name] = CommandHandler(command.name, command)
        self.dispatcher.add_handler(self._handlers[command.name])

        if command.aliases:
            for alias in command.aliases:
                self._handlers[alias] = CommandHandler(alias, command)
                self.dispatcher.add_handler(self._handlers[alias])

    def remove_command(self, command_name):
        if command_name not in self.commands.keys:
            raise ValueError("There is no command with that name")

        command = self.commands.pop(command_name)
        self._handlers.pop(command_name)
        self.dispatcher.remove_handler(command_name)

        if command.aliases:
            for alias in command.aliases:
                self._handlers.pop(alias)
                self.dispatcher.remove_handler(alias)

    def command(self, **kwargs):
        def decorater(func):
            if isinstance(func, Command):
                raise TypeError("Callback is already a command")

            command = Command(self, func, **kwargs)
            self.add_command(command)
            return command

        return decorater

    def stop(self):
        self.updater.stop()

    def run(self, *, idle=True):
        self.updater.start_polling()

        if idle:
            self.updater.idle()

    def idle(self):
        self.updater.idle()
