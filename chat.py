import numpy as np
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

import common
import settings
from common import ChatCommand

OPENAI_KEY_PATH = "Data/openai_key.txt"
ELEVENLABS_KEY_PATH = "Data/eleven_key.txt"
GPT_PROMPT_PATH = "Data/gpt_prompt.txt"
MARKOV_PATH = "Data/markov_chain.json"
MEMORY_PATH = "Data/openai_memory.json"
PREPEND_PATH = "Data/prepend_message.txt"

def generate_markov_text() -> str:
    # Markov-powered Text Generation Command
    config = settings.Config()
    if config.main.minmarkov > config.main.maxmarkov:
        raise ValueError("Markov minimum length cannot be greater than maximum length (config issue)")

    markov_chain = common.try_read_json(MARKOV_PATH, {})

    if not markov_chain:
        return "No markov chain data was found!"

    null_token = "NULL_TOKEN"
    chosen_tokens = []
    while True:
        if not chosen_tokens:
            prev_token = null_token
        else:
            prev_token = chosen_tokens[-1]

        new_token = np.random.choice(list(markov_chain[prev_token].keys()), 1, p=list(markov_chain[prev_token].values()))[0]

        if new_token == null_token:
            if len(chosen_tokens) < config.main.minmarkov:
                chosen_tokens = []
                continue
            break

        chosen_tokens.append(new_token)
        if len(chosen_tokens) >= config.main.maxmarkov:
            break

    output_message = ' '.join(chosen_tokens)
    output_message = output_message[0].upper() + output_message[1:]
    return output_message

def get_gpt_response(chat_command: ChatCommand) -> str:
    config = settings.Config()

    # Load and set the OpenAI API key
    with open(OPENAI_KEY_PATH, encoding='utf-8') as f:
        openai_api_key = f.readline().strip()

    openai_client = OpenAI(api_key=openai_api_key)

    # Load the system prompt
    with open(GPT_PROMPT_PATH, encoding='utf-8') as f:
        system_prompt = ''.join(f.readlines())

    prepend_message = ''
    try:
        with open(PREPEND_PATH, encoding='utf-8') as f:
            prepend_message = ''.join(f.readlines())
    except FileNotFoundError:
        pass

    # Load the current conversation so far
    loaded_memory: list[ChatCompletionMessageParam] = load_memory()

    # Place the system prompt before the loaded memory to instruct the AI how to act
    messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt}]

    # Place an assistant message after the system prompt but before the loaded memory
    # This is useful specifically with fine-tuned models to set the tone for the bot's responses
    if prepend_message:
        messages.append({"role": "assistant", "content": prepend_message})

    messages += loaded_memory

    user_prompt = chat_command.get_user_prompt()
    messages.append({"role": "user", "content": user_prompt})

    gpt_completion= openai_client.chat.completions.create(
        messages=messages,
        model=config.main.gptmodel,
        temperature=config.main.gpttemp,
        max_completion_tokens=config.main.gptmaxtokens
    )

    response = gpt_completion.choices[0].message.content

    if response is None:
        return ''

    # Remove quotation marks from the message if GPT decided to use them
    if response.startswith('"') and response.endswith('"'):
        response = response[1:-1]

    return response

def load_memory() -> list[ChatCompletionMessageParam]:
    # Load the AI's memory (if it exists)
    config = settings.Config()

    if config.main.usememory:
        return common.try_read_json(MEMORY_PATH, [])

    return []

def append_to_memory(user_prompt: str = '', bot_prompt: str = '') -> None:
    config = settings.Config()

    if not config.main.usememory:
        return

    memory = load_memory()

    if user_prompt:
        memory.append({"role": "user", "content": user_prompt})

    if bot_prompt:
        memory.append({"role": "assistant", "content": bot_prompt})

    # The AI's memory has a size limit to keep API usage low, and to keep it from veering off track too much
    if (size := len(memory)) > config.main.memorysize:
        memory = memory[size - config.main.memorysize:]

    # Write the AI's memory to a file so it can be retrieved later
    common.write_json_to_file(MEMORY_PATH, memory)
