import asyncio
from collections import defaultdict

from loguru import logger
from tqdm import tqdm
from unidecode import UnidecodeError, unidecode

import common


def fix_unicode(text: str) -> str:
    try:
        text = unidecode(text, errors='strict')
    except UnidecodeError:
        return ''
    return text


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
            continue

        if token.startswith(pair[0]) and not token.endswith(pair[1]):
            token = token[1:]

        if token.endswith(pair[1]) and not token.startswith(pair[0]):
            token = token[:-1]

    return token


async def load_chat_logs() -> list[str]:
    message_list: list[str] = []
    for file in common.PATH_MARKOV_INPUT.iterdir():
        logger.info(f"Processing {file}...")

        chat_data = await common.try_read_json(file, {})

        for message in tqdm(chat_data["messages"]):
            if "from" not in message:
                continue

            for entity in message["text_entities"]:
                text = entity["text"].strip()
                text = fix_unicode(text)

                if not text:
                    continue

                message_list.append(text)

    return message_list


def build_markov_chain(message_list: list[str]) -> dict[str, dict[str, float]]:
    markov_chain: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(int))
    null_token = "NULL_TOKEN"

    logger.info("Creating markov chain...")
    for message in tqdm(message_list):
        token_list = [clean_token(token) for token in message.split()]

        if not token_list:
            continue

        markov_chain[null_token][token_list[0]] += 1

        for index, current_token in enumerate(token_list):
            if index + 1 < len(token_list):
                next_token = token_list[index + 1]
            else:
                next_token = null_token

            markov_chain[current_token][next_token] += 1

    markov_chain = dict(sorted(markov_chain.items(), key=lambda item: sum(item[1].values()), reverse=True))

    for key in markov_chain:
        markov_chain[key] = dict(sorted(markov_chain[key].items(), key=lambda item: item[1], reverse=True))
        key_total = sum(markov_chain[key].values())
        for subkey in markov_chain[key]:
            markov_chain[key][subkey] /= key_total

    return markov_chain


async def main() -> None:
    chat_data = await load_chat_logs()
    markov_chain = build_markov_chain(chat_data)
    await common.write_json_to_file(common.PATH_MARKOV_CHAIN, markov_chain)
    logger.info(f"Markov chain written to file at '{common.PATH_MARKOV_CHAIN}'")


asyncio.run(main())
