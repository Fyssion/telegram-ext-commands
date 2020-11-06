# telegram-ext-commands

[![GitHub - License](https://img.shields.io/github/license/Fyssion/telegram-ext-commands)](https://github.com/Fyssion/telegram-ext-commands/blob/master/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Archive note

I am no longer maintaining this.
It was mainly a project to understand the internals of `discord.py`.

See [telegram.py](https://github.com/ilovetocode2019/telegram.py)

<hr>

Port of the [discord.py commands framework](https://discordpy.readthedocs.io/en/latest/ext/commands/index.html) to [python-telegram-bot](https://python-telegram-bot.org/)

This extension is mostly modified discord.py code. I had to make some changes and adjustments to fit with
telegram and python-telegram-bot.

This extension was also made mainly for my personal use.

## Note

This extension is still in development and is subject to breaking changes.

**It is also extremely unstable. DO NOT USE THIS IN PRODUCTION.**

### Todo list:

```
Key: [ ] Not started | [/] Incomplete | [x] Complete (I haven't tested it probably)

- [x] Basic bot and commands
- [x] Extensions and cogs
- [x] Argument parsing
- [ ] Documentation
- [x] HelpCommand
- [x] Checks?
- [x] Error handling
- [ ] More that I'm forgetting?
```

## Installation

Install with your favorite variant of the below:

```bash
python3 -m pip install git+https://github.com/Fyssion/telegram-ext-commands
```

## Quick Example

Here's a quick example for telegram-ext-commands

```py
from telegram.ext import commands
import telegram


bot = commands.Bot(token="token_here", owner_ids=[1234567890])


@bot.command(description="Greet me", aliases=["hello"])
def hi(ctx):
    ctx.send("Hi! I'm a bot. I was made with python-telegram-bot and telegram-ext-commands.")


bot.run()
```

## Requirements

- `python-telegram-bot`
