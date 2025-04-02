import os
import json
import random
import discord
import yt_dlp
import settings
import helpers
from strsimpy import Damerau

SOUNDS_PATH = "Sounds"
ALIAS_PATH = "Data/sound_aliases.json"
PLAYCOUNTS_PATH = "Data/playcounts.json"

# This message is sent if the user doesn't provide a sound name
TXT_SOUND_NOT_PROVIDED = (
    "I'm afraid my mindreader unit has been malfunctioning lately, what sound did you want?",
    "Use your words please.",
    "I unfortunately do not have any sounds without a name."
)

# This message is sent if the sound the user requests doesn't exist
TXT_SOUND_NOT_FOUND = (
    "Are you insane, do you have any idea how dangerous a sound with that name would be?",
    "I wouldn't be caught dead with a sound like that on my list.",
    "No dice. Someone probably forgot to upload it, what a fool."
)

class YTDLStream(discord.PCMVolumeTransformer):
    ytdl = yt_dlp.YoutubeDL({
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    })

    def __init__(self, stream_url: str):
        data = self.ytdl.extract_info(stream_url, download=settings.Config().main.ytdldownload)

        if data is None:
            return

        # If a playlist was provided, take the first entry
        if 'entries' in data:
            data = data['entries'][0]

        self.title = data['title']

        super().__init__(discord.FFmpegPCMAudio(data['url'], before_options="-vn"), 0.5)

def get_sound_dict() -> dict[str, str]:
    # If any .mp3 files are in the main directory, move them to the Sounds directory
    for file in os.listdir():
        if file.endswith(".mp3"):
            os.rename(file, f"{SOUNDS_PATH}/{file}")

    # Create the sound dictionary. The keys will be the names of each sound, and the values will be the
    # path to that sound's file
    sound_dict = {}
    for file in os.listdir(SOUNDS_PATH):
        if file.endswith(".mp3"):
            sound_dict[file[:-4].lower()] = os.path.join(SOUNDS_PATH, file)

    return sound_dict

def get_alias_dict() -> dict[str, str]:
    # Load a dictionary where the keys are aliases, and the values are the
    # sounds those aliases correspond to
    with open(ALIAS_PATH, mode='r', encoding='utf-8') as f:
        return json.load(f)

def get_playcount_dict() -> dict[str, int]:
    # Retrieve the sound and alias dictionaries
    sound_list = get_sound_list()
    alias_dict = get_alias_dict()

    playcount_dict = helpers.try_read_json(PLAYCOUNTS_PATH, {x: 0 for x in sound_list})

    # This variable makes note of whether a correction was made to the playcounts dictionary
    changed = False

    # Ensure that all sounds are in the playcount dictionary
    for sound_name in sound_list:
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
        if sound_name not in sound_list:
            del playcount_dict[sound_name]
            changed = True

    # If the playcount dictionary had to be corrected, then we write the corrected
    # dictionary to a file
    if changed:
        with open(PLAYCOUNTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(playcount_dict, f, indent=4)

    return playcount_dict

async def increment_playcount(sound_name: str) -> None:
    play_counts = get_playcount_dict()

    try:
        play_counts[sound_name] += 1
    except KeyError:
        play_counts[sound_name] = 1

    with open(PLAYCOUNTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(play_counts, f, indent=4)

def sound_exists(sound_name: str) -> bool:
    if sound_name in get_sound_dict():
        return True

    if sound_name in get_alias_dict():
        return True

    return False

def get_sound(sound_name: str) -> str | None | list[str]:
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()

    try:
        return sound_dict[sound_name]

    except KeyError:
        # Sounds can have aliases, which are alternative names you can call
        # them with. If an alias is provided, we determine what sound the
        # alias corresponds to and play that sound
        sound_aliases = get_alias_dict()

        if sound_name in sound_aliases:
            return sound_dict[sound_aliases[sound_name]]

    candidates = search_sounds(sound_name)
    if not candidates or len(candidates) > 5:
        return None

    if len(candidates) == 1:
        return get_sound(candidates[0])

    return candidates

def get_random_sound() -> tuple[str, str]:
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()
    sound_name = random.choice(list(sound_dict.keys()))

    return sound_name, sound_dict[sound_name]

def get_sound_list() -> list[str]:
    return sorted(get_sound_dict().keys())

def get_sound_list_txt() -> tuple[str, int]:
    sound_list = get_sound_list()
    count = len(sound_list)
    temp_path = 'Data/soundlist.txt'

    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sound_list))

    return temp_path, count

def get_aliases(sound_name: str) -> list[str]:
    # Get a list of every alias for the provided sound
    sound_dict = get_sound_dict()
    alias_dict = get_alias_dict()

    alias_list: list[str] = []

    if sound_name not in sound_dict:
        real_name = alias_dict[sound_name]
        alias_list.append(real_name)
    else:
        real_name = sound_name

    for alias in alias_dict:
        if alias_dict[alias] == real_name and alias != sound_name:
            alias_list.append(alias)

    return sorted(alias_list)

def add_sound_alias(new_alias, sound_name) -> str:
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

    with open(ALIAS_PATH, "w", encoding='utf-8') as f:
        json.dump(alias_dict, f, indent=4)

    return f"'{new_alias}' has been added as an alias for '{sound_name}'"

async def del_sound_alias(alias_to_delete: str) -> str:
    alias_dict = get_alias_dict()

    try:
        prev_sound = alias_dict[alias_to_delete]
        del alias_dict[alias_to_delete]

    except KeyError:
        return f"{alias_to_delete} isn't an alias for anything"

    with open(ALIAS_PATH, 'w', encoding='utf-8') as f:
        json.dump(alias_dict, f, indent=4)

    return f"'{alias_to_delete}' is no longer an alias for '{prev_sound}'"

def search_sounds(search_string: str) -> list[str]:
    config = settings.Config()

    search_results: list[str] = []
    for sound_name in get_sound_list():
        for alias in [sound_name] + get_aliases(sound_name):
            if search_string in alias:
                search_results.append(alias)
                break

            if len(search_string) > len(alias):
                continue

            # Calculate the similarity between the search string and the current alias
            calculator = Damerau()
            distance = calculator.distance(search_string, alias)
            larger_length = max(len(search_string), len(alias))
            similarity = (larger_length - distance)/larger_length

            if similarity >= config.main.minsimilarity:
                search_results.append(alias)
                break

    return sorted(search_results)

def verify_aliases():
    alias_dict = get_alias_dict()
    sound_list = get_sound_list()

    for alias in alias_dict:
        if alias in sound_list:
            yield f"Notice: {alias} is both an alias and a sound name"

        if alias_dict[alias] not in sound_list:
            yield f"Notice: {alias} corresponds to a nonexistant sound"
