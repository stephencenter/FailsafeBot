import os
import sys
import asyncio
import logging
from datetime import datetime
from telegram.ext import ApplicationBuilder
from telegram.error import InvalidToken
import discord
from discord.ext.commands import Bot as DiscordBot
from discord.errors import LoginFailure
from loguru import logger
import commands
import sound_manager
import settings

TELEGRAM_TOKEN_PATH = os.path.join("Data", "telegram_token.txt")
DISCORD_TOKEN_PATH = os.path.join("Data", "discord_token.txt")

discord_bot = None

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Convert LogRecord to Loguru format
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.bind(request_id="app").opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

def init_logging():
    # Clear default logger
    logger.remove()

    # Add console output
    logger.add(sys.stderr, level="INFO", backtrace=False, diagnose=False)

    # Add file output with error logging
    logger.add("Data/logging/log.txt", level="WARNING", backtrace=False, diagnose=False)

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    # Optional: override individual modules' logging levels if needed
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)

    # Hook unhandled exceptions
    def log_exceptions(exc_type, exc_value, exc_traceback):
        logger.error("Unhandled exception")

    sys.excepthook = log_exceptions

    return

async def create_run_telegram_bot(telegram_token: str):
    # Create telegram bot object
    telegram_bot = ApplicationBuilder().token(telegram_token).build()
    await telegram_bot.initialize()
    await telegram_bot.start()

    # Register all commands to the telegram bot
    commands.register_commands(telegram_bot)

    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling(drop_pending_updates=True)

async def create_run_discord_bot(discord_token: str):
    global discord_bot

    # Set intents for discord bot
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    # Create discord bot object
    discord_bot = DiscordBot(command_prefix='/', intents=intents, help_command=None)

    # Register all commands to the discord bot
    commands.register_commands(discord_bot)

    await discord_bot.start(discord_token)

async def initialize_and_run():
    print(f"Starting script {commands.VERSION_NUMBER} at {datetime.now()}")
    config = settings.Config()

    for problem in sound_manager.verify_aliases():
        print(problem)

    if config.main.runtelegram:
        # Retrieve telegram bot token from file
        try:
            with open(TELEGRAM_TOKEN_PATH, encoding='utf-8') as f:
                telegram_token = f.readline().strip()
        except FileNotFoundError:
            telegram_token = None

        # Attempt to run Telgram bot
        if telegram_token is not None:
            print("Starting telegram bot")
            try:
                await create_run_telegram_bot(telegram_token)
            except InvalidToken:
                print(f"Telegram token at {TELEGRAM_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            print(f"Telegram token not found at {TELEGRAM_TOKEN_PATH}, couldn't start bot")
    else:
        print("Telegram bot disabled in settings.toml, skipping")

    if config.main.rundiscord:
        # Retrieve discord bot token from file
        try:
            with open(DISCORD_TOKEN_PATH, encoding='utf-8') as f:
                discord_token = f.readline().strip()
        except FileNotFoundError:
            discord_token = None

        # Attempt to run Discord bot
        if discord_token is not None:
            print("Starting discord bot")
            try:
                await create_run_discord_bot(discord_token)
            except LoginFailure:
                print(f"Discord token at {DISCORD_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            print(f"Discord token not found at {DISCORD_TOKEN_PATH}, couldn't start bot")
    else:
        print(f"Discord bot disabled in {settings.CONFIG_PATH}, skipping")

    await asyncio.Event().wait()

async def main():
    try:
        with logger.catch():
            await initialize_and_run()
    finally:
        if isinstance(discord_bot, DiscordBot):
            # Disconnect from discord voice channels if necessary
            try:
                bot_channel = discord_bot.voice_clients[0].channel
            except IndexError:
                return

            if isinstance(bot_channel, discord.VoiceChannel):
                print('Disconnecting from voice channel...')
                await discord_bot.voice_clients[0].disconnect(force=False)

        print('Exiting...')

if __name__ == "__main__":
    # Initialize logging
    init_logging()

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.exceptions.CancelledError, RuntimeError, RuntimeWarning):
        pass
