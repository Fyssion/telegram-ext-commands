# telegram-ext-commands

[![GitHub - License](https://img.shields.io/github/license/Fyssion/telegram-ext-commands)](https://github.com/Fyssion/telegram-ext-commands/blob/master/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Commands extension for python-telegram-bot based off of discord.py

## Installation

Install with your favorite varient of the below:

```bash
python3 -m pip install git+https://github.com/Fyssion/python-telegram-bot
```

## Quick Example

Here's a quick example for telegram-ext-commands

```py
from telegram.ext import commands
import telegram


bot = commands.Bot(token="token_here")


@bot.command(description="Start command for the bot", aliases=["help"])
def start(ctx):
    ctx.send("Hi! I'm a bot. I was made with python-telegram-bot and telegram-ext-commands.")


bot.run()
```

## Requirements

- `python-telegram-bot`
