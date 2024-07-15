import os
import shutil
import logging
import asyncio
from logging.handlers import RotatingFileHandler
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler
import discord
from discord.ext import commands
import sound_player
import dice_roller
import message_replier
import chat
import memory
import helpers
import voice_chat

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

    await telegram_bot.initialize()
    await telegram_bot.start()

    discord_bot = commands.Bot(command_prefix='/', intents=intents)
    await add_commands(telegram_bot, discord_bot)

    await telegram_bot.updater.start_polling()
    print("Telegram bot started")
    async with discord_bot:
        with open(discord_token_path) as f:
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
        response = await command(context)
        try:
            if isinstance(response, helpers.FileResponse):
                await context.send(content=response.message, file=discord.File(response.path))
                if response.temp:
                    os.remove(response.path)
            elif isinstance(response, helpers.SoundResponse):
                await context.send(file=discord.File(response.path))
            else:
                await context.send(response)
        except discord.errors.HTTPException:
            pass

def telegram_handler(command):
    async def wrapper_function(update, context):
        response = await command(context, update=update)
        if isinstance(response, helpers.FileResponse):
            await context.bot.send_document(chat_id=update.effective_chat.id, document=response.path)

        elif isinstance(response, helpers.SoundResponse):
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(response.path, 'rb'))

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

    return helpers.FileResponse(output_path)

    # user_prompt = await memory.generate_user_prompt("Can you send me your error log?", context, update)
    # memory.append_to_memory(user_prompt, response)

if __name__ == "__main__":
    asyncio.run(main())
