import datetime
from collections.abc import Iterator
from pathlib import Path

import elevenlabs
import numpy as np
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError as ElevenLabsApiError
from loguru import logger
from openai import OpenAI

import common
import settings
from common import UserCommand

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

def get_gpt_response(user_command: UserCommand) -> str:
    config = settings.Config()

    # Load and set the OpenAI API key
    openai_api_key = common.try_read_single_line(OPENAI_KEY_PATH, None)
    openai_client = OpenAI(api_key=openai_api_key)

    # Load and place the system prompt before the loaded memory to instruct the AI how to act
    system_prompt = common.try_read_lines_str(GPT_PROMPT_PATH, None)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Place an assistant message after the system prompt but before the loaded memory
    # This is useful specifically with fine-tuned models to set the tone for the bot's responses
    prepend_message = common.try_read_lines_str(PREPEND_PATH, None)
    if prepend_message is not None:
        messages.append({"role": "assistant", "content": prepend_message})

    # Load the current conversation so far and add it to the end of the message history
    loaded_memory: list[dict] = load_memory()
    messages += loaded_memory

    user_prompt = user_command.get_user_prompt()
    messages.append({"role": "user", "content": user_prompt})

    gpt_completion= openai_client.chat.completions.create(
        messages=messages, # type: ignore
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

def load_memory() -> list[dict]:
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

def get_most_recent_bot_message() -> str | None:
    memory_list: list[dict] = load_memory()

    for memory in memory_list[::-1]:
        if memory["role"] == "assistant":
            return memory["content"]

    return None

def get_elevenlabs_response(input_text: str, *, save_to_file: bool = False) -> Path | Iterator[bytes]:
    # Get elevenlabs key from file
    elevenlabs_key = common.try_read_single_line(common.ELEVENLABS_KEY_PATH, None)
    if elevenlabs_key is None:
        raise ValueError("Couldn't retrieve elevenlabs key!")

    config = settings.Config()
    elevenlabs_client = ElevenLabs(api_key=elevenlabs_key)

    # Get text-to-speech response from elevenlabs
    audio = elevenlabs_client.text_to_speech.convert(
        text=input_text,
        voice_id=config.main.sayvoiceid,
        model_id=config.main.saymodelid
    )

    # Save sound to temp file
    if save_to_file:
        temp_path = Path(common.TEMP_FOLDER_PATH) / f"{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.mp3"
        Path(common.TEMP_FOLDER_PATH).mkdir(parents=True, exist_ok=True)
        elevenlabs.save(audio, str(temp_path))
        return temp_path

    return audio

def cap_elevenlabs_prompt(text_prompt: str) -> str:
    config = settings.Config()

    # Hard cap cuts off the text abruptly, to keep costs down (longer strings = more elevenlabs credits)
    text_prompt = text_prompt[:min(len(text_prompt), config.main.sayhardcap)]

    # Soft cap cuts off the text gently, only at certain punctuation marks
    for index, char in enumerate(text_prompt):
        if index >= config.main.saysoftcap and char in ('.', '?', '!'):
            text_prompt = text_prompt[:index]
            break

    return text_prompt

def handle_elevenlabs_error(error: ElevenLabsApiError) -> str:
    status = error.body['detail']['status']
    config = settings.Config()

    error_map = {
        'max_character_limit_exceeded': "Text input has too many characters for ElevenLabs text-to-speech (max is ~10k)",
        'invalid_api_key': f"ElevenLabs API Key in '{common.ELEVENLABS_KEY_PATH}' is invalid!",
        'voice_not_found': f"ElevenLabs Voice ID '{config.main.sayvoiceid}' is invalid!",
        'model_not_found': f"ElevenLabs Model ID '{config.main.saymodelid}' is invalid!",
        'quota_exceeded': "ElevenLabs account is out of credits!",
        'free_users_not_allowed': f"Voice with ID '{config.main.sayvoiceid}' needs an active ElevenLabs subscription to use."
    }

    try:
        return error_map[status]

    except KeyError:
        logger.error(error)
        return "There was an issue with the ElevenLabs API, try again later."
