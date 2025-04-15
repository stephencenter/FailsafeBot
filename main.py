import asyncio
import contextlib
import sys

import discord
from discord.errors import LoginFailure
from discord.ext.commands import Bot as DiscordBot
from loguru import logger
from telegram.error import InvalidToken
from telegram.ext import ApplicationBuilder

import command_list
import common
import runway
import sound_manager

discord_bot = None


def prepare_runway() -> None:
    # Initialize logging
    runway.init_logging()
    logger.info(f"Initialized logging to {common.LOGGING_FILE_PATH}")

    # Make sure all files and folders exist that this script needs
    for info in runway.create_project_structure():
        logger.info(info)

    # Clear temp folder if it wasn't already
    for info in runway.clear_temp_folder():
        logger.info(info)

    # Check for any paths defined in common.py that weren't included in the above check
    # (for debug purposes, this should never happen)
    for warning in runway.check_for_missing_paths():
        logger.warning(warning)

    # Check for common issues with sound aliases
    for warning in sound_manager.verify_aliases():
        logger.warning(warning)

    # Check for common issues with settings dataclasses
    # (for debug purposes, this should never happen)
    for warning in common.verify_settings():
        logger.warning(warning)


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
    config = common.Config()

    if config.main.runtelegram:
        # Retrieve telegram bot token from file
        telegram_token = common.try_read_single_line(common.TELEGRAM_TOKEN_PATH, None)

        # Attempt to run Telgram bot
        if telegram_token is not None:
            logger.info("Starting telegram bot")
            try:
                await create_run_telegram_bot(telegram_token)
            except InvalidToken:
                logger.error(f"Telegram token at {common.TELEGRAM_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            logger.error(f"Telegram bot is enabled but token not found at {common.TELEGRAM_TOKEN_PATH}, couldn't start bot")
    else:
        logger.info(f"Telegram bot disabled in {common.CONFIG_PATH}, skipping")

    if config.main.rundiscord:
        # Retrieve discord bot token from file
        discord_token = common.try_read_single_line(common.DISCORD_TOKEN_PATH, None)

        # Attempt to run Discord bot
        if discord_token is not None:
            logger.info("Starting discord bot")
            try:
                await create_run_discord_bot(discord_token)
            except LoginFailure:
                logger.error(f"Discord token at {common.DISCORD_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            logger.error(f"Discord bot is enabled but token not found at {common.DISCORD_TOKEN_PATH}, couldn't start bot")
    else:
        logger.info(f"Discord bot disabled in {common.CONFIG_PATH}, skipping")

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
    prepare_runway()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
