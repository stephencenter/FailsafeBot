import json
import numpy

markov_path = "Data/markov_chain.json"
NULL_TOKEN = "NULL_TOKEN"

with open(markov_path, 'r', encoding='utf8') as f:
    markov_chain = json.load(f)

def generate_text(min_length=2, max_length=255):
    chosen_tokens = []
    while True:
        if not chosen_tokens:
            prev_token = NULL_TOKEN
        else:
            prev_token = chosen_tokens[-1]

        new_token = numpy.random.choice(list(markov_chain[prev_token].keys()), 1, p=list(markov_chain[prev_token].values()))[0]

        if new_token == NULL_TOKEN:
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
    message_text = generate_text()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text)