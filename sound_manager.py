"""Sound utilities.

This module contains constants, classes, and functions used by Sound commands like
/sound, /stream, and /random.
"""

import random
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import aiofiles.os
import ffmpeg
import filetype
import strsimpy
import yt_dlp
from loguru import logger

import common


# region
class SilenceYTDL:
    """Dummy error logger that silences all unhandled error output from YTDL.

    This is disgusting but I don't know how else to stop YTDL from printing stuff to console
    when provided with bad URLs
    """

    def debug(self) -> None: pass
    def info(self) -> None: pass
    def warning(self) -> None: pass
    def error(self) -> None: pass


def stream_audio_from_url(url: str) -> dict[str, Any] | None:
    ytdl_parameters = {
        'format': 'bestaudio/best',
        'prefer_ffmpeg': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'logger': SilenceYTDL,
    }

    with yt_dlp.YoutubeDL(ytdl_parameters) as ytdl:
        data = ytdl.extract_info(url, download=False)  # type: ignore

        if data is None:
            return None

        # If a playlist was provided, take the first entry
        if 'entries' in data:
            if data['entries']:
                data = data['entries'][0]  # type: ignore
            else:
                return None

        if not isinstance(data, dict):
            return None

        return data  # type: ignore


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
        data = ytdl.extract_info(url, download=True)  # type: ignore

        if data is None:
            return None

        # If a playlist was provided, take the first entry
        if 'entries' in data:
            if data['entries']:
                data = data['entries'][0]  # type: ignore
            else:
                return None

        if not isinstance(data, dict):
            return None

        original_filename = Path(ytdl.prepare_filename(data))  # type: ignore
        return original_filename.with_suffix('.mp3')
# endregion


async def save_new_sound(sound_name: str, sound_file: bytearray) -> None:
    sound_path = (common.PATH_SOUNDS_FOLDER / sound_name).with_suffix('.mp3')

    await common.write_bytes_to_file(sound_path, sound_file)


def del_sound_file(sound_name: str) -> None:
    sound_path = (common.PATH_SOUNDS_FOLDER / sound_name).with_suffix('.mp3')
    sound_path.unlink()


async def get_sound_dict() -> dict[str, Path]:
    # Create the sound dictionary. The keys will be the names of each sound, and the values will be the
    # path to that sound's file
    sound_dict: dict[str, Path] = {}

    for f in await aiofiles.os.listdir(common.PATH_SOUNDS_FOLDER):
        file = common.PATH_SOUNDS_FOLDER / Path(f)
        if file.suffix == '.mp3':
            sound_dict[file.stem] = file

    return sound_dict


async def get_sound_list() -> list[str]:
    sound_list = [Path(file).stem
                  for file in await aiofiles.os.listdir(common.PATH_SOUNDS_FOLDER) if file.endswith('.mp3')]
    return sorted(sound_list)


async def get_alias_dict() -> dict[str, str]:
    # Load a dictionary where the keys are aliases, and the values are the
    # sounds those aliases correspond to
    return await common.try_read_json(common.PATH_SOUND_ALIASES, {})


async def new_playcount_dict() -> dict[str, int]:
    return dict.fromkeys(await get_sound_list(), 0)


async def get_playcount_dict() -> dict[str, dict[str, int]]:
    playcount_dict = await common.try_read_json(common.PATH_PLAYCOUNTS, {})
    playcount_dict, changed = await fix_playcount_dict(playcount_dict)

    # If the playcount dictionary had to be corrected, then we write the corrected
    # dictionary to a file
    if changed:
        await common.write_json_to_file(common.PATH_PLAYCOUNTS, playcount_dict)
        logger.info("Fixed error with playcount dictionary, wrote to file")

    return playcount_dict


async def fix_playcount_dict(playcount_dict: dict[str, dict[str, int]]) -> tuple[dict[str, dict[str, int]], bool]:
    sound_list = await get_sound_list()
    alias_dict = await get_alias_dict()

    # This variable makes note of whether a correction was made to the playcounts dictionary
    changed = False

    for chat_id, chat_playcounts in playcount_dict.items():
        # Ensure that all sounds are in the playcount dictionary
        missing_sounds = [sound for sound in sound_list if sound not in chat_playcounts]
        for sound_name in missing_sounds:
            playcount_dict[chat_id][sound_name] = 0
            changed = True

        # Ensure that the playcounts of aliases are not being tracked separately.
        # This could occur, for example, if a sound's name and alias are swapped
        unmerged_aliases = [alias for alias in alias_dict if alias in chat_playcounts]
        for alias in unmerged_aliases:
            sound_name = alias_dict[alias]
            playcount_dict[chat_id][sound_name] += chat_playcounts[alias]
            del playcount_dict[chat_id][alias]
            changed = True

        # Ensure that there aren't any nonexistent sounds in the playcount dictionary
        invalid_sounds = [sound for sound in chat_playcounts if sound not in sound_list]
        for sound_name in invalid_sounds:
            del playcount_dict[chat_id][sound_name]
            changed = True

    return playcount_dict, changed


async def increment_playcount(user_command: common.UserCommand, name: str) -> None:
    sound_name = await coalesce_sound_name(name)
    if sound_name is None:
        error_msg = f"Invalid sound name {name} provided."
        raise ValueError(error_msg)

    playcounts = await get_playcount_dict()
    chat_id = user_command.get_chat_id()

    if chat_id not in playcounts:
        playcounts[chat_id] = await new_playcount_dict()

    playcounts[chat_id][sound_name] = playcounts[chat_id].get(sound_name, 0) + 1
    await common.write_json_to_file(common.PATH_PLAYCOUNTS, playcounts)


async def get_chat_playcounts(user_command: common.UserCommand) -> dict[str, int]:
    """Return the number of times each sound has been played within the user's current chat."""
    playcount_dict = await get_playcount_dict()
    chat_id = user_command.get_chat_id()

    return playcount_dict.get(chat_id, await new_playcount_dict())


async def get_sound_chat_playcount(user_command: common.UserCommand, name: str) -> int | None:
    """Return the number of times the provided sound has been played within the user's current chat.

    Returns None if the sound does not exist.
    """
    sound_name = await coalesce_sound_name(name)
    if sound_name is None:
        return None

    playcounts = await get_chat_playcounts(user_command)
    return playcounts[sound_name]


async def get_global_playcounts() -> dict[str, int]:
    """Return the total number of times each sound has been played globally, in all chats."""
    playcount_dict = await get_playcount_dict()
    sound_list = await get_sound_list()

    global_playcounts = dict.fromkeys(sound_list, 0)
    for chat_id in playcount_dict:
        for sound in playcount_dict[chat_id]:
            global_playcounts[sound] += playcount_dict[chat_id][sound]

    return global_playcounts


async def get_sound_global_playcount(name: str) -> int | None:
    """Return the total number of times the provided sound has been played globally, in all chats.

    Returns None if the sound does not exist.
    """
    sound_name = await coalesce_sound_name(name)
    if sound_name is None:
        return None

    total = 0
    playcounts = await get_playcount_dict()
    for chat_id in playcounts:
        total += playcounts[chat_id][sound_name]

    return total


async def is_existing_sound(sound_name: str) -> bool:
    return sound_name in await get_sound_dict()


async def is_existing_alias(alias: str) -> bool:
    return alias in await get_alias_dict()


async def is_sound_or_alias(name: str) -> bool:
    return await is_existing_sound(name) or await is_existing_alias(name)


async def coalesce_sound_name(name: str) -> str | None:
    """Coalesce sound names and sound aliases to sound names.

    Returns None if `name` is neither a sound nor an alias.
    """
    if name in await get_sound_dict():
        return name

    if name in (alias_dict := await get_alias_dict()):
        return alias_dict[name]

    return None


async def get_sound_by_name(name: str, *, strict: bool) -> Path | list[str] | None:
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = await get_sound_dict()

    if (sound_name := await coalesce_sound_name(name)) is not None:
        return sound_dict[sound_name]

    # If strict = True, then we require an exact match for sound/alias name
    if strict:
        return None

    # Find sounds/aliases that are close matches to the provided string
    candidates = await search_sounds(name)

    # If there's more than 5 matches, then the search term is too general and we reject it
    max_candidates = 5
    if not candidates or len(candidates) > max_candidates:
        return None

    # If there's only 1 match, then we assume that's the intended sound and return it
    if len(candidates) == 1:
        return await get_sound_by_name(candidates[0], strict=True)  # Call recursively to handle aliases

    return candidates


async def get_random_sound() -> tuple[str, Path]:
    # Get the dictionary of all sounds and the paths they're located at
    sound_dict = await get_sound_dict()
    return random.choice(list(sound_dict.items()))


async def get_aliases(sound_name: str) -> list[str]:
    # Get a list of every alias for the provided sound or alias
    alias_dict = await get_alias_dict()
    alias_list: list[str] = []

    if sound_name in alias_dict:
        real_name = alias_dict[sound_name]
        alias_list.append(real_name)
    else:
        real_name = sound_name

    alias_list.extend(alias for alias in alias_dict if alias_dict[alias] == real_name and alias != sound_name)

    return sorted(alias_list)


async def add_sound_alias(new_alias: str, sound_name: str) -> str:
    if not await is_sound_or_alias(sound_name):
        return f"'{sound_name}' is not an existing sound or alias."

    if await is_existing_sound(new_alias):
        return f"There is already a sound called '{new_alias}'."

    alias_dict = await get_alias_dict()

    if new_alias in alias_dict:
        return f"'{new_alias}' is already an alias for '{alias_dict[new_alias]}'."

    try:
        alias_dict[new_alias] = alias_dict[sound_name]
    except KeyError:
        alias_dict[new_alias] = sound_name

    await common.write_json_to_file(common.PATH_SOUND_ALIASES, alias_dict)

    return f"'{new_alias}' has been added as an alias for '{sound_name}'."


async def del_sound_alias(alias_to_delete: str) -> str:
    alias_dict = await get_alias_dict()

    if not await is_existing_alias(alias_to_delete):
        return f"{alias_to_delete} isn't an alias for anything."

    prev_sound = alias_dict[alias_to_delete]
    del alias_dict[alias_to_delete]

    await common.write_json_to_file(common.PATH_SOUND_ALIASES, alias_dict)

    return f"'{alias_to_delete}' is no longer an alias for '{prev_sound}'."


async def search_sounds(search_string: str) -> list[str]:
    config = await common.Config.load()
    calculator = strsimpy.Damerau()

    search_results: list[str] = []
    for sound_name in await get_sound_list():
        for alias in [sound_name, *await get_aliases(sound_name)]:
            if search_string in alias:
                search_results.append(alias)
                break

            search_length = len(search_string)
            alias_length = len(alias)

            if search_length > alias_length:
                continue

            # Calculate the similarity between the search string and the current alias
            distance = calculator.distance(search_string, alias)
            larger_length = max(search_length, alias_length)
            similarity = (larger_length - distance) / larger_length

            if similarity >= config.misc.minsimilarity:
                search_results.append(alias)
                break

    return sorted(search_results)


def is_valid_audio(data: bytearray) -> bool:
    file_type = filetype.guess(data)
    if file_type is None:
        return False

    valid_types = {'audio/mpeg', 'audio/ogg', 'audio/x-wav'}  # mp3, ogg, wav
    return file_type.mime in valid_types


def adjust_volume(sound_name: str, delta: float) -> None:
    # Note that adjusting sound volume is LOSSY, i.e. NOT REVERSIBLE
    # Smaller adjustments may sound the same when reversed, but it's not exact
    # and larger adjustments will noticeably reduce sound quality when reversed
    # If the volume is reduced or increased too much, the sound can be entirely lost
    # Use at own risk! Back up your sound files!
    sound_path = (common.PATH_SOUNDS_FOLDER / sound_name).with_suffix('.mp3')
    temp_path = (common.PATH_TEMP_FOLDER / sound_name).with_suffix('.mp3')

    # Make sure temp folder exists and temp file doesn't exist already
    common.PATH_TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
    temp_path.unlink(missing_ok=True)

    # Write copy to temp directory in case an error occurs
    ffmpeg.input(sound_path).output(str(temp_path), af=f'volume={delta}dB').run(quiet=True)

    # If no error occurred then we can delete the original and replace with volume-adjusted version
    sound_path.unlink(missing_ok=True)
    temp_path.rename(sound_path)
    logger.info(f'Adjusted volume of {sound_name} by {delta} decibels')


async def verify_aliases() -> AsyncGenerator[str]:
    sound_list = await get_sound_list()
    alias_dict = await get_alias_dict()

    for alias in alias_dict:
        if alias in sound_list:
            yield f"Notice: {alias} is both an alias and a sound name"

        if alias_dict[alias] not in sound_list:
            yield f"Notice: {alias} corresponds to a nonexistant sound"
