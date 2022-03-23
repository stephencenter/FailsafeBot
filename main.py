import sound_player
import dice_roller
import message_replier
import logging
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Basic commands
def help_command(update, context):
    help_string = """\
Look upon my works, ye mighty, and despair:
/sound
/soundlist
/newsounds
/topsounds
/botsounds
/playcount
/roll
/statroll
/pressf"""
    context.bot.send_message(chat_id=update.effective_chat.id, text=help_string)
     
def pressf_command(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="F")

# Main method
def main():
    with open("token.txt") as f:
        token_string = f.readline().strip()
        
    updater = Updater(token=token_string, use_context=True)

    # Add handlers
    handler_list = [
        CommandHandler("sound", sound_player.sound_command), 
        CommandHandler("soundlist", sound_player.soundlist_command),
        CommandHandler("playcount", sound_player.playcount_command),
        CommandHandler("topsounds", sound_player.topsounds_command),
        CommandHandler("botsounds", sound_player.botsounds_command),
        CommandHandler("newsounds", sound_player.newsounds_command),
        CommandHandler("alias", sound_player.alias_command),
        CommandHandler("delalias", sound_player.delalias_command),
        CommandHandler("statroll", dice_roller.statroll_command), 
        CommandHandler("roll", dice_roller.roll_command),
        CommandHandler("pressf", pressf_command),
        CommandHandler("help", help_command),
        MessageHandler(Filters.text & (~Filters.command), message_replier.handle_message)
    ]

    for handler in handler_list:
        updater.dispatcher.add_handler(handler)
    
    updater.start_polling()
    updater.idle()
    
if __name__ == "__main__":
    main()