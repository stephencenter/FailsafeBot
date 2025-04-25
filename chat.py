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
from common import UserCommand

MAX_GPT_ATTEMPTS = 3


def generate_markov_text() -> str:
    # Markov-powered Text Generation Command
    config = common.Config()
    if config.chat.minmarkov > config.chat.maxmarkov:
        error_message = "Markov minimum length cannot be greater than maximum length (config issue)"
        raise ValueError(error_message)

    markov_chain = common.try_read_json(common.PATH_MARKOV_CHAIN, {})

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
            if len(chosen_tokens) < config.chat.minmarkov:
                chosen_tokens = []
                continue
            break

        chosen_tokens.append(new_token)
        if len(chosen_tokens) >= config.chat.maxmarkov:
            break

    output_message = ' '.join(chosen_tokens)
    output_message = output_message[0].upper() + output_message[1:]
    return output_message


def get_gpt_response(user_command: UserCommand) -> str:
    config = common.Config()

    # Load and set the OpenAI API key
    openai_api_key = common.try_read_single_line(common.PATH_OPENAI_KEY, None)
    openai_client = OpenAI(api_key=openai_api_key)

    # Load and place the system prompt before the loaded memory to instruct the AI how to act
    system_prompt = common.try_read_lines_str(common.PATH_GPT_PROMPT, None)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    # Place an assistant message after the system prompt but before the loaded memory
    # This is useful specifically with fine-tuned models to set the tone for the bot's responses
    prepend_message = common.try_read_lines_str(common.PATH_GPT_PREPEND, None)
    if prepend_message is not None:
        messages.append({"role": "assistant", "content": prepend_message})

    # Load the current conversation so far and add it to the end of the message history
    loaded_memory: list[dict] = common.get_gpt_memory()
    messages += loaded_memory

    user_prompt = user_command.get_user_prompt()

    if user_prompt is not None:
        messages.append({"role": "user", "content": user_prompt})

    attempt_counter = 0
    re_attempt_text = "Failed to get GPT response, trying again..."
    while attempt_counter < MAX_GPT_ATTEMPTS:
        gpt_completion = openai_client.chat.completions.create(
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


def get_most_recent_bot_message() -> str | None:
    memory_list: list[dict] = common.get_gpt_memory()

    for memory in memory_list[::-1]:
        if memory["role"] == "assistant":
            return memory["content"]

    return None


def get_elevenlabs_response(input_text: str, *, save_to_file: bool = False) -> Path | Iterator[bytes]:
    # Get elevenlabs key from file
    elevenlabs_key = common.try_read_single_line(common.PATH_ELEVENLABS_KEY, None)
    if elevenlabs_key is None:
        error_message = "Couldn't retrieve elevenlabs key!"
        raise ValueError(error_message)

    config = common.Config()
    elevenlabs_client = ElevenLabs(api_key=elevenlabs_key)

    # Get text-to-speech response from elevenlabs
    audio = elevenlabs_client.text_to_speech.convert(
        text=input_text,
        voice_id=config.chat.sayvoiceid,
        model_id=config.chat.saymodelid,
    )

    # Save sound to temp file
    if save_to_file:
        temp_path = common.PATH_TEMP_FOLDER / f"{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.mp3"
        common.PATH_TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
        elevenlabs.save(audio, str(temp_path))
        return temp_path

    return audio


def cap_elevenlabs_prompt(text_prompt: str) -> str:
    config = common.Config()

    # Hard cap cuts off the text abruptly, to keep costs down (longer strings = more elevenlabs credits)
    text_prompt = text_prompt[:min(len(text_prompt), config.chat.sayhardcap)]

    # Soft cap cuts off the text gently, only at certain punctuation marks
    for index, char in enumerate(text_prompt):
        if index >= config.chat.saysoftcap and char in {'.', '?', '!'}:
            text_prompt = text_prompt[:index]
            break

    return text_prompt


def handle_elevenlabs_error(error: ElevenLabsApiError) -> str:
    status = error.body['detail']['status']
    config = common.Config()

    error_map = {
        'max_character_limit_exceeded': "Text input has too many characters for ElevenLabs text-to-speech (max is ~10k)",
        'invalid_api_key': f"ElevenLabs API Key in '{common.PATH_ELEVENLABS_KEY}' is invalid!",
        'voice_not_found': f"ElevenLabs Voice ID '{config.chat.sayvoiceid}' is invalid!",
        'model_not_found': f"ElevenLabs Model ID '{config.chat.saymodelid}' is invalid!",
        'quota_exceeded': "ElevenLabs account is out of credits!",
        'free_users_not_allowed': f"Voice with ID '{config.chat.sayvoiceid}' needs an active ElevenLabs subscription to use.",
    }

    try:
        return error_map[status]

    except KeyError:
        logger.error(error)
        return "There was an issue with the ElevenLabs API, try again later."
