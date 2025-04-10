import asyncio
import logging
import sys
import contextlib

import discord
from discord.errors import LoginFailure
from discord.ext.commands import Bot as DiscordBot
from loguru import logger
from telegram.error import InvalidToken
from telegram.ext import ApplicationBuilder

import command_list
import common
import settings
import sound_manager

TELEGRAM_TOKEN_PATH = "Data/telegram_token.txt"
DISCORD_TOKEN_PATH = "Data/discord_token.txt"

discord_bot = None

class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Convert LogRecord to Loguru format
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.bind(request_id="app").opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

def init_logging() -> None:
    # Clear default logger
    logger.remove()

    # Add console output
    info_format = "{message} <level>[{level}]</level> <green>{time:YYYY-MM-DD HH:mm:ss}</green> <cyan>{name}:{function}:{line}</cyan>"
    logger.add(sys.stderr, level="INFO", backtrace=False, diagnose=False, format=info_format)

    # Add file output with error logging
    logger.add("Data/logging/log.txt", level="WARNING", backtrace=False, diagnose=False)

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    # Override logging levels for individual modules
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)

    # Hook unhandled exceptions
    def log_exceptions(exc_type, exc_value, exc_traceback) -> None: # noqa: ANN001
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).error("Unhandled exception")

    sys.excepthook = log_exceptions

async def create_run_telegram_bot(telegram_token: str) -> None:
    # Create telegram bot object
    telegram_bot = ApplicationBuilder().token(telegram_token).build()
    await telegram_bot.initialize()
    await telegram_bot.start()

    # Register all commands to the telegram bot
    command_list.register_commands(telegram_bot)

    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling(drop_pending_updates=True)

async def create_run_discord_bot(discord_token: str) -> None:
    global discord_bot

    # Set intents for discord bot
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    # Create discord bot object
    discord_bot = DiscordBot(command_prefix='/', intents=intents, help_command=None)

    # Register all commands to the discord bot
    command_list.register_commands(discord_bot)

    await discord_bot.start(discord_token)

async def initialize_and_run() -> None:
    logger.info(f"Starting {common.APPLICATION_NAME} {common.VERSION_NUMBER}")
    config = settings.Config()

    for problem in sound_manager.verify_aliases():
        logger.warning(problem)

    if config.main.runtelegram:
        # Retrieve telegram bot token from file
        telegram_token = common.try_read_single_line(TELEGRAM_TOKEN_PATH, None)

        # Attempt to run Telgram bot
        if telegram_token is not None:
            logger.info("Starting telegram bot")
            try:
                await create_run_telegram_bot(telegram_token)
            except InvalidToken:
                logger.error(f"Telegram token at {TELEGRAM_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            logger.error(f"Telegram token not found at {TELEGRAM_TOKEN_PATH}, couldn't start bot")
    else:
        logger.info(f"Telegram bot disabled in {settings.CONFIG_PATH}, skipping")

    if config.main.rundiscord:
        # Retrieve discord bot token from file
        discord_token = common.try_read_single_line(DISCORD_TOKEN_PATH, None)

        # Attempt to run Discord bot
        if discord_token is not None:
            logger.info("Starting discord bot")
            try:
                await create_run_discord_bot(discord_token)
            except LoginFailure:
                logger.error(f"Discord token at {DISCORD_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            logger.error(f"Discord token not found at {DISCORD_TOKEN_PATH}, couldn't start bot")
    else:
        logger.info(f"Discord bot disabled in {settings.CONFIG_PATH}, skipping")

    await asyncio.Event().wait()

async def main() -> None:
    try:
        await initialize_and_run()
    finally:
        if isinstance(discord_bot, DiscordBot):
            # Disconnect from discord voice channels if necessary
            with contextlib.suppress(IndexError):
                bot_channel = discord_bot.voice_clients[0].channel

                if isinstance(bot_channel, discord.VoiceChannel):
                    logger.info('Disconnecting from voice channel...')
                    await discord_bot.voice_clients[0].disconnect(force=False)

        logger.info('Exiting...')

if __name__ == "__main__":
    init_logging()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
