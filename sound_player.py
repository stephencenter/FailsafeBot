import os
import json
import discord
from discord.ext import commands
import random
import memory
import helpers

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

async def sound_command(context, update=None):
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()

    # Alert the user if they forgot to provide a sound name
    user_message = await helpers.get_args_list(context, update)
    if not user_message or user_message[0].isspace():
        return txt_sound_not_provided

    # Parse the arguments the user provided for the sound name
    sound_name = user_message[0].lower()

    # Sounds can have aliases, which are alternative names you can call
    # them with. If an alias is provided, we determine what sound the
    # alias corresponds to and play that sound
    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    # Alert the user if the sound they requested does not exist
    if sound_name not in sound_dict:
        return random.choice(txt_sound_not_found)

    user_prompt = await memory.generate_user_prompt(f"Can you play the {sound_name} sound for me?", context, update)

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        response = "You know, I'm just not feeling it right now."
        memory.append_to_memory(user_prompt, response)
        return response

    # If the sound was requested in a non-private chat, then we'll update the
    # playcount for this sound
    if not await helpers.is_private(context, update):
        update_playcount(sound_name)

    memory.append_to_memory(user_prompt, "Sure, here you go.")

    return helpers.SoundResponse(sound_dict[sound_name])

async def randomsound_command(context, update=None):
    user_prompt = await memory.generate_user_prompt("Can you play a random sound for me?", context, update)

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        response = "You know, I'm just not feeling it right now."
        memory.append_to_memory(user_prompt, response)
        return response

    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()
    sound_name = random.choice(list(sound_dict.keys()))

    # If the sound was requested in a group chat, then we update the playcount for this sound
    if not await helpers.is_private(context, update):
        update_playcount(sound_name)

    memory.append_to_memory(user_prompt, f"Sure, here you go. The sound I chose is called '{sound_name}'.")

    return helpers.SoundResponse(sound_dict[sound_name])

async def vcsound_command(context, update=None):
    if update is not None:
        return "That's Discord only, sorry"

    if context.voice_client is None:
        return "I'm not in a voice channel!"

    chosen_sound = await sound_command(context, update)

    if isinstance(chosen_sound, helpers.SoundResponse):
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(chosen_sound.path))
        context.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)
        return

    return chosen_sound

async def vcjoin_command(context, update=None):
    if update is not None:
        return "That's Discord only, sorry"

    vc_converter = commands.VoiceChannelConverter()
    channel_name = ' '.join(await helpers.get_args_list(context))

    try:
        voice_channel = await vc_converter.convert(context, channel_name)
    except commands.errors.ChannelNotFound:
        return "Couldn't find that channel (note that channel names are case-sensitive)"

    if context.voice_client is not None:
        return await context.voice_client.move_to(voice_channel)

    await voice_channel.connect()

async def vcleave_command(context, update=None):
    if update is not None:
        return

    try:
        await context.voice_client.disconnect()
    except (AttributeError, commands.errors.CommandInvokeError):
        pass

async def soundlist_command(context, update=None):
    sorted_list = sorted(get_sound_dict().keys())
    count = len(sorted_list)

    user_prompt = await memory.generate_user_prompt("How many sounds are available to use? Can you list them for me?", context, update)
    response = f"There are {count} sounds available to use. If I try to tell you want they are it makes me crash and Stephen's too lazy to fix it so you're gonna have to guess."
    memory.append_to_memory(user_prompt, response)

    return response

async def alias_command(context, update=None):
    # Get the username of the user that called this command
    username = await helpers.get_sender()
    user_message = await helpers.get_args_list(context, update)

    # Verify that the user is on the admin list
    with open(admins_path) as f:
        admin_list = f.readlines()

    # If the user is not on the admin list, do not let them use this command
    if username not in admin_list:
        return random.choice(txt_no_permissions)

    # Attempt to parse the new alias and target sound from the arguments provided
    try:
        new_alias = user_message[0]
        sound_name = user_message[1]

    except KeyError:
        return "Format is /alias [new alias] [sound name]"

    # Get the list of all sounds
    sound_dict = get_sound_dict()

    if new_alias in sound_dict:
        return f"There is already a sound called '{new_alias}'"

    alias_dict = get_alias_dict()

    # Avoid redirecting existing aliases to new sounds
    if new_alias in alias_dict:
        return f"'{new_alias}' is already an alias for '{alias_dict[new_alias]}'"

    if sound_name not in sound_dict:
        try:
            sound_name = alias_dict[sound_name]

        except KeyError:
            return random.choice(txt_sound_not_found)

    alias_dict[new_alias] = sound_name

    with open(alias_path, "w") as f:
        json.dump(alias_dict, f, indent=4)

    return f"'{new_alias}' has been added as an alias for '{sound_name}'"

async def delalias_command(context, update=None):
    username = await helpers.get_sender()

    with open(admins_path) as f:
        admin_list = f.readlines()

    if username not in admin_list:
        return random.choice(txt_no_permissions)

    alias_to_delete = await helpers.get_args_list(context, update)[0]
    alias_dict = get_alias_dict()

    try:
        del alias_dict[alias_to_delete]

    except KeyError:
        return f"{alias_to_delete} isn't an alias for anything."

    with open(alias_path, 'w') as f:
        json.dump(alias_dict, f, indent=4)

    return f"{alias_to_delete} is no longer assigned to a sound."

async def newsounds_command(context, update=None):
    sound_list = sorted(get_sound_dict().keys())
    playcount_dict = get_playcount_dict()
    new_sounds = [sound for sound in sound_list if playcount_dict[sound] == 0]
    new_count = len(new_sounds)
    list_string = ', '.join(new_sounds)

    if new_count == 0:
        return "There are no new sounds available."

    elif new_count == 1:
        return f"There is one new sound available: {list_string}"

    else:
        return f"There are {new_count} new sounds available:\n\n{list_string}"

async def getaliases_command(context, update=None):
    try:
        sound_name = await helpers.get_args_list(context, update).lower()
    except IndexError:
        return random.choice(txt_sound_not_provided)

    sound_dict = get_sound_dict()
    alias_dict = get_alias_dict()

    if sound_name not in sound_dict and sound_name not in alias_dict:
        return random.choice(txt_sound_not_found)

    aliases = sorted(get_aliases(sound_name, sound_dict, alias_dict))
    num_alias = len(aliases)
    join_string = "', '"
    alias_string = f"'{join_string.join(aliases)}'"

    if num_alias == 1:
        return f"The sound '{sound_name}' has one alias: {alias_string}"

    elif num_alias > 1:
        return f"The sound '{sound_name}' has {num_alias} aliases: {alias_string}"

    else:
        return f"The sound '{sound_name}' has no assigned aliases"

async def search_command(context, update=None):
    try:
        search_string = ' '.join(await helpers.get_args_list(context, update)).lower()
    except IndexError:
        return "What sound do you want me to search for?"

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
        return f"There is one sound matching '{search_string}': {list_string}"

    elif num_matches > 1:
        return f"There are {len(filtered_list)} sounds matching '{search_string}': {list_string}"

    else:
        return f"There are no sounds matching '{search_string}'"

async def playcount_command(context, update=None):
    user_message = await helpers.get_args_list(context, update)
    if not user_message or user_message[0].isspace():
        return random.choice(txt_sound_not_provided)

    sound_name = user_message[0].lower()

    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    if sound_name not in get_sound_dict():
        return random.choice(txt_sound_not_found)

    playcount = get_playcount_dict()[sound_name]
    return f"/sound {sound_name} has been used {playcount} times"

async def topsounds_command(context, update=None):
    play_counts = get_playcount_dict()
    list_size = 20
    top_sounds = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_sounds)
    return f"The {list_size} most used sounds are:\n{message}"

async def botsounds_command(context, update=None):
    play_counts = get_playcount_dict()
    list_size = 20
    bot_sounds = sorted(play_counts, key=lambda x: play_counts[x])[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in bot_sounds)
    return f"The {list_size} least used sounds are:\n{message}"
