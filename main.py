import sound_player
import dice_roller
import message_replier
import markov
import logging
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Basic commands
async def help_command(update, context):
    help_string = """\
Look upon my works, ye mighty, and despair:
/sound
/soundlist
/search
/random
/newsounds
/roll
/pressf
/wisdom"""
#/statroll
#/topsounds
#/botsounds
#/playcount

    await context.bot.send_message(chat_id=update.effective_chat.id, text=help_string)
     
async def pressf_command(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="F")

# Main method
def main():
    with open("token.txt") as f:
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
        CommandHandler("wisdom", markov.wisdom_command),
        CommandHandler("help", help_command),
        MessageHandler(filters.TEXT & (~filters.COMMAND), message_replier.handle_message)
    ]

    for handler in handler_list:
        application.add_handler(handler)
    
    application.run_polling()
    
if __name__ == "__main__":
    main()