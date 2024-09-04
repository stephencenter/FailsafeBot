import os
import logging
import asyncio
from datetime import datetime
from logging.handlers import RotatingFileHandler
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler
from telegram.ext import Application as TelegramBot
from telegram.error import BadRequest, TimedOut, NetworkError, InvalidToken
import discord
from discord.ext.commands import Bot as DiscordBot
from discord.errors import LoginFailure
import helpers
import commands
import events
import chat
import settings

TELEGRAM_TOKEN_PATH = os.path.join("Data", "telegram_token.txt")
DISCORD_TOKEN_PATH = os.path.join("Data", "discord_token.txt")

async def init_logging():
    # Configure log formatting
    log_formatter = logging.Formatter(f"---------------------\n%(asctime)s - {commands.VERSION_NUMBER} - %(name)s - %(levelname)s - %(message)s")

    # Create a rotating log handler - this ensures that the log is
    log_handler = RotatingFileHandler(commands.LOGGING_FILE_PATH, mode='a', maxBytes=1024*1024, backupCount=1, encoding=None, delay=True)
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.ERROR)

    app_log = logging.getLogger("root")
    app_log.setLevel(logging.WARNING)
    app_log.addHandler(log_handler)

async def register_commands(bot: TelegramBot | DiscordBot):
    # List of all commands, add commands here to register them.
    # The first item in each tuple is the name of the command, and the second is
    # the function that will be tied to that command
    command_list = [
        ("sound", commands.sound_command),
        ("soundlist", commands.soundlist_command),
        ("random", commands.randomsound_command),
        ("playcount", commands.playcount_command),
        ("topsounds", commands.topsounds_command),
        ("botsounds", commands.botsounds_command),
        ("newsounds", commands.newsounds_command),
        ("addalias", commands.addalias_command),
        ("delalias", commands.delalias_command),
        ("getalias", commands.getalias_command),
        ("search", commands.search_command),
        ("statroll", commands.statroll_command),
        ("roll", commands.roll_command),
        ("pressf", commands.pressf_command),
        ("wisdom", commands.wisdom_command),
        ("help", commands.help_command),
        ("chat", commands.chat_command),
        ("test", commands.test_command),
        ("lobotomize", commands.lobotomize_command),
        ("memory", commands.memory_command),
        ("logs", commands.logs_command),
        ("vcsound", commands.vcsound_command),
        ("vcrandom", commands.vcrandom_command),
        ("vcstop", commands.vcstop_command),
        ("vcjoin", commands.vcjoin_command),
        ("vcleave", commands.vcleave_command),
        ("vcstream", commands.vcstream_command),
        ("getconfig", commands.getconfig_command),
        ("setconfig", commands.setconfig_command),
        ("configlist", commands.configlist_command),
        ("restart", commands.restart_command),
        ("system", commands.system_command),
        ("terminal", commands.terminal_command),
        ("version", commands.version_command),
        ("crash", commands.crash_command)
    ]

    if isinstance(bot, TelegramBot):
        for command in command_list:
            bot.add_handler(CommandHandler(command[0], telegram_handler(command[1])))
        bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), events.handle_message))

    elif isinstance(bot, DiscordBot):
        for command in command_list:
            discord_handler(bot, command[0], command[1])

        events.apply_events(bot)

    else:
        raise NotImplementedError

async def create_run_telegram_bot(telegram_token: str):
    # Create telegram bot object
    telegram_bot = ApplicationBuilder().token(telegram_token).build()
    await telegram_bot.initialize()
    await telegram_bot.start()

    # Register all commands to the telegram bot
    await register_commands(telegram_bot)

    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling(drop_pending_updates=True)

async def create_run_discord_bot(discord_token: str):
    # Set intents for discord bot
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    # Create discord bot object
    discord_bot = DiscordBot(command_prefix='/', intents=intents, help_command=None)

    # Register all commands to the discord bot
    await register_commands(discord_bot)
    await discord_bot.start(discord_token)

async def main():
    print(f"Starting script {commands.VERSION_NUMBER} at {datetime.now()}")
    config = settings.Config()

    # Initialize logging
    if config.main.uselogging:
        await init_logging()

    # Retrieve telegram bot token from file
    try:
        with open(TELEGRAM_TOKEN_PATH, encoding='utf-8') as f:
            telegram_token = f.readline().strip()
    except FileNotFoundError:
        telegram_token = None

    # Retrieve discord bot token from file
    try:
        with open(DISCORD_TOKEN_PATH, encoding='utf-8') as f:
            discord_token = f.readline().strip()
    except FileNotFoundError:
        discord_token = None

    # Attempt to run Telgram bot
    if config.main.runtelegram:
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

    # Attempt to run Discord bot
    if config.main.rundiscord:
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

def discord_handler(bot, command_name: str, command):
    # This function creates command handlers for the discord bot.
    # Provide this function with a bot, a command name, and a command function,
    # and it will create a wrapper for that command function and tie it to the
    # bot. This wrapper automatically handles the bot's response to the command
    # and writes it to memory if necessary
    @bot.command(name=command_name)
    async def wrapper_function(context):
        command_response: commands.CommandResponse = await command(context)

        try:
            if isinstance(command_response, commands.SoundResponse):
                await context.send(file=discord.File(command_response.file_path))

            elif isinstance(command_response, commands.FileResponse):
                await context.send(content=command_response.bot_message, file=discord.File(command_response.file_path))
                if command_response.temp:
                    os.remove(command_response.file_path)

            elif command_response.send_to_chat:
                await context.send(command_response.bot_message)

        except discord.errors.HTTPException:
            pass

        # Add the command and its response to memory if necessary
        if command_response.record_to_memory:
            user_prompt = chat.generate_user_prompt(command_response.user_message, context)
            chat.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

    return wrapper_function

def telegram_handler(command):
    # This function creates command handlers for the telegram bot.
    # Provide this function with a command function and it will create a wrapper
    # for that command function and return it. This wrapper automatically handles
    # the bot's response to the command and writes it to memory if necessary
    async def wrapper_function(update, context):
        # Telegram doesn't allow you to make "private" bots, meaning anyone can add your bot to their chat
        # and use up your CPU time. This check prevents the bot from responding to commands unless it comes
        # from a whitelisted chat
        if not helpers.is_whitelisted(context, update):
            print("rejected", update.message.chat.id, datetime.now())
            return

        command_response: commands.CommandResponse = await command(context, update=update)

        if isinstance(command_response, commands.SoundResponse):
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=command_response.file_path)

        elif isinstance(command_response, commands.FileResponse):
            await context.bot.send_document(chat_id=update.effective_chat.id, document=command_response.file_path)
            if command_response.temp:
                os.remove(command_response.file_path)

        elif command_response.send_to_chat:
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=command_response.bot_message)

            except (BadRequest, TimedOut, NetworkError):
                error_response = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=error_response)

        # Add the command and its response to memory if necessary
        if command_response.record_to_memory:
            user_prompt = chat.generate_user_prompt(command_response.user_message, context, update)
            chat.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

    return wrapper_function

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.exceptions.CancelledError, RuntimeError):
        print('Exiting...')
