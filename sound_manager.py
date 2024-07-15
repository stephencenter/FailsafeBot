import os
import json
import random

sounds_path = "Sounds"
alias_path = "Data/sound_aliases.json"
playcounts_path = "Data/playcounts.json"

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

async def increment_playcount(sound_name):
    play_counts = get_playcount_dict()

    try:
        play_counts[sound_name] += 1
    except KeyError:
        play_counts[sound_name] = 1

    with open(playcounts_path, 'w') as f:
        json.dump(play_counts, f, indent=4)

def sound_exists(sound_name):
    if sound_name in get_sound_dict():
        return True

    if sound_name in get_alias_dict():
        return True

    return False

def get_sound(sound_name):
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()

    # Sounds can have aliases, which are alternative names you can call
    # them with. If an alias is provided, we determine what sound the
    # alias corresponds to and play that sound
    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    try:
        return sound_dict[sound_name]

    except KeyError:
        return None

def get_random_sound():
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()
    sound_name = random.choice(list(sound_dict.keys()))

    return sound_name, sound_dict[sound_name]

def get_sound_list() -> list:
    return sorted(get_sound_dict().keys())

def get_sound_list_txt():
    sound_list = get_sound_list()
    count = len(sound_list)
    temp_path = 'Data/soundlist.txt'

    with open(temp_path, 'w') as f:
        f.write('\n'.join(sound_list))

    return temp_path, count

def get_aliases(sound_name) -> list:
    sound_dict = get_sound_dict()
    alias_dict = get_alias_dict()

    alias_list = []

    if sound_name not in sound_dict:
        real_name = alias_dict[sound_name]
        alias_list.append(real_name)
    else:
        real_name = sound_name

    for alias in alias_dict:
        if alias_dict[alias] == real_name and alias != sound_name:
            alias_list.append(alias)

    return sorted(alias_list)

def add_sound_alias(new_alias, sound_name):
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
            return f"'{sound_name}' is not an existing sound or alias"

    alias_dict[new_alias] = sound_name

    with open(alias_path, "w") as f:
        json.dump(alias_dict, f, indent=4)

    return f"'{new_alias}' has been added as an alias for '{sound_name}'"

async def del_sound_alias(alias_to_delete):
    alias_dict = get_alias_dict()

    try:
        prev_sound = alias_dict[alias_to_delete]
        del alias_dict[alias_to_delete]

    except KeyError:
        return f"{alias_to_delete} isn't an alias for anything"

    with open(alias_path, 'w') as f:
        json.dump(alias_dict, f, indent=4)

    return f"'{alias_to_delete}' is no longer an alias for '{prev_sound}'"


def search_sounds(search_string) -> list:
    search_results = []
    for sound_name in get_sound_dict():
        if search_string in sound_name:
            search_results.append(sound_name)
        else:
            for alias in get_aliases(sound_name):
                if search_string in alias:
                    search_results.append(alias)
                    break

    return sorted(search_results)
