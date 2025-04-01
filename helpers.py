import json
import settings

TELEGRAM_WHITELIST_PATH = "Data/tg_whitelist.txt"
ADMINS_PATH = "Data/admins.txt"
USERNAME_MAP_PATH = "Data/username_map.json"

def get_sender(context, update=None, map_name=False) -> str:
    # Returns the username of the user that sent the command or message
    if update is not None:
        username = update.message.from_user.username
    else:
        username = context.author.name

    if map_name:
        return map_username(username)

    return username

def get_sender_id(context, update=None) -> str:
    # Returns the user ID of the user that sent the command or message
    if update is not None:
        user_id = str(update.message.from_user.id)
    else:
        user_id = str(context.author.id)

    return user_id

def is_private(context, update=None) -> bool:
    # Returns whether the command was called in a private chat or a group chat
    if update is not None:
        return update.message.chat.type == "private"

    return context.guild is None

def get_args_list(context, update=None) -> list[str]:
    # Returns the list of arguments provided with the command
    # e.g. /test a b c -> ['a', 'b', 'c']
    if update is not None:
        return context.args
    try:
        return context.message.content.split()[1:]
    except IndexError:
        return []

def get_args_string(context, update=None) -> str:
    # Returns the arguments provided with the command as a string
    # e.g. /test a b c -> 'a b c'
    if update is not None:
        return ' '.join(context.args)
    try:
        return ' '.join(context.message.content.split()[1:])
    except IndexError:
        return ''

def is_admin(context, update=None) -> bool:
    # Returns whether the message sender is on the bot's admin list
    if not settings.Config().main.requireadmin:
        return True

    user_id = get_sender_id(context, update)

    with open(ADMINS_PATH, encoding='utf-8') as f:
        admin_list = [x.strip() for x in f.readlines()]

    return user_id in admin_list

def is_whitelisted(context, update) -> bool:
    # Returns whether the chat is on the bot's whitelist (telegram only)
    if not settings.Config().main.usewhitelist:
        return True

    chat_id = str(update.message.chat.id)

    with open(TELEGRAM_WHITELIST_PATH, encoding='utf-8') as f:
        whitelist = [x.strip() for x in f.readlines()]

    return chat_id in whitelist

def map_username(username) -> str:
    try:
        with open(USERNAME_MAP_PATH, 'r', encoding='utf-8') as f:
            username_map = json.load(f)
    except FileNotFoundError:
        return username

    try:
        corrected_name = username_map[username.lower()]
    except KeyError:
        return username

    return corrected_name
