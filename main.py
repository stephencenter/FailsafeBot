import os
import shutil
import logging
import asyncio
from logging.handlers import RotatingFileHandler
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler
from telegram.error import BadRequest
import discord
from discord.ext import commands
import sound_player
import dice_roller
import message_replier
import chat
import memory
import helpers
import voice_chat

TELEGRAM_TOKEN_PATH = os.path.join("Data", "telegram_token.txt")
DISCORD_TOKEN_PATH = os.path.join("Data", "discord_token.txt")
LOGGING_DIR_PATH = os.path.join("Data", "logging")
LOGGING_FILE_PATH = os.path.join(LOGGING_DIR_PATH, "log.txt")
ADMIN_LIST_PATH = "Data/admins.txt"

async def init_logging():
    # Configure logger
    log_formatter = logging.Formatter("---------------------\n%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_handler = RotatingFileHandler(LOGGING_FILE_PATH, mode='a', maxBytes=1024*1024, backupCount=2, encoding=None, delay=False)
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.WARNING)

    app_log = logging.getLogger("root")
    app_log.setLevel(logging.WARNING)
    app_log.addHandler(log_handler)

async def init_bots():
    # Retrieve Telegram token from file
    with open(TELEGRAM_TOKEN_PATH, encoding='utf-8') as f:
        telegram_token = f.readline().strip()

    telegram_bot = ApplicationBuilder().token(telegram_token).build()

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    await telegram_bot.initialize()
    await telegram_bot.start()

    discord_bot = commands.Bot(command_prefix='/', intents=intents)
    await add_commands(telegram_bot, discord_bot)

    if telegram_bot.updater is not None:
        await telegram_bot.updater.start_polling()
        print("Telegram bot started")

    async with discord_bot:
        with open(DISCORD_TOKEN_PATH, encoding='utf-8') as f:
            discord_token = f.readline().strip()
        print("Discord bot started")
        await discord_bot.start(discord_token)

    await telegram_bot.stop()
    await telegram_bot.shutdown()

async def add_commands(telegram_bot, discord_bot):
    # Create and add handlers
    command_list = [
        ("sound", sound_player.sound_command),
        ("soundlist", sound_player.soundlist_command),
        ("random", sound_player.randomsound_command),
        ("playcount", sound_player.playcount_command),
        ("topsounds", sound_player.topsounds_command),
        ("botsounds", sound_player.botsounds_command),
        ("newsounds", sound_player.newsounds_command),
        ("addalias", sound_player.addalias_command),
        ("delalias", sound_player.delalias_command),
        ("getalias", sound_player.getalias_command),
        ("search", sound_player.search_command),
        ("statroll", dice_roller.statroll_command),
        ("roll", dice_roller.roll_command),
        ("pressf", chat.pressf_command),
        ("wisdom", chat.wisdom_command),
        # ("help", chat.help_command),
        ("chat", chat.chat_command),
        ("say", chat.say_command),
        ("lobotomize", memory.lobotomize_command),
        ("logs", logs_command),
        ("vcsound", voice_chat.vcsound_command),
        ("vcrandom", voice_chat.vcrandom_command),
        ("vcstop", voice_chat.vcstop_command),
        ("vcjoin", voice_chat.vcjoin_command),
        ("vcleave", voice_chat.vcleave_command),
        ("vcstream", voice_chat.vcstream_command)
    ]

    for command in command_list:
        telegram_bot.add_handler(CommandHandler(command[0], telegram_handler(command[1])))
        discord_handler(discord_bot, command[0], command[1])

    telegram_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_replier.handle_message))

async def main():
    await init_logging()
    await init_bots()

# Basic commands
def discord_handler(bot, command_name, command):
    @bot.command(name=command_name)
    async def wrapper_function(context):
        command_response: helpers.CommandResponse = await command(context)

        try:
            if isinstance(command_response, helpers.SoundResponse):
                await context.send(file=discord.File(command_response.file_path))

            elif isinstance(command_response, helpers.FileResponse):
                await context.send(content=command_response.bot_message, file=discord.File(command_response.file_path))
                if command_response.temp:
                    os.remove(command_response.file_path)

            elif command_response.send_to_chat:
                await context.send(command_response.bot_message)

        except discord.errors.HTTPException:
            pass

        if command_response.record_to_memory:
            user_prompt = await memory.generate_user_prompt(command_response.user_message, context)
            await memory.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

    return wrapper_function

def telegram_handler(command):
    async def wrapper_function(update, context):
        command_response: helpers.CommandResponse = await command(context, update=update)

        if isinstance(command_response, helpers.SoundResponse):
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=command_response.file_path)

        elif isinstance(command_response, helpers.FileResponse):
            await context.bot.send_document(chat_id=update.effective_chat.id, document=command_response.file_path)
            if command_response.temp:
                os.remove(command_response.file_path)

        elif command_response.send_to_chat:
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=command_response.bot_message)

            except BadRequest:
                error_response = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"
                await context.bot.send_document(chat_id=update.effective_chat.id, text=error_response)

        if command_response.record_to_memory:
            user_prompt = await memory.generate_user_prompt(command_response.user_message, context, update)
            await memory.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

    return wrapper_function

async def logs_command(context, update=None) -> helpers.CommandResponse:
    output_path = os.path.join(LOGGING_DIR_PATH, "error_log.txt")

    # Try to remove the temp error log if it already exists
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

    # Concatenate the rolling error log files together into one file
    with open(output_path, 'wb') as wfd:
        for file in os.listdir(LOGGING_DIR_PATH)[::-1]:
            file_path = os.path.join(LOGGING_DIR_PATH, file)

            if os.path.samefile(file_path, output_path):
                continue

            with open(file_path, 'rb') as fd:
                shutil.copyfileobj(fd, wfd)

    return helpers.FileResponse("Can you send me your error log?", "Sure, here you go.", output_path)

if __name__ == "__main__":
    asyncio.run(main())
