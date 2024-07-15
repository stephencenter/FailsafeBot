# Text for if the user tries to perform an action they aren't allowed to
txt_no_permissions = [
    "You don't have the right, O you don't have the right.",
    "You think I'd let just anyone do this?"
]

async def get_sender(context, update=None):
    if update is not None:
        return update.message.from_user["username"]
    else:
        return context.author.name

async def is_private(context, update=None):
    if update is not None:
        return update.message.chat.type == "private"
    return context.guild is None

async def get_args_list(context, update=None):
    if update is not None:
        return context.args
    try:
        return context.message.content.split()[1:]
    except IndexError:
        return []

async def is_admin(username) -> bool:
    admins_path = "Data/admins.txt"
    with open(admins_path) as f:
        admin_list = f.readlines()

    return username in admin_list

class SoundResponse:
    def __init__(self, path):
        self.path = path

class FileResponse:
    def __init__(self, path, message="", temp=False):
        self.path = path
        self.message = message
        self.temp = temp
