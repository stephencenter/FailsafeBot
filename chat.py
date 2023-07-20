import openai

async def chat_command(update, context):
    if not context.args:
        return
    
    with open("openai_key.txt") as f:
        openai.api_key = f.readline().strip()

    with open("ai_prompt.txt") as f:
        instructions = ''.join(f.readlines())

    messages = [{"role": "system", "content": instructions}]
    
    user_msg = ' '.join(context.args)
    sender = update.message.from_user["first_name"]

    prompt = f'{sender} just sent you the following message in the group chat: "{user_msg}". How do you respond?'

    messages.append({"role": "user", "content": prompt},)

    try:
        chat = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)

    except openai.error.ServiceUnavailableError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="*beep-boop* CONNECTION TIMED OUT *beep-boop*")
        return

    response = chat.choices[0].message.content

    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    #messages.append({"role": "assistant", "content": reply})
