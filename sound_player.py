import os
import json
import random
import memory

sounds_path = "Sounds"
alias_path = "Data/sound_aliases.json"
playcounts_path = "Data/playcounts.json"
admins_path = "Data/admins.txt"

# This message is sent if the user doesn't provide a sound name
txt_sound_not_provided = [
    "I'm afraid my mindreader unit has been malfunctioning lately, what sound did you want?",
    "Use your words please.",
    "I don't have any sounds without a name unfortunately."
]

# This message is sent if the sound the user requests doesn't exist
txt_sound_not_found = [
    "Are you insane, do you have any idea how dangerous a sound with that name would be?",
    "I wouldn't be caught dead with a sound like that on my list.",
    "No dice. Stephen probably forgot to upload it, what a fool."
]

# This message is sent if the user tries to perform an action they aren't allowed to
txt_no_permissions = [
    "You don't have the right, O you don't have the right.",
    "You think I'd let just anyone do this?"
]

def get_sound_dict() -> dict:
    # If any .mp3 files are in the main directory, move them to the Sounds directory
    for file in os.listdir():
        if file.endswith(".mp3"):
            os.rename(file, f"{sounds_path}/{file}")

    # Create the sound dictionary. The keys will be the names of each sound, and the values will be the
    # path to that sound's file
    sound_dict = dict()
    for file in os.listdir(sounds_path):
        if file.endswith(".mp3"):
            sound_dict[file[:-4].lower()] = os.path.join(sounds_path, file)

    return sound_dict

def get_alias_dict() -> dict:
    # Load a dictionary where the keys are aliases, and the values are the
    # sounds those aliases correspond to
    with open(alias_path) as f:
        return json.load(f)

def get_playcount_dict() -> dict:
    # Retrieve the sound and alias dictionaries
    sound_dict = get_sound_dict()
    alias_dict = get_alias_dict()

    playcount_dict = {x: 0 for x in sound_dict}

    try:
        with open(playcounts_path) as f:
            playcount_dict = json.load(f)

    # If loading the stored dictionary fails, return the blank playcount dictionary
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return playcount_dict

    # This variable makes note of whether a correction was made to the playcounts dictionary
    changed = False

    # Ensure that all sounds are in the playcount dictionary
    for sound_name in sound_dict:
        if sound_name not in playcount_dict:
            playcount_dict[sound_name] = 0
            changed = True

    # Ensure that the playcounts of aliases are not being tracked separately.
    # This could occur, for example, if a sound's name and alias are swapped
    for alias in alias_dict:
        if alias in playcount_dict:
            sound_name = alias_dict[alias]
            playcount_dict[sound_name] += playcount_dict[alias]
            del playcount_dict[alias]
            changed = True

    # Ensure that there aren't any nonexistent sounds in the playcount dictionary
    for sound_name in playcount_dict.copy():
        if sound_name not in sound_dict:
            del playcount_dict[sound_name]
            changed = True

    # If the playcount dictionary had to be corrected, then we write the corrected
    # dictionary to a file
    if changed:
        with open(playcounts_path, 'w') as f:
            json.dump(playcount_dict, f, indent=4)

    return playcount_dict

def get_aliases(sound_name, sound_dict, alias_dict) -> list:
    alias_list = []

    if sound_name not in sound_dict:
        real_name = alias_dict[sound_name]
        alias_list.append(real_name)
    else:
        real_name = sound_name

    for alias in alias_dict:
        if alias_dict[alias] == real_name and alias != sound_name:
            alias_list.append(alias)

    return alias_list

def update_playcount(sound_name):
    play_counts = get_playcount_dict()

    try:
        play_counts[sound_name] += 1
    except KeyError:
        play_counts[sound_name] = 1

    with open(playcounts_path, 'w') as f:
        json.dump(play_counts, f, indent=4)

async def sound_command(update, context):
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()

    # Alert the user if they forgot to provide a sound name
    if not context.args or context.args[0].isspace():
        await update.message.reply_text(random.choice(txt_sound_not_provided))
        return

    # Parse the arguments the user provided for the sound name
    sound_name = context.args[0].lower()

    # Sounds can have aliases, which are alternative names you can call
    # them with. If an alias is provided, we determine what sound the
    # alias corresponds to and play thatS
    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    # Alert the user if the sound they requested does not exist
    if sound_name not in sound_dict:
        await update.message.reply_text(random.choice(txt_sound_not_found))
        return

    user_prompt = memory.generate_user_prompt(f"Can you play the {sound_name} sound for me?", update)

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        response = "You know, I'm just not feeling it right now."
        await update.message.reply_text(response)
        memory.append_to_memory(user_prompt, response)
        return

    # If the sound was requested in a non-private chat, then we'll update the
    # playcount for this sound
    if update.message.chat.type != "private":
        update_playcount(sound_name)

    # Load the sound and send it to the user
    with open(sound_dict[sound_name], 'rb') as sound_file:
        await context.bot.send_voice(chat_id=update.effective_chat.id, voice=sound_file)
        memory.append_to_memory(user_prompt, "Sure, here you go.")

async def randomsound_command(update, context):
    user_prompt = memory.generate_user_prompt("Can you play a random sound for me?", update)

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        response = "You know, I'm just not feeling it right now."
        await update.message.reply_text(response)
        memory.append_to_memory(user_prompt, response)
        return

    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()
    sound_name = random.choice(list(sound_dict.keys()))

    # If the sound was requested in a group chat, then we update the playcount for this sound
    if update.message.chat.type != "private":
        update_playcount(sound_name)

    memory.append_to_memory(user_prompt, f"Sure, here you go. The sound I chose is called '{sound_name}'.")

    # Load the sound and send it to the user
    with open(sound_dict[sound_name], 'rb') as f:
        await context.bot.send_voice(chat_id=update.effective_chat.id, voice=f)

async def soundlist_command(update, context):
    sorted_list = sorted(get_sound_dict().keys())
    list_string = ', '.join(sorted_list)
    count = len(sorted_list)

    user_prompt = memory.generate_user_prompt("How many sounds are available to use? Can you list them for me?", update)
    response = f"There are {count} sounds available to use. If I try to tell you want they are it makes me crash and Stephen is too lazy to fix it so you're gonna have to just guess."
    memory.append_to_memory(user_prompt, response)

    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

async def alias_command(update, context):
    # Get the username of the user that called this command
    username = update.message.from_user.username

    # Verify that the user is on the admin list
    with open(admins_path) as f:
        admin_list = f.readlines()

    # If the user is not on the admin list, do not let them use this command
    if username not in admin_list:
        await update.message.reply_text(random.choice(txt_no_permissions))
        return

    # Attempt to parse the new alias and target sound from the arguments provided
    try:
        new_alias = context.args[0]
        sound_name = context.args[1]

    except KeyError:
        await update.message.reply_text("Format is /alias [new alias] [sound name]")
        return

    # Get the list of all sounds
    sound_dict = get_sound_dict()

    if new_alias in sound_dict:
        await update.message.reply_text(f"There is already a sound called '{new_alias}'")
        return

    alias_dict = get_alias_dict()

    # Avoid redirecting existing aliases to new sounds
    if new_alias in alias_dict:
        await update.message.reply_text(f"'{new_alias}' is already an alias for '{alias_dict[new_alias]}'")
        return

    if sound_name not in sound_dict:
        try:
            sound_name = alias_dict[sound_name]

        except KeyError:
            await update.message.reply_text(random.choice(txt_sound_not_found))
            return

    alias_dict[new_alias] = sound_name

    with open(alias_path, "w") as f:
        json.dump(alias_dict, f, indent=4)

    await update.message.reply_text(f"'{new_alias}' has been added as an alias for '{sound_name}'")

async def delalias_command(update, context):
    username = update.message.from_user.username

    with open(admins_path) as f:
        admin_list = f.readlines()

    if username not in admin_list:
        await update.message.reply_text(random.choice(txt_no_permissions))
        return

    alias_to_delete = context.args[0]
    alias_dict = get_alias_dict()

    try:
        del alias_dict[alias_to_delete]

    except KeyError:
        await update.message.reply_text(f"{alias_to_delete} isn't an alias for anything.")
        return

    with open(alias_path, 'w') as f:
        json.dump(alias_dict, f, indent=4)

    await update.message.reply_text(f"{alias_to_delete} is no longer assigned to a sound.")

async def newsounds_command(update, context):
    sound_list = sorted(get_sound_dict().keys())
    playcount_dict = get_playcount_dict()
    new_sounds = [sound for sound in sound_list if playcount_dict[sound] == 0]
    new_count = len(new_sounds)
    list_string = ', '.join(new_sounds)

    if new_count == 0:
        await update.message.reply_text("There are no new sounds available.")

    elif new_count == 1:
        await update.message.reply_text(f"There is one new sound available: {list_string}")

    else:
        await update.message.reply_text(f"There are {new_count} new sounds available:\n\n{list_string}")

async def getaliases_command(update, context):
    try:
        sound_name = context.args[0].lower()
    except IndexError:
        await update.message.reply_text(random.choice(txt_sound_not_provided))
        return

    sound_dict = get_sound_dict()
    alias_dict = get_alias_dict()

    if sound_name not in sound_dict and sound_name not in alias_dict:
        await update.message.reply_text(random.choice(txt_sound_not_found))
        return

    aliases = sorted(get_aliases(sound_name, sound_dict, alias_dict))
    num_alias = len(aliases)
    join_string = "', '"
    alias_string = f"'{join_string.join(aliases)}'"

    if num_alias == 1:
        await update.message.reply_text(f"The sound '{sound_name}' has one alias: {alias_string}")

    elif num_alias > 1:
        await update.message.reply_text(f"The sound '{sound_name}' has {num_alias} aliases: {alias_string}")

    else:
        await update.message.reply_text(f"The sound '{sound_name}' has no assigned aliases")

async def search_command(update, context):
    try:
        search_string = context.args[0].lower()
    except IndexError:
        await update.message.reply_text("What sound do you want me to search for?")
        return

    sound_dict = get_sound_dict()
    alias_dict = get_alias_dict()

    filtered_list = []
    for sound_name in sound_dict:
        if search_string in sound_name:
            filtered_list.append(sound_name)
        else:
            for alias in get_aliases(sound_name, sound_dict, alias_dict):
                if search_string in alias:
                    filtered_list.append(alias)
                    break

    num_matches = len(filtered_list)
    list_string = f"\n\n{', '.join(sorted(filtered_list))}"
    if num_matches == 1:
        await update.message.reply_text(f"There is one sound matching '{search_string}': {list_string}")

    elif num_matches > 1:
        await update.message.reply_text(
            f"There are {len(filtered_list)} sounds matching '{search_string}': {list_string}")

    else:
        await update.message.reply_text(f"There are no sounds matching '{search_string}'")

async def playcount_command(update, context):
    if not context.args or context.args[0].isspace():
        await update.message.reply_text(random.choice(txt_sound_not_provided))
        return

    sound_name = context.args[0].lower()

    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    if sound_name not in get_sound_dict():
        await update.message.reply_text(random.choice(txt_sound_not_found))
        return

    playcount = get_playcount_dict()[sound_name]
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"/sound {sound_name} has been used {playcount} times")

async def topsounds_command(update, context):
    play_counts = get_playcount_dict()
    list_size = 20
    top_sounds = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_sounds)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"The {list_size} most used sounds are:\n{message}")

async def botsounds_command(update, context):
    play_counts = get_playcount_dict()
    list_size = 20
    bot_sounds = sorted(play_counts, key=lambda x: play_counts[x])[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in bot_sounds)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text=f"The {list_size} least used sounds are:\n{message}")
