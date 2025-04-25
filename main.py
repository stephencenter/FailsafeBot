import asyncio
import contextlib
import sys

import discord
from discord.errors import LoginFailure as DiscordInvalidToken
from discord.ext.commands import Bot as DiscordBot
from loguru import logger
from telegram.error import InvalidToken as TelegramInvalidToken
from telegram.ext import Application as TelegramBot
from telegram.ext import ApplicationBuilder

import command_list
import common
import runway
import sound_manager


def prepare_runway() -> None:
    # Initialize logging
    runway.init_logging()
    logger.info(f"Loaded {common.APPLICATION_NAME} {common.VERSION_NUMBER}, logging to {common.LOGGING_FILE_PATH}")

    # Make sure all files and folders exist that this script needs
    for info in runway.create_project_structure():
        logger.info(info)

    # Clear temp folder if it wasn't already
    for info in runway.clear_temp_folder():
        logger.info(info)

    # Check for any paths defined in common.py that weren't included in the above check
    # (for debug purposes, this should never happen in production)
    for warning in runway.check_for_missing_paths():
        logger.warning(warning)

    # Check for common issues with sound aliases
    for warning in sound_manager.verify_aliases():
        logger.warning(warning)

    # Check for common issues with settings dataclasses
    # (for debug purposes, this should never happen in production)
    for warning in common.verify_settings():
        logger.warning(warning)


async def try_start_telegram_bot() -> TelegramBot | None:
    config = common.Config()
    if not config.main.runtelegram:
        logger.info(f"Telegram bot disabled in {common.CONFIG_PATH}, skipping")
        return None

    telegram_token = common.try_read_single_line(common.TELEGRAM_TOKEN_PATH, None)
    if telegram_token is None:
        logger.error(f"Telegram bot is enabled but token not found at {common.TELEGRAM_TOKEN_PATH}, couldn't start bot")
        return None

    telegram_bot = ApplicationBuilder().token(telegram_token).build()

    try:
        await telegram_bot.initialize()

    except TelegramInvalidToken:
        logger.error(f"Telegram token at {common.TELEGRAM_TOKEN_PATH} was rejected, couldn't start bot")
        return None

    logger.info("Starting telegram bot")
    await telegram_bot.start()
    command_list.register_commands(telegram_bot)

    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling(drop_pending_updates=True)

    return telegram_bot


async def try_start_discord_bot() -> tuple[DiscordBot | None, asyncio.Task | None]:
    config = common.Config()
    if not config.main.rundiscord:
        logger.info(f"Discord bot disabled in {common.CONFIG_PATH}, skipping")
        return None, None

    discord_token = common.try_read_single_line(common.DISCORD_TOKEN_PATH, None)
    if discord_token is None:
        logger.error(f"Discord bot is enabled but token not found at {common.DISCORD_TOKEN_PATH}, couldn't start bot")
        return None, None

    logger.info("Starting discord bot")
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    discord_bot = DiscordBot(command_prefix='/', intents=intents, help_command=None)
    command_list.register_commands(discord_bot)

    try:
        await discord_bot.login(discord_token)
        discord_task = asyncio.create_task(discord_bot.connect())

    except DiscordInvalidToken:
        logger.error(f"Discord token at {common.DISCORD_TOKEN_PATH} was rejected, couldn't start bot")
        return None, None

    return discord_bot, discord_task


async def shutdown_telegram_bot(telegram_bot: TelegramBot | None) -> None:
    if telegram_bot is not None:
        if telegram_bot.updater is not None:
            await telegram_bot.updater.stop()

        await telegram_bot.stop()
        await telegram_bot.shutdown()


async def shutdown_discord_bot(discord_bot: DiscordBot | None, discord_task: asyncio.Task | None) -> None:
    if discord_bot is not None:
        logger.info("Shutting down discord bot...")
        with contextlib.suppress(IndexError):
            # Disconnect from discord voice channels if necessary
            bot_channel = discord_bot.voice_clients[0].channel

            if isinstance(bot_channel, discord.VoiceChannel):
                logger.info('Disconnecting discord bot from voice channel...')
                await discord_bot.voice_clients[0].disconnect(force=False)

        await discord_bot.close()

    if discord_task is not None:
        discord_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await discord_task


async def main() -> None:
    telegram_bot = None
    discord_bot = None
    discord_task = None
    try:
        telegram_bot = await try_start_telegram_bot()
        discord_bot, discord_task = await try_start_discord_bot()

        if telegram_bot is None and discord_bot is None:
            logger.info("No bots were started, script will exit now")

        else:
            logger.info("Setup complete, polling for user commands...")
            await asyncio.Event().wait()  # Continue with tasks until they are completed or user exits

    finally:
        await shutdown_telegram_bot(telegram_bot)
        await shutdown_discord_bot(discord_bot, discord_task)
        logger.info('Exiting...')


if __name__ == "__main__":
    prepare_runway()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
