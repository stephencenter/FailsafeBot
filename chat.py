import os
import json
import random
import numpy
import openai

apikey_path = "Data/openai_key.txt"
prompt_path = "Data/gpt_prompt.txt"
memory_path = "Data/openai_memory.json"
admins_path = "Data/admins.txt"
markov_path = "Data/markov_chain.json"

with open(markov_path, 'r', encoding='utf8') as f:
    markov_chain = json.load(f)

# GPT-powered Chat Command
def load_memory() -> list:
    # Load the AI's memory (if it exists)
    try:
        with open(memory_path) as f:
            memory = json.load(f)
    except FileNotFoundError:
        memory = []
    
    return memory

def save_memory(memory : list):
    # The AI's memory has a size limit to avoid it veering off track too much, and to keep API usage low
    memory_size = 8
    if len(memory) > memory_size:
        memory = memory[len(memory) - memory_size:]

    # Write the AI's memory to a file so it can be retrieved later
    with open(memory_path, mode='w') as f:
        json.dump(memory, f, indent=4, ensure_ascii=False)

def get_ai_response(messages : list) -> str:
    try:
        chat = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)

    except openai.error.ServiceUnavailableError:
        return None

    response = chat.choices[0].message.content
    
    # Remove quotation marks from the message if GPT decided to use them
    if response.startswith('"') and response.endswith('"'):
        response = response[1:-1]

    return response

async def chat_command(update, context):
    if not context.args:
        return
    
    # Load and set the OpenAI API key
    with open(apikey_path) as f:
        openai.api_key = f.readline().strip()

    # Load the system prompt
    with open(prompt_path) as f:
        system_prompt = ''.join(f.readlines())

    memory = load_memory()

    # Place the system prompt before the loaded memory to instruct the AI how to act
    messages = [{"role": "system", "content": system_prompt}] + memory

    # Create a prompt for GPT that includes the user's name and message, as well as whether it was a private message or not
    sender = update.message.from_user["username"]
    user_msg = ' '.join(context.args)

    if update.message.chat.type == "private":
        user_prompt = f'{sender} just sent you following message in a private chat: "{user_msg}". Write a message that you will send to them privately as a response.'

    else:
         user_prompt = f'{sender} just sent the following message in the group chat: "{user_msg}". Write a message that you will send into the group chat as a response.'
    
    messages.append({"role": "user", "content": user_prompt})
    memory.append({"role": "user", "content": user_prompt})

    # Have GPT generate a response to the user prompt
    response = get_ai_response(messages)

    if response is None:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="*beep-boop* CONNECTION TIMED OUT *beep-boop*")
        return

    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    # Add the AI's response to its memory
    memory.append({"role": "assistant", "content": response})
    save_memory(memory)

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

# Markov-powered Text Generation Command
def generate_markov_text(min_length=2, max_length=255):
    null_token = "NULL_TOKEN"

    chosen_tokens = []
    while True:
        if not chosen_tokens:
            prev_token = null_token
        else:
            prev_token = chosen_tokens[-1]

        new_token = numpy.random.choice(list(markov_chain[prev_token].keys()), 1, p=list(markov_chain[prev_token].values()))[0]

        if new_token == null_token:
            if len(chosen_tokens) < min_length:
                chosen_tokens = []
                continue
            break

        chosen_tokens.append(new_token)
        if len(chosen_tokens) >= max_length:
            break

    output_message = ' '.join(chosen_tokens)
    output_message = output_message[0].upper() + output_message[1:]
    return output_message
    
async def wisdom_command(update, context):
    message_text = generate_markov_text()

    sender = update.message.from_user["username"]
    memory = load_memory()
    memory.append({"role": "user", "content": f'{sender} has sent you the following message: "O, wise and powerful girthbot, please grant me your wisdom!" Write them a wise message in response.'})
    memory.append({"role": "assistant", "content": message_text})
    save_memory(memory)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text)