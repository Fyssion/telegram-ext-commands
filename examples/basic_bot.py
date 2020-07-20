from telegram.ext import commands
import telegram


bot = commands.Bot(token="token_here")


@bot.command(description="Start command for the bot", aliases=["help"])
def start(ctx):
    ctx.send("Hi! I'm a bot. I was made by Fyssion.")


bot.run()
