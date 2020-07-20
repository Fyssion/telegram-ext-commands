from telegram.ext import commands
import telegram

import logging


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


bot = commands.Bot(token="token_here")


@bot.command(description="Start command for the bot", aliases=["help"])
def start(ctx):
    ctx.send(
        "Hi! I'm a bot. I was made with python-telegram-bot and telegram-ext-commands."
    )


bot.run()
