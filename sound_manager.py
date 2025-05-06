"""Sound utilities.

This module contains constants, classes, and functions used by Sound commands like
/sound, /stream, and /random.
"""

import random
from collections.abc import AsyncGenerator
from pathlib import Path

import filetype
import strsimpy
import yt_dlp

import common


class SilenceYTDL:
    # This is disgusting but I don't know how else to stop YTDL from printing stuff to console
    # when provided with bad URLs
    def debug(self) -> None: pass
    def info(self) -> None: pass
    def warning(self) -> None: pass
    def error(self) -> None: pass


def stream_audio_from_url(url: str) -> dict | None:
    ytdl_parameters = {
        'format': 'bestaudio/best',
        'prefer_ffmpeg': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'logger': SilenceYTDL,
    }

    with yt_dlp.YoutubeDL(ytdl_parameters) as ytdl:
        data = ytdl.extract_info(url, download=False)

        if data is None:
            return None

        # If a playlist was provided, take the first entry
        if 'entries' in data:
            if data['entries']:
                data = data['entries'][0]
            else:
                return None

        if not isinstance(data, dict):
            return None

        return data


async def download_audio_from_url(url: str) -> Path | None:
    config = await common.Config.load()
    ytdl_parameters = {
        'format': 'bestaudio/best',
        'outtmpl': str(common.PATH_TEMP_FOLDER / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'postprocessor_args': [
            '-ss', '0',
            '-t', str(config.misc.maxstreamtime),
        ],
        'prefer_ffmpeg': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'logger': SilenceYTDL,
    }

    with yt_dlp.YoutubeDL(ytdl_parameters) as ytdl:
        data = ytdl.extract_info(url, download=True)

        if data is None:
            return None

        # If a playlist was provided, take the first entry
        if 'entries' in data:
            if data['entries']:
                data = data['entries'][0]
            else:
                return None

        if not isinstance(data, dict):
            return None

        original_filename = Path(ytdl.prepare_filename(data))
        final_filename = original_filename.with_suffix('.mp3')
        return final_filename


async def save_new_sound(sound_name: str, sound_file: bytes) -> None:
    sound_path = (common.PATH_SOUNDS_FOLDER / sound_name).with_suffix(".mp3")

    await common.write_bytes_to_file(sound_path, sound_file)


def get_sound_dict() -> dict[str, Path]:
    # If any .mp3 files are in the main directory, move them to the Sounds directory
    for file in Path().iterdir():
        if file.suffix == ".mp3":
            Path.replace(file, f"{common.PATH_SOUNDS_FOLDER}/{file}")

    # Create the sound dictionary. The keys will be the names of each sound, and the values will be the
    # path to that sound's file
    sound_dict: dict[str, Path] = {}
    for file in common.PATH_SOUNDS_FOLDER.iterdir():
        if file.suffix == ".mp3":
            sound_dict[file.stem] = file

    return sound_dict


async def get_alias_dict() -> dict[str, str]:
    # Load a dictionary where the keys are aliases, and the values are the
    # sounds those aliases correspond to
    return await common.try_read_json(common.PATH_SOUND_ALIASES, {})


async def get_playcount_dict() -> dict[str, int]:
    # Retrieve the sound and alias dictionaries
    sound_list = get_sound_list()
    alias_dict = await get_alias_dict()

    playcount_dict = await common.try_read_json(common.PATH_PLAYCOUNTS, dict.fromkeys(sound_list, 0))

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
        await common.write_json_to_file(common.PATH_PLAYCOUNTS, playcount_dict)

    return playcount_dict


async def increment_playcount(sound_name: str) -> None:
    play_counts = await get_playcount_dict()

    try:
        play_counts[sound_name] += 1
    except KeyError:
        play_counts[sound_name] = 1

    await common.write_json_to_file(common.PATH_PLAYCOUNTS, play_counts)


async def sound_exists(sound_name: str) -> bool:
    if sound_name in get_sound_dict():
        return True

    return sound_name in await get_alias_dict()


async def get_sound(sound_name: str) -> Path | list[str] | None:
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()

    try:
        return sound_dict[sound_name]

    except KeyError:
        # Sounds can have aliases, which are alternative names you can call
        # them with. If an alias is provided, we determine what sound the
        # alias corresponds to and play that sound
        sound_aliases = await get_alias_dict()

        if sound_name in sound_aliases:
            return sound_dict[sound_aliases[sound_name]]

    candidates = await search_sounds(sound_name)
    if not candidates or len(candidates) > 5:
        return None

    if len(candidates) == 1:
        return await get_sound(candidates[0])

    return candidates


def get_random_sound() -> tuple[str, Path]:
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = get_sound_dict()
    sound_name = random.choice(list(sound_dict.keys()))

    return sound_name, sound_dict[sound_name]


def get_sound_list() -> list[str]:
    return sorted(get_sound_dict().keys())


async def get_aliases(sound_name: str) -> list[str]:
    # Get a list of every alias for the provided sound
    sound_dict = get_sound_dict()
    alias_dict = await get_alias_dict()

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


async def add_sound_alias(new_alias: str, sound_name: str) -> str:
    # Get the list of all sounds
    sound_dict = get_sound_dict()

    if new_alias in sound_dict:
        return f"There is already a sound called '{new_alias}'"

    alias_dict = await get_alias_dict()

    # Avoid redirecting existing aliases to new sounds
    if new_alias in alias_dict:
        return f"'{new_alias}' is already an alias for '{alias_dict[new_alias]}'"

    if sound_name not in sound_dict:
        try:
            sound_name = alias_dict[sound_name]

        except KeyError:
            return f"'{sound_name}' is not an existing sound or alias"

    alias_dict[new_alias] = sound_name
    await common.write_json_to_file(common.PATH_SOUND_ALIASES, alias_dict)

    return f"'{new_alias}' has been added as an alias for '{sound_name}'"


async def del_sound_alias(alias_to_delete: str) -> str:
    alias_dict = await get_alias_dict()

    try:
        prev_sound = alias_dict[alias_to_delete]
        del alias_dict[alias_to_delete]

    except KeyError:
        return f"{alias_to_delete} isn't an alias for anything"

    await common.write_json_to_file(common.PATH_SOUND_ALIASES, alias_dict)

    return f"'{alias_to_delete}' is no longer an alias for '{prev_sound}'"


async def search_sounds(search_string: str) -> list[str]:
    config = await common.Config.load()

    search_results: list[str] = []
    for sound_name in get_sound_list():
        for alias in [sound_name, *await get_aliases(sound_name)]:
            if search_string in alias:
                search_results.append(alias)
                break

            if len(search_string) > len(alias):
                continue

            # Calculate the similarity between the search string and the current alias
            calculator = strsimpy.Damerau()
            distance = calculator.distance(search_string, alias)
            larger_length = max(len(search_string), len(alias))
            similarity = (larger_length - distance) / larger_length

            if similarity >= config.misc.minsimilarity:
                search_results.append(alias)
                break

    return sorted(search_results)


def is_valid_audio(data: bytes) -> bool:
    file_type = filetype.guess(data)
    if file_type is None:
        return False

    valid_types = {'audio/mpeg', 'audio/ogg', 'audio/x-wav'}
    return file_type.mime in valid_types


async def verify_aliases() -> AsyncGenerator[str]:
    sound_list = get_sound_list()
    alias_dict = await get_alias_dict()

    for alias in alias_dict:
        if alias in sound_list:
            yield f"Notice: {alias} is both an alias and a sound name"

        if alias_dict[alias] not in sound_list:
            yield f"Notice: {alias} corresponds to a nonexistant sound"
