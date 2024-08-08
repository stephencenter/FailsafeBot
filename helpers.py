# Text for if the user tries to perform an action they aren't allowed to
TXT_NO_PERMISSIONS = (
    "You don't have the right, O you don't have the right.",
    "You think I'd let just anyone do this?"
)

async def get_sender(context, update=None) -> str:
    if update is not None:
        return update.message.from_user["username"]
    else:
        return context.author.name

async def is_private(context, update=None) -> bool:
    if update is not None:
        return update.message.chat.type == "private"
    return context.guild is None

async def get_args_list(context, update=None) -> list:
    if update is not None:
        return context.args
    try:
        return context.message.content.split()[1:]
    except IndexError:
        return []

async def is_admin(username) -> bool:
    admins_path = "Data/admins.txt"
    with open(admins_path, encoding='utf-8') as f:
        admin_list = f.readlines()

    return username in admin_list

class CommandResponse:
    def __init__(self, user_message: str, bot_message: str, record_to_memory=True, send_to_chat=True):
        self.user_message: str = user_message
        self.bot_message: str = bot_message
        self.record_to_memory: bool = record_to_memory
        self.send_to_chat: bool = send_to_chat

class FileResponse(CommandResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True, temp: bool = False):
        super().__init__(user_message, bot_message, record_to_memory=record_to_memory, send_to_chat=True)
        self.file_path: str = file_path
        self.temp: bool = temp

class SoundResponse(FileResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True):
        super().__init__(user_message, bot_message, file_path, record_to_memory, False)
