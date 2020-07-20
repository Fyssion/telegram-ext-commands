from telegram.ext import Updater, CommandHandler

from .core import Command


class Bot:
    def __init__(self, token):
        self.commands = {}
        self._handlers = {}
        self.updater = Updater(token=token, pass_context=True)
        self.dispatcher = self.updater.dispatcher

    def add_command(self, command):
        if command.name in self.commands.keys():
            raise ValueError("There is already a command with that name")

        self.commands[command.name] = command

        self._handlers[command.name] = CommandHandler(command.name, command)

        if command.aliases:
            for alias in command.aliases:
                self._handlers[alias] = Command(alias, command)

    def remove_command(self, command_name):
        if command_name not in self.commands.keys:
            raise ValueError("There is no command with that name")

        command = self.commands.pop(command_name)
        self._handlers.pop(command_name)

        if command.aliases:
            for alias in command.aliases:
                self._handlers.pop(alias)

    def command(self, **kwargs):
        def wrapper(func):
            command = Command(self, func, **kwargs)
            self.add_command(command)
            return command

        return wrapper

    def stop(self):
        self.updater.stop()

    def run(self, idle=True):
        self.updater.start_polling()

        if idle:
            self.updater.idle()

    def idle(self):
        self.updater.idle()
