from telegram.ext import commands
import telegram

import logging

# Set up basic logging to get useful info in the console
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Create a Bot instance with a token
# You can specify owner_ids if you wish to use
# the commands.is_owner() check
bot = commands.Bot(token="token_here", owner_ids=[1234567890])


# Create a basic 'hi' command for the bot
@bot.command(description="Greet me", aliases=["hello"])
def hi(ctx):
    ctx.send(
        "Hi! I'm a bot. I was made with python-telegram-bot and telegram-ext-commands."
    )


# Run the bot
bot.run()
