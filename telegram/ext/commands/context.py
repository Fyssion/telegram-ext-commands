from telegram import error


class Context:
    def __init__(self, command, update, context):
        self.command = command
        self.bot = command.bot
        self.update = update
        self.context = context
        self.update_id: int = update.update_id
        self.message = update.effective_message
        self.chat = update.effective_chat
        self.user = update.effective_user
        self.args = context.args
        self.me = context.bot

    def send(self, text="", *, reply=None, parse_mode=None, photo=None):
        if photo:
            try:
                return self.me.send_photo(
                    self.chat.id,
                    photo=photo,
                    caption=text,
                    parse_mode=parse_mode,
                    reply_to_message_id=reply,
                )
            except error.BadRequest:
                photo.seek(0)
                return self.me.send_document(
                    self.chat.id,
                    document=photo,
                    filename="photo.png",
                    caption=text,
                    parse_mode=parse_mode,
                    reply_to_message_id=reply,
                )

        return self.me.send_message(
            self.chat.id, text=text, parse_mode=parse_mode, reply_to_message_id=reply
        )

    def reply(self, text="", **kwargs):
        self.send(text, reply=self.message, **kwargs)
