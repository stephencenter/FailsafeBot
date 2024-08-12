# Text for if the user tries to perform an action they aren't allowed to
TXT_NO_PERMISSIONS = (
    "You don't have the right, O you don't have the right.",
    "You think I'd let just anyone do this?"
)

async def get_sender(context, update=None) -> str:
    # Returns the username of the user that send the command
    if update is not None:
        return update.message.from_user["username"]
    return context.author.name

async def is_private(context, update=None) -> bool:
    # Returns whether the command was called in a private chat or a group chat
    if update is not None:
        return update.message.chat.type == "private"
    return context.guild is None

async def get_args_list(context, update=None) -> list:
    # Returns the list of arguments provided with the command
    # e.g. /test a b c -> ['a', 'b', 'c']
    if update is not None:
        return context.args
    try:
        return context.message.content.split()[1:]
    except IndexError:
        return []

async def is_admin(context, update=None) -> bool:
    # Returns whether the message sender is on the bot's admin list
    username = await get_sender(context, update)

    admins_path = "Data/admins.txt"
    with open(admins_path, encoding='utf-8') as f:
        admin_list = [x.strip() for x in f.readlines()]

    return username in admin_list

class CommandResponse:
    def __init__(self, user_message: str, bot_message: str, record_to_memory=True, send_to_chat=True):
        self.user_message: str = user_message
        self.bot_message: str = bot_message
        self.record_to_memory: bool = record_to_memory  # Whether user_message and bot_message should be recorded to memory
        self.send_to_chat: bool = send_to_chat  # Whether bot_message should be printed in chat

class FileResponse(CommandResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True, temp: bool = False):
        super().__init__(user_message, bot_message, record_to_memory=record_to_memory, send_to_chat=True)
        self.file_path: str = file_path  # The path of the file to send
        self.temp: bool = temp  # Whether the file should be deleted after being sent

class SoundResponse(FileResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True):
        super().__init__(user_message, bot_message, file_path, record_to_memory, False)

class NoResponse(CommandResponse):
    def __init__(self):
        super().__init__('', '', record_to_memory=False, send_to_chat=False)
