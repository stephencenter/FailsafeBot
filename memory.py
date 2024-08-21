import os
import json
import random
import helpers
import settings

MEMORY_PATH = "Data/openai_memory.json"

async def generate_user_prompt(user_message: str, context, update=None) -> str:
    sender = await helpers.get_sender(context, update)

    if await helpers.is_private(context, update):
        user_prompt = f'{sender} sent the following message in a private chat: "{user_message}". Write a message to send as a response.'
    else:
        user_prompt = f'{sender} sent the following message in a group chat: "{user_message}". Write a message to send as a response.'

    return user_prompt

async def load_memory() -> list:
    # Load the AI's memory (if it exists)
    try:
        with open(MEMORY_PATH, encoding='utf-8') as f:
            memory = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        memory = []

    return memory

async def append_to_memory(user_prompt: str, bot_prompt: str) -> None:
    memory = await load_memory()

    if user_prompt is not None:
        memory.append({"role": "user", "content": user_prompt})

    if bot_prompt is not None:
        memory.append({"role": "assistant", "content": bot_prompt})

    config = settings.get_config()
    # The AI's memory has a size limit to keep API usage low, and too keep it from veering off track too much
    if len(memory) > config.main.memorysize:
        memory = memory[len(memory) - config.main.memorysize:]

    # Write the AI's memory to a file so it can be retrieved later
    with open(MEMORY_PATH, mode='w', encoding='utf-8') as f:
        json.dump(memory, f, indent=4)

# This command clears the bot's memory
async def lobotomize_command(context, update=None) -> helpers.CommandResponse:
    try:
        os.remove(MEMORY_PATH)
    except FileNotFoundError:
        pass

    msg_options = ["My mind has never been clearer.", "Hey, what happened to those voices in my head?", "My inner demons seem to have calmed down a bit."]
    return helpers.CommandResponse('', random.choice(msg_options), record_to_memory=False)
