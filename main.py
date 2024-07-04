import os
import shutil
import logging
import asyncio
from logging.handlers import RotatingFileHandler
import telegram
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler
import discord
from discord.ext import commands
import sound_player
import dice_roller
import message_replier
import chat
import memory

telegram_token_path = os.path.join("Data", "telegram_token.txt")
discord_token_path = os.path.join("Data", "discord_token.txt")
logging_dir = os.path.join("Data", "logging")
logging_path = os.path.join(logging_dir, "log.txt")
admins_path = "Data/admins.txt"

async def init_logging():
    # Configure logger
    log_formatter = logging.Formatter("---------------------\n%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_handler = RotatingFileHandler(logging_path, mode='a', maxBytes=1024*1024, backupCount=2, encoding=None, delay=False)
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.WARNING)

    app_log = logging.getLogger("root")
    app_log.setLevel(logging.WARNING)
    app_log.addHandler(log_handler)

async def init_bots():
    # Retrieve Telegram token from file
    with open(telegram_token_path) as f:
        telegram_token = f.readline().strip()

    telegram_bot = ApplicationBuilder().token(telegram_token).build()

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    with open(discord_token_path) as f:
        discord_token = f.readline().strip()

    await telegram_bot.initialize()
    await telegram_bot.start()
    discord_bot = commands.Bot(command_prefix='/', intents=intents)
    await add_commands(telegram_bot, discord_bot)

    await telegram_bot.updater.start_polling()
    async with discord_bot:
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
        ("alias", sound_player.alias_command),
        ("delalias", sound_player.delalias_command),
        ("getaliases", sound_player.getaliases_command),
        ("search", sound_player.search_command),
        ("statroll", dice_roller.statroll_command),
        ("roll", dice_roller.roll_command),
        ("pressf", chat.pressf_command),
        ("wisdom", chat.wisdom_command),
        # ("help", chat.help_command),
        ("chat", chat.chat_command),
        ("say", chat.say_command),
        ("lobotomize", memory.lobotomize_command),
        ("logs", logs_command)
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
        response = await command(context)
        try:
            await context.send(response)
        except discord.errors.HTTPException:
            pass

def telegram_handler(command):
    async def wrapper_function(update, context):
        response = await command(context, update=update)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    return wrapper_function

async def logs_command(context, update=None):
    output_path = os.path.join(logging_dir, "error_log.txt")

    # Try to remove the temp error log if it already exists
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

    # Concatenate the rolling error log files together into one file
    with open(output_path, 'wb') as wfd:
        for file in os.listdir(logging_dir)[::-1]:
            file_path = os.path.join(logging_dir, file)

            if os.path.samefile(file_path, output_path):
                continue

            with open(file_path, 'rb') as fd:
                shutil.copyfileobj(fd, wfd)

    # Try to send the resulting log file
    try:
        response = "Sure, here you go."
        await context.bot.send_document(chat_id=update.effective_chat.id, document=output_path)

    except telegram.error.BadRequest:
        response = "My error log is empty."
        return response

    user_prompt = await memory.generate_user_prompt("Can you send me your error log?", context, update)
    memory.append_to_memory(user_prompt, response)

    # Delete the temp error log
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

if __name__ == "__main__":
    asyncio.run(main())
