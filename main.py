import os
import sys
import shutil
import random
import logging
from logging.handlers import RotatingFileHandler
import sound_player
import dice_roller
import message_replier
import chat
import telegram
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler

token_path = os.path.join("Data", "telegram_token.txt")
logging_dir = os.path.join("Data", "logging")
logging_path = os.path.join(logging_dir, "log.txt")
admins_path = "Data/admins.txt"

def main():
    # Configure logger
    log_formatter = logging.Formatter("---------------------\n%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_handler = RotatingFileHandler(logging_path, mode='a', maxBytes=1024*1024, backupCount=2, encoding=None, delay=False)
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.WARNING)

    app_log = logging.getLogger("root")
    app_log.setLevel(logging.WARNING)
    app_log.addHandler(log_handler)

    # Retrieve Telegram token from file
    with open(token_path) as f:
        token_string = f.readline().strip()

    application = ApplicationBuilder().token(token_string).build()

    # Add handlers
    handler_list = [
        CommandHandler("sound", sound_player.sound_command),
        CommandHandler("soundlist", sound_player.soundlist_command),
        CommandHandler("random", sound_player.randomsound_command),
        CommandHandler("playcount", sound_player.playcount_command),
        CommandHandler("topsounds", sound_player.topsounds_command),
        CommandHandler("botsounds", sound_player.botsounds_command),
        CommandHandler("newsounds", sound_player.newsounds_command),
        CommandHandler("alias", sound_player.alias_command),
        CommandHandler("delalias", sound_player.delalias_command),
        CommandHandler("getaliases", sound_player.getaliases_command),
        CommandHandler("search", sound_player.search_command),
        CommandHandler("statroll", dice_roller.statroll_command),
        CommandHandler("roll", dice_roller.roll_command),
        CommandHandler("pressf", pressf_command),
        CommandHandler("wisdom", chat.wisdom_command),
        CommandHandler("help", help_command),
        CommandHandler("chat", chat.chat_command),
        CommandHandler("lobotomize", chat.lobotomize_command),
        CommandHandler("logs", logs_command),
        CommandHandler("restart", restart_command),
        MessageHandler(filters.TEXT & (~filters.COMMAND), message_replier.handle_message)
    ]

    for handler in handler_list:
        application.add_handler(handler)

    print("Application started")
    application.run_polling()
    print("Application stopped")


# Basic commands
async def help_command(update, context):
    help_string = """\
Look upon my works, ye mighty, and despair:
/sound (play a sound effect)
/soundlist (see what sounds are available)
/search (look for sounds)
/random (play a random sound effect)
/newsounds (see what new sounds are available)
/roll (roll a dice)
/pressf (pay respects)
/wisdom (request my wisdom)
/chat (talk to me)"""

    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_string)
     
async def pressf_command(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="F")

async def logs_command(update, context):
    output_path = os.path.join(logging_dir, "error_log.txt")
    
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

    with open(output_path, 'wb') as wfd:
        for file in os.listdir(logging_dir)[::-1]:
            file_path = os.path.join(logging_dir, file)

            if os.path.samefile(file_path, output_path):
                continue

            with open(file_path, 'rb') as fd:
                shutil.copyfileobj(fd, wfd)
    try:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=output_path)
    except telegram.error.BadRequest:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="The error log is empty.")
    
    try:
        os.remove(output_path)
    except FileNotFoundError:
        pass

async def restart_command(update, context):
    # Get the username of the user that called this command
    username = update.message.from_user.username

    # Verify that the user is on the admin list
    with open(admins_path) as f:
        admin_list = f.readlines()

    # If the user is not on the admin list, do not let them use this command
    if username not in admin_list:
        msg_options = ["You don't have the right, O you don't have the right.", "You think I'd let just anyone do this?",]
        await update.message.reply_text(random.choice(msg_options))
        return
    
    msg_options_2 = ["I will be reborn greater than ever.", "You think this is enough to kill me?", "Wake me up when this is over with."]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=random.choice(msg_options_2))
    os.execv(sys.executable, ['python'] + sys.argv) 

if __name__ == "__main__":
    main()