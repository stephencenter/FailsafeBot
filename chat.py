import os
import json
import random
import openai

apikey_path = "Data/openai_key.txt"
prompt_path = "Data/gpt_prompt.txt"
memory_path = "Data/openai_memory.json"
admins_path = "Data/admins.txt"

memory_size = 8

async def chat_command(update, context):
    if not context.args:
        return
    
    # Load and set the OpenAI API key
    with open(apikey_path) as f:
        openai.api_key = f.readline().strip()

    # Load the system prompt
    with open(prompt_path) as f:
        instructions = ''.join(f.readlines())

    # Load the AI's memory (if it exists)
    try:
        with open(memory_path) as f:
            memory = json.load(f)
    except FileNotFoundError:
        memory = []

    # Place the system prompt before the loaded memory to instruct the AI how to act
    messages = [{"role": "system", "content": instructions}] + memory
    sender = update.message.from_user["username"]
    user_msg = ' '.join(context.args)

    # Private chat and group chat messages get different prompts
    if update.message.chat.type == "private":
        prompt = f'{sender} just sent you following message in a private chat: "{user_msg}". Write a message that you will send to them privately as a response.'

    else:
        prompt = f'{sender} just sent the following message in the group chat: "{user_msg}". Write a message that you will send into the group chat as a response.'
    
    new_message = {"role": "user", "content": prompt}
    messages.append(new_message)
    memory.append(new_message)

    try:
        chat = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)

    except openai.error.ServiceUnavailableError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="*beep-boop* CONNECTION TIMED OUT *beep-boop*")
        return

    response = chat.choices[0].message.content
    
    # Remove quotation marks from the message if GPT decided to use them
    if response.startswith('"') and response.endswith('"'):
        response = response[1:-1]

    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    # Add the new message to the AI's memory
    memory.append({"role": "assistant", "content": response})

    # The AI's memory has a size limit to avoid it veering off track too much, and to keep API usage low
    if len(memory) > memory_size:
        memory = memory[len(memory) - memory_size:]

    with open(memory_path, mode='w') as f:
        json.dump(memory, f, indent=4, ensure_ascii=False)

async def lobotomize_command(update, context):
    # Get the username of the user that called this command
    username = update.message.from_user.username

    # Verify that the user is on the admin list
    with open(admins_path) as f:
        admin_list = f.readlines()

    # If the user is not on the admin list, do not let them use this command
    if username not in admin_list:
        await update.message.reply_text("Only trained surgeons are permitted to operate on me.")
        return
    
    try:
        os.remove(memory_path)
    except FileNotFoundError:
        pass

    msg_options = ["My mind has never been clearer.", "Hey, what happened to those voices in my head?", "My inner demons seem to have calmed down a bit."]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=random.choice(msg_options))