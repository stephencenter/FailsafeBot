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
from aiopath import AsyncPath
from loguru import logger

import command
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

    with yt_dlp.YoutubeDL(ytdl_parameters) as ytdl:  # pyright: ignore[reportArgumentType]
        data = ytdl.extract_info(url, download=False)

        # If a playlist was provided, take the first entry
        if 'entries' in data:
            if data['entries']:
                data = data['entries'][0]
            else:
                return None

        if not data:
            return None

        return dict(data)


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
            '-t', str(config.misc.maxstreamtime.value),
        ],
        'prefer_ffmpeg': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'logger': SilenceYTDL,
    }

    with yt_dlp.YoutubeDL(ytdl_parameters) as ytdl:  # pyright: ignore[reportArgumentType]
        data = ytdl.extract_info(url, download=True)

        # If a playlist was provided, take the first entry
        if 'entries' in data:
            if data['entries']:
                data = data['entries'][0]
            else:
                return None

        if not data:
            return None

        original_filename = Path(ytdl.prepare_filename(data))
        return original_filename.with_suffix('.mp3')
# endregion


async def save_new_sound(sound_name: str, sound_file: bytearray) -> None:
    """Write the provided bytearray to an .mp3 file with the provided sound_name."""
    sound_path = (common.PATH_SOUNDS_FOLDER / sound_name).with_suffix('.mp3')

    await common.write_bytes_to_file(sound_path, sound_file)


async def del_sound_file(sound_name: str) -> None:
    """Delete the sound file with the given name from the file system."""
    sound_path = AsyncPath(common.PATH_SOUNDS_FOLDER / sound_name)
    await sound_path.with_suffix('.mp3').unlink()


async def get_sound_dict() -> dict[str, Path]:
    """Return a dictionary where each key is a sound name and each value is the path to its sound file."""
    sound_dict: dict[str, Path] = {}

    for f in await aiofiles.os.listdir(common.PATH_SOUNDS_FOLDER):
        file: Path = common.PATH_SOUNDS_FOLDER / Path(f)
        if file.suffix == '.mp3':
            sound_dict[file.stem] = file

    return sound_dict


async def get_sound_list() -> list[str]:
    """Return an alphabetically sorted list of all sounds available in the Sounds directory."""
    sound_list = [
        Path(file).stem
        for file in await aiofiles.os.listdir(common.PATH_SOUNDS_FOLDER)
        if file.endswith('.mp3')
    ]
    return sorted(sound_list)


async def get_alias_dict() -> dict[str, str]:
    """Load the alias dict from a file and return it.

    The alias dict is a dictionary where the keys are aliases, and the values are the
    sound names those aliases correspond to
    """
    return await common.try_read_json(common.PATH_SOUND_ALIASES, {})


async def new_playcount_dict() -> dict[str, int]:
    """Return a dict where each available sound is a key and all values are 0."""
    return {key: 0 for key in await get_sound_list()}  # noqa: C420 (makes type checker angry)


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
    """Return the provided playcount dict with any errors fixed."""
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


async def increment_playcount(user_command: command.UserCommand, name: str) -> None:
    """Increments the playcount in the current chat for the given sound name."""
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


async def get_chat_playcounts(user_command: command.UserCommand) -> dict[str, int]:
    """Return the number of times each sound has been played within the user's current chat."""
    playcount_dict = await get_playcount_dict()
    chat_id = user_command.get_chat_id()

    return playcount_dict.get(chat_id, await new_playcount_dict())


async def get_sound_chat_playcount(user_command: command.UserCommand, name: str) -> int | None:
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
    global_playcounts = await new_playcount_dict()

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


async def is_existing_sound(name: str) -> bool:
    """Return True if the provided name is a valid sound name (i.e. has a matching .mp3 file), False otherwise.

    Does NOT return True if the provided name only matches an alias.
    """
    return name in await get_sound_dict()


async def is_existing_alias(name: str) -> bool:
    """Return True if the provided name is a valid sound alias, False otherwise..

    Does NOT return True if the provided name only matches a sound name.
    """
    return name in await get_alias_dict()


async def is_sound_or_alias(name: str) -> bool:
    """Return True if the provided name is a valid sound name or alias, False otherwise."""
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


async def get_sound_candidates(search_string: str, max_candidates: int = 5) -> list[tuple[str, Path]]:
    sound_dict = await get_sound_dict()

    # If we have an exact match we return it immediately
    if (sound_name := await coalesce_sound_name(search_string)) is not None:
        item = (sound_name, sound_dict[sound_name])
        return [item]

    # Find sounds/aliases that are close matches to the provided string
    matches = await search_sounds(search_string)

    candidates: list[tuple[str, Path]] = []
    for item in matches:
        sound_name = await coalesce_sound_name(item)
        if sound_name is None:
            continue

        candidates.append((sound_name, sound_dict[sound_name]))

    # If there's more than 5 matches, then the search term is too general and we reject it
    if len(candidates) > max_candidates:
        return []

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
    similarity_threshold = min(config.misc.minsimilarity.value, 1.0)

    search_results: list[str] = []
    for sound_name in await get_sound_list():
        for alias in [sound_name, *await get_aliases(sound_name)]:
            if search_string in alias:
                search_results.append(alias)
                break

            # If similarity threshold is 1.0 then only exact matches are accepted, so the similarity
            # check is skipped
            if similarity_threshold >= 1.0:
                continue

            search_length = len(search_string)
            alias_length = len(alias)

            if search_length > alias_length:
                continue

            # Calculate the similarity between the search string and the current alias
            distance = calculator.distance(search_string, alias)
            larger_length = max(search_length, alias_length)
            similarity = (larger_length - distance) / larger_length

            if similarity >= similarity_threshold:
                search_results.append(alias)
                break

    return sorted(search_results)


def is_valid_audio(data: bytearray) -> bool:
    """Return True if provided bytearray has a supported audio mimetype (mp3, ogg, wav), False otherwise."""
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
