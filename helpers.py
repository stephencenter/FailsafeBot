import settings

TXT_NO_PERMISSIONS = (
    "You don't have the right, O you don't have the right.",
    "You think I'd let just anyone do this?"
)

def get_sender(context, update=None) -> str:
    # Returns the username of the user that send the command
    if update is not None:
        return update.message.from_user["username"]
    return context.author.name

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

def is_admin(context, update=None) -> bool:
    # Returns whether the message sender is on the bot's admin list
    if not settings.get_config().main.requireadmin:
        return True

    username = get_sender(context, update)

    admins_path = "Data/admins.txt"
    with open(admins_path, encoding='utf-8') as f:
        admin_list = [x.strip() for x in f.readlines()]

    return username in admin_list
