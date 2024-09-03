import os
import logging
import asyncio
from datetime import datetime
from logging.handlers import RotatingFileHandler
import telegram.ext
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler
from telegram.error import BadRequest, TimedOut, NetworkError
import discord
from discord.ext import commands as discord_commands
import helpers
import commands
import events
import chat

TELEGRAM_TOKEN_PATH = os.path.join("Data", "telegram_token.txt")
DISCORD_TOKEN_PATH = os.path.join("Data", "discord_token.txt")
VERSION_NUMBER = 'v1.0.2'

async def init_logging():
    # Configure log formatting
    log_formatter = logging.Formatter("---------------------\n%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Create a rotating log handler - this ensures that the log is
    log_handler = RotatingFileHandler(commands.LOGGING_FILE_PATH, mode='a', maxBytes=1024*1024, backupCount=1, encoding=None, delay=True)
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.ERROR)

    app_log = logging.getLogger("root")
    app_log.setLevel(logging.WARNING)
    app_log.addHandler(log_handler)

async def create_bots() -> tuple[telegram.ext.Application, discord_commands.Bot]:
    # Retrieve telegram bot token from file
    with open(TELEGRAM_TOKEN_PATH, encoding='utf-8') as f:
        telegram_token = f.readline().strip()

    # Create telegram bot object
    telegram_bot = ApplicationBuilder().token(telegram_token).build()

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    # Create discord bot object
    discord_bot = discord_commands.Bot(command_prefix='/', intents=intents, help_command=None)

    # Add a command to this list to register it
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
        ("terminal", commands.terminal_command)
    ]

    # Iterate through the command list and set the 1st element as the command name and the 2nd
    # as the command function for each command
    for command in command_list:
        telegram_bot.add_handler(CommandHandler(command[0], telegram_handler(command[1])))
        discord_handler(discord_bot, command[0], command[1])

    telegram_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), events.handle_message))
    events.apply_events(discord_bot)

    return telegram_bot, discord_bot

async def run_telegram_bot(telegram_bot):
    # Start the telegram bot and begin listening for commands
    await telegram_bot.start()
    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling(drop_pending_updates=True)

async def run_discord_bot(discord_bot):
    # Retrieve discord bot token from file
    with open(DISCORD_TOKEN_PATH, encoding='utf-8') as f:
        discord_token = f.readline().strip()

    # Start the discord bot and begin listening for commands
    await discord_bot.start(discord_token)

async def main():
    print(f"Starting script {VERSION_NUMBER} at {datetime.now()}")

    # Initialize logging and set up the bots
    await init_logging()
    telegram_bot, discord_bot = await create_bots()

    # Run the bots simultaneously
    async with telegram_bot:
        print("Telegram bot started")
        await run_telegram_bot(telegram_bot)

        async with discord_bot:
            print("Discord bot started")
            await run_discord_bot(discord_bot)

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
