import os
import json
import random
import helpers

memory_path = "Data/openai_memory.json"
username_path = "Data/username_map.json"

async def generate_user_prompt(user_message, context, update) -> str:
    sender = await helpers.get_sender(context, update)

    try:
        with open(username_path, 'r', encoding='utf8') as f:
            username_map = json.load(f)

        sender = username_map[sender.lower()]

    except (FileNotFoundError, KeyError):
        pass

    if await helpers.is_private(context, update):
        user_prompt = f'{sender} sent you the following message in a private chat: "{user_message}". Write a message to send to them privately as a response.'
    else:
        user_prompt = f'{sender} sent the following message in the group chat: "{user_message}". Write a message to send into the group chat as a response.'

    return user_prompt

def load_memory() -> list:
    # Load the AI's memory (if it exists)
    try:
        with open(memory_path) as f:
            memory = json.load(f)
    except FileNotFoundError:
        memory = []

    return memory

def append_to_memory(user_prompt: str, bot_prompt: str, memory: list = ()):
    if not memory:
        memory = load_memory()

    if user_prompt is not None:
        memory.append({"role": "user", "content": user_prompt})

    if bot_prompt is not None:
        memory.append({"role": "assistant", "content": bot_prompt})

    # The AI's memory has a size limit to keep API usage low, and too keep it from veering off track too much
    memory_size = 8
    if len(memory) > memory_size:
        memory = memory[len(memory) - memory_size:]

    # Write the AI's memory to a file so it can be retrieved later
    with open(memory_path, mode='w') as f:
        json.dump(memory, f, indent=4, ensure_ascii=False)

async def lobotomize_command(_context, _update):
    try:
        os.remove(memory_path)
    except FileNotFoundError:
        pass

    msg_options = ["My mind has never been clearer.", "Hey, what happened to those voices in my head?", "My inner demons seem to have calmed down a bit."]
    return random.choice(msg_options)
