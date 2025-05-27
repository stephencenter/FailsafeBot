"""Chat utilities.

This module contains constants, classes, and functions used by Chat commands like
/chat, /say, and /wisdom.
"""

import collections
import datetime
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
import openai
from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core.api_error import ApiError as ElevenLabsApiError
from loguru import logger

import common
from common import UserCommand

MAX_GPT_ATTEMPTS = 3
NULL_TOKEN = "NULL_TOKEN"


async def get_gpt_response(user_command: UserCommand) -> str:
    config = await common.Config.load()

    # Load and set the OpenAI API key
    openai_api_key = await common.try_read_single_line(common.PATH_OPENAI_KEY, None)
    openai_client = openai.AsyncOpenAI(api_key=openai_api_key)

    # This is the message list we will send to OpenAI to get a response for
    messages: list[dict[str, str]] = []

    # Load and place the system prompt before the loaded memory to instruct the AI how to act
    system_prompt = await common.try_read_lines_str(common.PATH_GPT_PROMPT, None)
    if system_prompt is not None:
        messages.append({"role": "system", "content": system_prompt})

    # Place an assistant message after the system prompt but before the loaded memory
    # This is useful specifically with fine-tuned models to set the tone for the bot's responses
    prepend_message = await common.try_read_lines_str(common.PATH_GPT_PREPEND, None)
    if prepend_message is not None:
        messages.append({"role": "assistant", "content": prepend_message})

    # Load the current conversation so far and add it to the end of the message history
    loaded_memory: list[dict[str, str]] = await common.get_recall_chat_memory()
    messages += loaded_memory

    user_prompt = await user_command.get_user_prompt()

    if user_prompt is not None:
        messages.append({"role": "user", "content": user_prompt})

    attempt_counter = 0
    re_attempt_text = "Failed to get GPT response, trying again..."
    while attempt_counter < MAX_GPT_ATTEMPTS:
        gpt_completion = await openai_client.chat.completions.create(
            messages=messages,  # type: ignore
            model=config.chat.gptmodel,
            temperature=config.chat.gpttemp,
            max_completion_tokens=config.chat.gptmaxtokens,
        )

        response = gpt_completion.choices[0].message.content

        # We try to get a response from OpenAI up to MAX_GPT_ATTEMPTS times
        # If the response is None, blank, or is blank after removing quotes, we don't accept and try again
        # up to MAX_GPT_ATTEMPTS times
        if response is not None:
            # Remove quotation marks from the message if GPT decided to use them
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1]

            if response:
                return response

        logger.warning(re_attempt_text)
        attempt_counter += 1
        continue

    error_msg = f"Failed to get a response from OpenAI Chat Completion API within {MAX_GPT_ATTEMPTS} attempts"
    logger.error(error_msg)
    return common.TXT_BZZZT_ERROR


async def get_most_recent_bot_message() -> str | None:
    memory_list: list[dict[str, str]] = await common.get_full_chat_memory()

    for memory in memory_list[::-1]:
        if memory["role"] == "assistant":
            return memory["content"]

    return None


async def get_elevenlabs_response(input_text: str, *, save_to_file: bool = False) -> Path | AsyncIterator[bytes]:
    # Get elevenlabs key from file
    elevenlabs_key = await common.try_read_single_line(common.PATH_ELEVENLABS_KEY, None)
    if elevenlabs_key is None:
        error_message = "Couldn't retrieve elevenlabs key!"
        raise ValueError(error_message)

    config = await common.Config.load()
    elevenlabs_client = AsyncElevenLabs(api_key=elevenlabs_key)

    # Get text-to-speech response from elevenlabs
    audio_stream = elevenlabs_client.text_to_speech.convert(
        text=input_text,
        voice_id=config.chat.sayvoiceid,
        model_id=config.chat.saymodelid,
    )

    # Save sound to temp file
    if save_to_file:
        temp_name = f"{datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d_%H-%M-%S")}.mp3"
        temp_path = common.PATH_TEMP_FOLDER / temp_name
        await common.write_bytes_to_file(temp_path, audio_stream)
        return temp_path

    return audio_stream


async def cap_elevenlabs_prompt(text_prompt: str) -> str:
    config = await common.Config.load()
    hard_cap = config.chat.sayhardcap
    soft_cap = config.chat.saysoftcap

    # Hard cap cuts off the text abruptly, to keep costs down (longer strings = more elevenlabs credits)
    if len(text_prompt) > hard_cap:
        text_prompt = text_prompt[:hard_cap]

    # Soft cap cuts off the text gently, only at spaces or certain punctuation marks
    break_chars = {' ', '.', '?', '!', ','}
    for index, char in enumerate(text_prompt[soft_cap:]):
        if char in break_chars:
            text_prompt = text_prompt[:soft_cap + index]
            break

    return text_prompt


async def handle_elevenlabs_error(error: ElevenLabsApiError) -> str:
    config = await common.Config.load()

    error_map = {
        'max_character_limit_exceeded':
            "Text input has too many characters for ElevenLabs text-to-speech (max is ~10k)",

        'invalid_api_key':
            f"ElevenLabs API Key in '{common.PATH_ELEVENLABS_KEY}' is invalid!",

        'voice_not_found':
            f"ElevenLabs Voice ID '{config.chat.sayvoiceid}' is invalid!",

        'model_not_found':
            f"ElevenLabs Model ID '{config.chat.saymodelid}' is invalid!",

        'quota_exceeded':
            "ElevenLabs account is out of credits!",

        'free_users_not_allowed':
            f"Voice with ID '{config.chat.sayvoiceid}' needs an active ElevenLabs subscription to use.",
    }

    status = error.body['detail']['status']

    try:
        return error_map[status]

    except KeyError:
        logger.error(error)
        return "There was an issue with the ElevenLabs API, try again later."


async def generate_markov_text(markov_chain: dict[str, dict[str, float]]) -> str:
    # Markov-powered Text Generation Command
    config = await common.Config.load()
    if config.chat.minmarkov > config.chat.maxmarkov:
        error_message = "Markov minimum length cannot be greater than maximum length (config issue)"
        raise ValueError(error_message)

    chosen_tokens: list[str] = []
    rng = np.random.default_rng()
    while True:
        if not chosen_tokens:
            prev_token: str = NULL_TOKEN
        else:
            prev_token: str = chosen_tokens[-1]

        new_token = rng.choice(list(markov_chain[prev_token].keys()), 1, p=list(markov_chain[prev_token].values()))
        new_token = new_token[0]

        if new_token == NULL_TOKEN:
            if len(chosen_tokens) < config.chat.minmarkov:
                chosen_tokens = []
                continue
            break

        chosen_tokens.append(new_token)
        if len(chosen_tokens) >= config.chat.maxmarkov:
            break

    output_message = ' '.join(chosen_tokens)
    return output_message[0].upper() + output_message[1:]


def clean_token(token: str) -> str:
    # Remove paired characters like () and {} if they don't have a match on the other end of the token
    pair_list = [
        ('(', ')'),
        ('[', ']'),
        ('"', '"'),
        ('{', '}'),
    ]

    for pair in pair_list:
        if token.startswith(":") or token.endswith(":"):
            # Don't remove unpaired characters from emoticons like :-) and (-:
            continue

        if token.startswith(pair[0]) and not token.endswith(pair[1]):
            token = token[1:]

        if token.endswith(pair[1]) and not token.startswith(pair[0]):
            token = token[:-1]

    return token


def get_chat_data_files() -> list[Path]:
    try:
        return [path for path in common.PATH_MARKOV_INPUT.iterdir() if path.suffix == ".json"]
    except FileNotFoundError:
        return []


async def load_message_list(chat_files: list[Path]) -> list[str]:
    # Load messages from list of .json files for use in building Markov chain.
    message_list: list[str] = []
    for file in chat_files:
        logger.info(f"Processing {file}...")

        chat_data = await common.try_read_json(file, {})
        if "messages" not in chat_data:
            continue

        for message in chat_data["messages"]:
            if "from" not in message or "text_entities" not in message:
                continue

            for entity in message["text_entities"]:
                if "text" not in entity:
                    continue

                text = entity["text"].strip()
                text = common.convert_to_ascii(text)

                if not text:
                    continue

                message_list.append(text)

    return message_list


def build_markov_chain(message_list: list[str]) -> dict[str, dict[str, float]]:
    markov_chain: dict[str, dict[str, float]] = collections.defaultdict(lambda: collections.defaultdict(int))

    logger.info("Creating markov chain...")
    for message in message_list:
        token_list = [clean_token(token) for token in message.split()]

        if not token_list:
            continue

        markov_chain[NULL_TOKEN][token_list[0]] += 1

        for index, current_token in enumerate(token_list):
            if index + 1 < len(token_list):
                next_token = token_list[index + 1]
            else:
                next_token = NULL_TOKEN

            markov_chain[current_token][next_token] += 1

    markov_chain = dict(sorted(markov_chain.items(), key=lambda item: sum(item[1].values()), reverse=True))

    for key in markov_chain:
        markov_chain[key] = dict(sorted(markov_chain[key].items(), key=lambda item: item[1], reverse=True))
        key_total = sum(markov_chain[key].values())
        for subkey in markov_chain[key]:
            markov_chain[key][subkey] /= key_total

    return markov_chain
