import json
import typing
import settings

VERSION_NUMBER = 'v1.0.10'
TELEGRAM_WHITELIST_PATH = "Data/tg_whitelist.txt"
ADMINS_PATH = "Data/admins.txt"
USERNAME_MAP_PATH = "Data/username_map.json"
LOGGING_FILE_PATH = "Data/logging/log.txt"
RESPONSES_PATH = "Data/response_list.txt"

T = typing.TypeVar('T')

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
    admin_list = try_read_lines(ADMINS_PATH, [])

    return user_id in admin_list

def is_whitelisted(context, update) -> bool:
    # Returns whether the chat is on the bot's whitelist (telegram only)
    if not settings.Config().main.usewhitelist:
        return True

    chat_id = str(update.message.chat.id)
    whitelist = try_read_lines(TELEGRAM_WHITELIST_PATH, [])

    return chat_id in whitelist

def map_username(username) -> str:
    username_map = try_read_json(USERNAME_MAP_PATH, dict())

    try:
        corrected_name = username_map[username.lower()]
    except KeyError:
        return username

    return corrected_name

def try_read_json(path: str, default: T) -> T:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default

def try_read_lines(path: str, default) -> list:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return [x.strip() for x in f.readlines()]
    except OSError:
        return default

def write_json_to_file(path: str, data) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def write_lines_to_file(path: str, lines) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(f"{x}\n" for x in lines)
