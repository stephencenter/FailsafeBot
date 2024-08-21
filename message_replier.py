import random
import memory
import settings

RESPONSES_PATH = "Data/response_list.txt"

async def handle_message(update, context):
    if update is None:
        return

    message_text = update.message.text.lower()

    config = settings.get_config()
    bot_name = config.main.botname.lower()

    response = None
    if config.main.replytomonkey and "monkey" in message_text:
        response = await monkey_reply(context, update)

    elif config.main.replytoname and (bot_name in message_text or ''.join(bot_name.split()) in message_text):
        response = await botname_reply(context, update)

    user_prompt = await memory.generate_user_prompt(message_text, context, update)

    if response is not None:
        await memory.append_to_memory(user_prompt, response)

async def botname_reply(context, update=None):
    if update is None:
        return

    try:
        with open(RESPONSES_PATH, encoding="utf-8") as f:
            response_list = f.readlines()

    except FileNotFoundError:
        return

    response_list = [line for line in response_list if not line.isspace() and not line.startswith("#")]

    chosen_response = random.choice(response_list)
    if chosen_response.startswith('f"') or chosen_response.startswith("f'"):
        chosen_response = eval(chosen_response)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=chosen_response)
    return chosen_response

async def monkey_reply(context, update=None):
    # Discworld adventure game reference
    if update is None:
        return

    await context.bot.send_voice(chat_id=update.effective_chat.id, voice="Sounds/monkey.mp3")
    return "AAAAAHHHHH-EEEEE-AAAAAHHHHH!"
