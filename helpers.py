async def get_sender(context, update):
    if update is not None:
        return update.message.from_user["username"]
    else:
        return context.author.display_name

async def is_private(context, update):
    if update is not None:
        return update.message.chat.type == "private"
    return context.guild is None

async def get_args_list(context, update):
    if update is not None:
        return context.args
    try:
        return context.message.content.split()[1:]
    except IndexError:
        return []
