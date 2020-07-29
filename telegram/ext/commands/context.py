from telegram import error


class Context:
    def __init__(self, command, update, context, *, view):
        self.command = command
        self.bot = command.bot
        self.update = update
        self.context = context
        self.view = view
        self.update_id: int = update.update_id
        self.message = update.effective_message
        self.chat = update.effective_chat
        self.user = update.effective_user
        self.original_args = context.args
        self.text = self.message.text if self.message else None
        self.me = context.bot
        self.command_failed = False

        self.args = []
        self.kwargs = []

    @property
    def cog(self):
        """Returns the cog associated with this context's command. None if it does not exist."""

        if self.command is None:
            return None
        return self.command.cog

    def send(self, text="", *, reply=None, parse_mode=None, photo=None, reply_markup=None):
        if photo:
            try:
                return self.me.send_photo(
                    self.chat.id,
                    photo=photo,
                    caption=text,
                    parse_mode=parse_mode,
                    reply_to_message_id=reply,
                    reply_markup=reply_markup
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
                    reply_markup=reply_markup
                )

        return self.me.send_message(
            self.chat.id, text=text, parse_mode=parse_mode, reply_to_message_id=reply,
                    reply_markup=reply_markup
        )

    def reply(self, text="", **kwargs):
        self.send(text, reply=self.message.message_id, **kwargs)
