from telegram.ext import CommandHandler as TelegramCommandHandler

# The only reason we need to override this is to fix the split() method that
# removes newlines
class CommandHandler(TelegramCommandHandler):
    def check_update(self, update):
        """Determines whether an update should be passed to this handlers :attr:`callback`.
        Args:
            update (:class:`telegram.Update`): Incoming telegram update.
        Returns:
            :obj:`list`: The list of args for the handler
        """
        if isinstance(update, Update) and update.effective_message:
            message = update.effective_message

            if (message.entities and message.entities[0].type == MessageEntity.BOT_COMMAND
                    and message.entities[0].offset == 0):
                command = message.text[1:message.entities[0].length]
                args = message.text.split()[1:]
                command = command.split('@')
                command.append(message.bot.username)

                if not (command[0].lower() in self.command
                        and command[1].lower() == message.bot.username.lower()):
                    return None

                filter_result = self.filters(update)
                if filter_result:
                    return args, filter_result
                else:
                    return False
