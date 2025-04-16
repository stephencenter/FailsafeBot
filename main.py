import asyncio
import contextlib
import sys

import discord
from discord.errors import LoginFailure
from discord.ext.commands import Bot as DiscordBot
from loguru import logger
from telegram.error import InvalidToken
from telegram.ext import Application as TelegramBot
from telegram.ext import ApplicationBuilder

import command_list
import common
import runway
import sound_manager


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


async def create_run_telegram_bot(telegram_token: str) -> TelegramBot:
    # Create telegram bot object
    telegram_bot = ApplicationBuilder().token(telegram_token).build()
    await telegram_bot.initialize()
    await telegram_bot.start()

    # Register all commands to the telegram bot
    command_list.register_commands(telegram_bot)

    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling(drop_pending_updates=True)

    return telegram_bot


async def create_run_discord_bot(discord_token: str) -> tuple[DiscordBot, asyncio.Task[None]]:
    # Set intents for discord bot
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    # Create discord bot object
    discord_bot = DiscordBot(command_prefix='/', intents=intents, help_command=None)

    # Register all commands to the discord bot
    command_list.register_commands(discord_bot)

    # Create a background task to start the discord bot
    discord_task = asyncio.create_task(discord_bot.start(discord_token))

    return discord_bot, discord_task


async def initialize_and_run() -> tuple[TelegramBot | None, DiscordBot | None, asyncio.Task | None]:
    logger.info(f"Starting {common.APPLICATION_NAME} {common.VERSION_NUMBER}")
    config = common.Config()

    telegram_bot = None
    if config.main.runtelegram:
        # Retrieve telegram bot token from file
        telegram_token = common.try_read_single_line(common.TELEGRAM_TOKEN_PATH, None)

        # Attempt to run Telgram bot
        if telegram_token is not None:
            logger.info("Starting telegram bot")
            try:
                telegram_bot = await create_run_telegram_bot(telegram_token)
            except InvalidToken:
                logger.error(f"Telegram token at {common.TELEGRAM_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            logger.error(f"Telegram bot is enabled but token not found at {common.TELEGRAM_TOKEN_PATH}, couldn't start bot")
    else:
        logger.info(f"Telegram bot disabled in {common.CONFIG_PATH}, skipping")

    discord_bot = None
    discord_task = None
    if config.main.rundiscord:
        # Retrieve discord bot token from file
        discord_token = common.try_read_single_line(common.DISCORD_TOKEN_PATH, None)

        # Attempt to run Discord bot
        if discord_token is not None:
            logger.info("Starting discord bot")
            try:
                discord_bot, discord_task = await create_run_discord_bot(discord_token)
            except LoginFailure:
                logger.error(f"Discord token at {common.DISCORD_TOKEN_PATH} is invalid, couldn't start bot")
        else:
            logger.error(f"Discord bot is enabled but token not found at {common.DISCORD_TOKEN_PATH}, couldn't start bot")
    else:
        logger.info(f"Discord bot disabled in {common.CONFIG_PATH}, skipping")

    return telegram_bot, discord_bot, discord_task


async def main() -> None:
    try:
        _, discord_bot, discord_task = await initialize_and_run()
        await asyncio.Event().wait()  # Continue with tasks until they are completed or user exits

    finally:
        if discord_bot is not None:
            with contextlib.suppress(IndexError):
                # Disconnect from discord voice channels if necessary
                bot_channel = discord_bot.voice_clients[0].channel

                if isinstance(bot_channel, discord.VoiceChannel):
                    logger.info('Disconnecting from voice channel...')
                    await discord_bot.voice_clients[0].disconnect(force=False)

        if discord_task:
            discord_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await discord_task

        logger.info('Exiting...')


if __name__ == "__main__":
    prepare_runway()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
