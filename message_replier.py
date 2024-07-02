import random
import memory

responses_path = "Data/response_list.txt"

async def handle_message(update, context):
    try:
        message_text = update.message.text.lower()

    except AttributeError:
        return

    response = None
    if "girthbot" in message_text or "girth bot" in message_text:
        response = await girthbot_reply(update, context)

    elif "monkey" in message_text:
        response = await monkey_reply(update, context)

    user_prompt = memory.generate_user_prompt(message_text, update)

    if response is not None:
        memory.append_to_memory(user_prompt, response)

async def girthbot_reply(update, context):
    try:
        with open(responses_path, encoding="utf-8") as f:
            response_list = f.readlines()

    except FileNotFoundError:
        return

    response_list = [line for line in response_list if not line.isspace() and not line.startswith("#")]

    chosen_response = random.choice(response_list)
    if chosen_response.startswith('f"') or chosen_response.startswith("f'"):
        chosen_response = eval(chosen_response)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=chosen_response)
    return chosen_response

async def monkey_reply(update, context):
    monkey_sound = "Sounds/monkey.mp3"
    await context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(monkey_sound, 'rb'))
    return "AAAAAHHHHH-EEEEE-AAAAAHHHHH!"
