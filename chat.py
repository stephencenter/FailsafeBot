import json
import numpy
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
import settings
import helpers

OPENAI_KEY_PATH = "Data/openai_key.txt"
ELEVENLABS_KEY_PATH = "Data/eleven_key.txt"
GPT_PROMPT_PATH = "Data/gpt_prompt.txt"
ADMINS_PATH = "Data/admins.txt"
MARKOV_PATH = "Data/markov_chain.json"
MEMORY_PATH = "Data/openai_memory.json"

with open(MARKOV_PATH, 'r', encoding='utf8') as markov:
    markov_chain = json.load(markov)

# Markov-powered Text Generation Command
def generate_markov_text(min_length=2, max_length=255) -> str:
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

def get_gpt_response(user_message) -> str:
    # Load and set the OpenAI API key
    with open(OPENAI_KEY_PATH, encoding='utf-8') as f:
        openai_api_key = f.readline().strip()

    openai_client = OpenAI(api_key=openai_api_key)

    # Load the system prompt
    with open(GPT_PROMPT_PATH, encoding='utf-8') as f:
        system_prompt = ''.join(f.readlines())

    # Load the current conversation so far
    loaded_memory: list = load_memory()

    # Place the system prompt before the loaded memory to instruct the AI how to act
    messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt}]
    messages += loaded_memory
    messages.append({"role": "user", "content": user_message})

    config = settings.get_config()
    gpt_creation = openai_client.chat.completions.create(messages=messages, model=config.main.gptmodel)
    response = gpt_creation.choices[0].message.content

    if response is None:
        return ''

    # Remove quotation marks from the message if GPT decided to use them
    if response.startswith('"') and response.endswith('"'):
        response = response[1:-1]

    return response

def generate_user_prompt(user_message: str, context, update=None) -> str:
    sender = helpers.get_sender(context, update)

    if helpers.is_private(context, update):
        user_prompt = f'{sender} sent the following message in a private chat: "{user_message}". Write a message to send as a response.'
    else:
        user_prompt = f'{sender} sent the following message in a group chat: "{user_message}". Write a message to send as a response.'

    return user_prompt

def load_memory() -> list[dict[str, str]]:
    # Load the AI's memory (if it exists)
    config = settings.get_config()

    memory = []
    if config.main.usememory:
        try:
            with open(MEMORY_PATH, encoding='utf-8') as f:
                memory = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    return memory

def append_to_memory(user_prompt=None, bot_prompt=None) -> None:
    config = settings.get_config()

    if not config.main.usememory:
        return

    memory = load_memory()

    if user_prompt is not None:
        memory.append({"role": "user", "content": user_prompt})

    if bot_prompt is not None:
        memory.append({"role": "assistant", "content": bot_prompt})

    # The AI's memory has a size limit to keep API usage low, and too keep it from veering off track too much
    if len(memory) > config.main.memorysize:
        memory = memory[len(memory) - config.main.memorysize:]

    # Write the AI's memory to a file so it can be retrieved later
    with open(MEMORY_PATH, mode='w', encoding='utf-8') as f:
        json.dump(memory, f, indent=4)
