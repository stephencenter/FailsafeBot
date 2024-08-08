import os
import json
from tqdm import tqdm

INPUT_PATH = 'Data/chat_data/'
OUTPUT_PATH = 'Data/markov_chain.json'

def fix_apple(text: str) -> str:
    # Apple devices have an awful feature called 'smart punctuation' that we need to account for
    text = text.replace('‘', "'")
    text = text.replace('’', "'")
    text = text.replace('“', '"')
    text = text.replace('”', '"')
    text = text.replace('…', '...')
    text = text.replace('—', '-')
    text = text.replace('é', 'e')

    return text

def clean_token(token: str) -> str:
    pair_list = [
        ('(', ')'),
        ('[', ']'),
        ('"', '"'),
        ('{', '}')
    ]

    for pair in pair_list:
        if token.startswith(":") or token.endswith(":"):
            continue

        if token.startswith(pair[0]) and not token.endswith(pair[1]):
            token = token[1:]

        if token.endswith(pair[1]) and not token.startswith(pair[0]):
            token = token[:-1]

    return token

def load_chat_logs() -> list[str]:
    message_list = []
    for file in os.listdir(INPUT_PATH):
        print(f"Processing {file}...")

        with open(os.path.join(INPUT_PATH, file), 'r', encoding='utf-8') as f:
            chat_data = json.load(f)

        for message in tqdm(chat_data["messages"]):
            if "from" not in message or message["from"] == "Girth Bot":
                continue

            for entity in message["text_entities"]:
                text = entity["text"].strip()

                if not text:
                    continue

                if "in the middle of our goblin" in text.lower():
                    continue

                if any(x in text.lower() for x in ["https", "www.", ".com"]):
                    continue

                if text.startswith("/"):
                    continue

                if "\n" in text:
                    continue

                # Thanks apple
                text = fix_apple(text)

                if not text.isascii():
                    continue

                message_list.append(text)

    return message_list

def build_markov_chain(message_list):
    markov_chain = {}
    null_token = "NULL_TOKEN"

    print("Creating markov chain...")
    for message in tqdm(message_list):
        token_list = [clean_token(token) for token in message.split()]

        for index, token in enumerate(token_list):
            if index == 0:
                if null_token in markov_chain:
                    if token in markov_chain[null_token]:
                        markov_chain[null_token][token] += 1
                    else:
                        markov_chain[null_token][token] = 1
                else:
                    markov_chain[null_token] = {}
                    markov_chain[null_token][token] = 1

            if index + 1 == len(token_list):
                if token in markov_chain:
                    if null_token in markov_chain[token]:
                        markov_chain[token][null_token] += 1
                    else:
                        markov_chain[token][null_token] = 1
                else:
                    markov_chain[token] = {}
                    markov_chain[token][null_token] = 1

            else:
                next_token = token_list[index + 1]
                if token in markov_chain:
                    if next_token in markov_chain[token]:
                        markov_chain[token][next_token] += 1
                    else:
                        markov_chain[token][next_token] = 1
                else:
                    markov_chain[token] = {}
                    markov_chain[token][next_token] = 1

    markov_chain = dict(sorted(markov_chain.items(), key=lambda item: sum(item[1].values()), reverse=True))

    for key in markov_chain:
        markov_chain[key] = dict(sorted(markov_chain[key].items(), key=lambda item: item[1], reverse=True))
        key_total = sum(markov_chain[key].values())
        for subkey in markov_chain[key]:
            markov_chain[key][subkey] = markov_chain[key][subkey]/key_total

    return markov_chain

def main():
    chat_data = load_chat_logs()
    markov_chain = build_markov_chain(chat_data)

    with open(OUTPUT_PATH, 'w', encoding='utf8') as f:
        json.dump(markov_chain, f, indent=4, ensure_ascii=False)

    print(f"Markov chain written to file at '{OUTPUT_PATH}'")
    input()

main()
