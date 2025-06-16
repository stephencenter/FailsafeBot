"""Main module, do not import. Run this module to start the bots."""

import asyncio
import contextlib
import sys
from typing import Any

import discord
from discord.errors import LoginFailure as DiscordInvalidToken
from discord.ext import commands as discord_commands
from loguru import logger
from telegram.error import InvalidToken as TelegramInvalidToken
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

import command
import command_list
import common
import runway
import sound


async def prepare_runway() -> None:
    # Initialize logging
    runway.init_logging()
    logger.info(f"Loaded {common.APPLICATION_NAME} {common.VERSION_NUMBER}, logging to {common.PATH_LOGGING_FILE}")

    # Make sure all files and folders exist that this script needs
    for info in runway.create_project_structure():
        logger.info(info)

    # Clear temp folder if it isn't already
    for info in runway.clear_temp_folder():
        logger.info(info)

    # Check for any paths defined in common.py that weren't included in the above check
    # (for debug purposes, this should never happen in production)
    for warning in runway.check_for_untracked_paths():
        logger.warning(warning)

    for warning in command_list.check_unregistered_commands():
        logger.warning(warning)

    # Check for common issues with sound aliases
    async for warning in sound.verify_aliases():
        logger.warning(warning)

    # Check for common issues with settings dataclasses
    # (for debug purposes, this should never happen in production)
    async for warning in common.verify_settings():
        logger.warning(warning)

    async for warning in runway.check_superadmins():
        logger.warning(warning)


async def try_start_telegram_bot() -> command.TelegramBotAnn | None:
    config = await common.Config.load()
    if not config.main.runtelegram.value:
        logger.info(f"Telegram bot disabled in {common.PATH_CONFIG_FILE}, skipping")
        return None

    # Retrieve telegram token
    telegram_token = await common.try_read_single_line(common.PATH_TELEGRAM_TOKEN, None)
    if telegram_token is None:
        error_msg = f"Telegram bot is enabled but no token found at {common.PATH_TELEGRAM_TOKEN}, couldn't start bot"
        logger.error(error_msg)
        return None

    telegram_bot: command.TelegramBotAnn = ApplicationBuilder().token(telegram_token).build()

    try:
        await telegram_bot.initialize()

    except TelegramInvalidToken:
        logger.error(f"Telegram token at {common.PATH_TELEGRAM_TOKEN} was rejected, couldn't start bot")
        return None

    logger.info("Starting telegram bot")
    await telegram_bot.start()

    # Register commands
    for function in command_list.COMMAND_LIST:
        wrapped_command = command.wrap_telegram_command(telegram_bot, function[1])
        telegram_bot.add_handler(CommandHandler(function[0], wrapped_command))

    for function in command_list.FILE_COMMAND_LIST:
        r_string = rf'^/{function[0]}'
        regex = (filters.ALL & filters.CaptionRegex(r_string)) | (filters.TEXT & filters.Regex(r_string))
        wrapped_command = command.wrap_telegram_command(telegram_bot, function[1])
        telegram_bot.add_handler(MessageHandler(regex, wrapped_command))

    wrapped_msg_handler = command.wrap_telegram_command(telegram_bot, command_list.handle_message_event)
    telegram_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), wrapped_msg_handler))

    # Begin polling
    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling(drop_pending_updates=True)

    return telegram_bot


async def try_start_discord_bot() -> tuple[command.DiscordBotAnn | None, asyncio.Task[Any] | None]:
    config = await common.Config.load()
    if not config.main.rundiscord.value:
        logger.info(f"Discord bot disabled in {common.PATH_CONFIG_FILE}, skipping")
        return None, None

    # Retrieve discord token
    discord_token = await common.try_read_single_line(common.PATH_DISCORD_TOKEN, None)
    if discord_token is None:
        logger.error(f"Discord bot is enabled but no token found at {common.PATH_DISCORD_TOKEN}, couldn't start bot")
        return None, None

    logger.info("Starting discord bot")
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    discord_bot = command.DiscordBotAnn(
        command_prefix=common.COMMAND_PREFIX,
        intents=intents,
        help_command=None,
    )

    # Register commands
    for function in [*command_list.COMMAND_LIST, *command_list.FILE_COMMAND_LIST]:
        wrapped = command.wrap_discord_command(discord_bot, function[1])
        new_command: discord_commands.Command[Any, Any, Any] = discord_commands.Command(wrapped)
        new_command.name = function[0]
        discord_bot.add_command(new_command)

    await command_list.discord_register_events(discord_bot)

    # Login and start polling
    try:
        await discord_bot.login(discord_token)
        discord_task = asyncio.create_task(discord_bot.connect())

    except DiscordInvalidToken:
        logger.error(f"Discord token at {common.PATH_DISCORD_TOKEN} was rejected, couldn't start bot")
        return None, None

    return discord_bot, discord_task


async def stop_telegram_bot(telegram_bot: command.TelegramBotAnn | None) -> None:
    if telegram_bot is not None:
        logger.info("Shutting down telegram bot...")

        if telegram_bot.updater is not None:
            await telegram_bot.updater.stop()

        await telegram_bot.stop()
        await telegram_bot.shutdown()


async def stop_discord_bot(discord_bot: command.DiscordBotAnn | None, discord_task: asyncio.Task[Any] | None) -> None:
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

    await prepare_runway()
    try:
        telegram_bot = await try_start_telegram_bot()
        discord_bot, discord_task = await try_start_discord_bot()

        if telegram_bot is None and discord_bot is None:
            logger.info("No bots were started, script will exit now")

        else:
            logger.info("Setup complete, polling for user commands...")
            await asyncio.Event().wait()  # Continue with tasks until they are completed or user exits

    finally:
        await stop_telegram_bot(telegram_bot)
        await stop_discord_bot(discord_bot, discord_task)
        logger.info('Exiting...')


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
