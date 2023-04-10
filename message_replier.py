import random

async def handle_message(update, context):
    try:
        message_text = " ".join(update.message.text.lower().split())
        
    except AttributeError:
        return
    
    if "girthbot" in message_text or "girth bot" in message_text:
        await girthbot_reply(update, context)
        
    elif "monkey" in message_text:
        await monkey_reply(update, context)
    
async def girthbot_reply(update, context):
    try:
        with open("response_list.txt", encoding="utf-8") as f:
            response_list = f.readlines()
            
    except FileNotFoundError:
        return
    
    response_list = [line for line in response_list if not line.isspace() and not line.startswith("#")]
    
    chosen_response = random.choice(response_list)
    if chosen_response.startswith('f"') or chosen_response.startswith("f'"):
        chosen_response = eval(chosen_response)
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=chosen_response)
    
async def monkey_reply(update, context):
    monkey_sound = "Sounds/monkey.mp3"
    context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(monkey_sound, 'rb'))