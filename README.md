# Failsafe Bot
Bot for Discord and Telegram in one package with unified commands.

Built with Python using [Discord.py](https://discordpy.readthedocs.io/en/stable/) and [python-telegram-bot](https://python-telegram-bot.org/). Compatible with both Windows and Linux.

## Features
- Supports Discord and Telegram bots in one script
- Easily create new commands that work on both platforms without needing to learn their APIs
- Built-in commands for sound effects, trivia, dice rolling, etc.
- GPT-powered AI chatting (provide your own key)
- ElevenLabs-powered AI text-to-speech (provide your own key)
- Discord voice support for sound effects & text-to-speech
- Whitelist specific users and chats
- Configure bot settings using chat commands
- Require admin role for specific commands

## How to use
Failsafe Bot requires **Python version >=3.12** to run. It is recommended that you use [uv](https://docs.astral.sh/uv/) and the included `uv.lock` and `pyproject.toml` files to create the environment for running this project. The instructions below will assume you are doing so.

### Step 1: Get Tokens
Follow these tutorials until you have bot tokens for both Telegram and Discord:
- **Telegram**: https://core.telegram.org/bots/features#botfather
- **Discord**: https://discordpy.readthedocs.io/en/stable/discord.html

### Step 2: Download Project
Download a `.zip` file of this repository, then open it and locate `main.py`.

### Step 3: Create Environment
Open the folder containing `main.py` in a terminal and set up a virtual environment with `uv sync`.

### Step 4: Build Structure
Enter `uv run main.py` into the terminal and hit enter. The script should start running, create a number of files and folders, and then exit.

### Step 5: Enter Tokens
Navigate to the newly-created `Data` folder and find the files named `discord_token.txt` and `telegram_token.txt`. Paste your Discord token into the first line of `discord_token.txt`, and do the same with your Telegram token and `telegram_token.txt`.

### Step 6: Activate Bot
You should now be able to return to the folder containing `main.py` and run `uv run main.py` again. If the script gets to the line that says `Setup Complete, polling for user commands...` then the script is working and your bots should begin responding to commands.

Try /help for a list of commands to experiment with.
