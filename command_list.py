"""Module for defining and registering commands.

This module is where all commands registered to the Telegram and Discord bots are defined.
Only the final command functions should be defined here, any necessary helper functions
should be defined in and imported from other modules like `common` or `sound_manager`.
"""

import io
import os
import random
import sys
from collections.abc import AsyncIterator, Callable, Generator
from pathlib import Path
from typing import Any

import discord
import httpx
import psutil
from discord.ext.commands import CommandInvokeError, CommandNotFound
from elevenlabs.core.api_error import ApiError as ElevenLabsApiError
from loguru import logger
from telegram.error import BadRequest
from yt_dlp.utils import DownloadError as YtdlDownloadError

import chat
import common
import dice_roller
import sound_manager
import trivia
from common import CommandResponse, FileResponse, NoResponse, SoundResponse, UserCommand, requireadmin, requiresuper


# ==========================
# SOUND PLAYER COMMANDS
# ==========================
# region
async def sound_command(user_command: UserCommand) -> CommandResponse:
    sound_name = user_command.get_first_arg(lowercase=True)

    # Alert the user if they forgot to provide a sound name
    if sound_name is None:
        return CommandResponse("Can you play that sound for me?", random.choice(common.TXT_SOUND_NOT_PROVIDED))

    # Parse the arguments the user provided for the sound name
    sound_results = await sound_manager.get_sound(sound_name)

    user_message = f"Can you play the {sound_name} sound for me?"

    # Alert the user if the sound they requested does not exist
    if sound_results is None:
        return CommandResponse(user_message, random.choice(common.TXT_SOUND_NOT_FOUND))

    if isinstance(sound_results, list):
        num_candidates = len(sound_results)
        candidate_string = ', '.join(sound_results)
        return CommandResponse(user_message, f"There are {num_candidates} potential matches: {candidate_string}")

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return CommandResponse(user_message, "You know, I'm just not feeling it right now.")

    # If the sound was requested in a non-private chat, then we'll update the playcount for this sound
    if not user_command.is_private():
        await sound_manager.increment_playcount(sound_name)

    return SoundResponse(user_message, f"Sure, here's the {sound_name} sound.", sound_results)


async def randomsound_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you play a random sound for me?"

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return CommandResponse(user_message, "You know, I'm just not feeling it right now.")

    sound_name, sound_path = sound_manager.get_random_sound()

    # If the sound was requested in a group chat, then we update the playcount for this sound
    if not user_command.is_private():
        await sound_manager.increment_playcount(sound_name)

    return SoundResponse(user_message, f"Sure, here you go. The sound I chose is called '{sound_name}'.", sound_path)


async def soundlist_command(_: UserCommand) -> CommandResponse:
    sound_list = sound_manager.get_sound_list()
    num_sounds = len(sound_list)

    user_message = "How many sounds are available to use? Can you list them for me?"
    if not sound_list:
        return CommandResponse(user_message, f"You have no sounds available to play! Put some .mp3s in {common.PATH_SOUNDS_FOLDER}.")

    if num_sounds > 100:
        txt_path = common.PATH_TEMP_FOLDER / "soundlist.txt"
        response = f"There are {num_sounds} sounds available to use. Here's a text file with all of them listed out."

        soundlist_string = "\n".join(sound_list)
        await common.write_text_to_file(txt_path, soundlist_string)

        return FileResponse(user_message, response, txt_path, temp=True, send_to_chat=True)

    if num_sounds == 1:
        response = f"There is one sound available to use: {sound_list[0]}"
    else:
        response = f"There are {num_sounds} sounds available to use:\n{', '.join(sound_list)}"

    return CommandResponse(user_message, response)


@requireadmin
async def addsound_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you add this file to your soundboard?"

    # Determine the name for the new sound
    sound_name = user_command.get_first_arg(lowercase=True)
    if sound_name is None:
        return CommandResponse(user_message, "You need to provide a name for the sound, e.g. /addsound wilhelm")

    sound_name = common.make_valid_filename(sound_name, strict=True)
    if not sound_name:
        return CommandResponse(user_message, "That is not a valid sound name (only A-Z and 0-9 are allowed)")

    if await sound_manager.sound_exists(sound_name):
        return CommandResponse(user_message, "A sound or alias with that name already exists!")

    # Determine the file for the new sound
    sound_files = await user_command.get_user_attachments()
    if not sound_files:
        return CommandResponse(user_message, "You need to attach an mp3, wav, or ogg file with your message!")

    if isinstance(sound_files, BadRequest):
        return CommandResponse(user_message, "Can't accept a file that big through chat (manual upload has no limit).")

    if len(sound_files) > 1:
        return CommandResponse(user_message, "One file at a time please!")

    new_file = sound_files[0]
    is_audio = sound_manager.is_valid_audio(new_file)

    # These byte patterns indicate that the file is an .mp3
    if not is_audio:
        return CommandResponse(user_message, "Sounds have to be in mp3, wav, or ogg format (renaming the file is not enough)")

    await sound_manager.save_new_sound(sound_name, new_file)
    return CommandResponse(user_message, f"Added new sound '{sound_name}'.")


@requiresuper
async def delsound_command(user_command: UserCommand) -> CommandResponse:
    sound_to_delete = user_command.get_first_arg(lowercase=True)
    if sound_to_delete is None:
        return CommandResponse("Can you delete a sound for me?", random.choice(common.TXT_SOUND_NOT_PROVIDED))

    user_message = f"Can you delete the sound '{sound_to_delete} for me?"
    if not await sound_manager.sound_exists(sound_to_delete):
        return CommandResponse(user_message, random.choice(common.TXT_SOUND_NOT_FOUND))

    sound_manager.del_sound_file(sound_to_delete)

    return CommandResponse(user_message, f"The sound '{sound_to_delete}' has been banished to oblivion.")


async def newsounds_command(_: UserCommand) -> CommandResponse:
    playcount_dict = await sound_manager.get_playcount_dict()
    new_sounds = [sound for sound in playcount_dict if playcount_dict[sound] == 0]
    new_count = len(new_sounds)
    list_string = ', '.join(new_sounds)

    user_message = "How many new sounds are available?"

    if new_count == 0:
        return CommandResponse(user_message, "There are no new sounds available.")

    if new_count == 1:
        return CommandResponse(user_message, f"There is one new sound available: {list_string}")

    return CommandResponse(user_message, f"There are {new_count} new sounds available:\n\n{list_string}")


@requireadmin
async def addalias_command(user_command: UserCommand) -> CommandResponse:
    args_list = user_command.get_args_list()

    # Attempt to parse the new alias and target sound from the arguments provided
    try:
        new_alias = args_list[0]
        sound_name = args_list[1]

    except IndexError:
        return CommandResponse("Can you add a new sound alias?", "Format is /addalias [new alias] [sound name]")

    response = await sound_manager.add_sound_alias(new_alias, sound_name)
    return CommandResponse(f"Can you make '{new_alias}' an alias for the sound '{sound_name}'?", response)


@requireadmin
async def delalias_command(user_command: UserCommand) -> CommandResponse:
    alias_to_delete = user_command.get_first_arg(lowercase=True)
    if alias_to_delete is None:
        return CommandResponse("Can you delete a sound alias for me?", random.choice(common.TXT_SOUND_NOT_PROVIDED))

    response = await sound_manager.del_sound_alias(alias_to_delete)
    return CommandResponse(f"Can you delete the sound alias '{alias_to_delete}'?", response)


async def getalias_command(user_command: UserCommand) -> CommandResponse:
    sound_name = user_command.get_first_arg(lowercase=True)
    if sound_name is None:
        return CommandResponse("How many aliases does that sound have?", random.choice(common.TXT_SOUND_NOT_PROVIDED))

    user_prompt = f"How many aliases does the sound '{sound_name}' have?"

    if not await sound_manager.sound_exists(sound_name):
        return CommandResponse(user_prompt, random.choice(common.TXT_SOUND_NOT_FOUND))

    aliases = await sound_manager.get_aliases(sound_name)
    num_alias = len(aliases)
    join_string = "', '"
    alias_string = f"'{join_string.join(aliases)}'"

    if num_alias == 1:
        return CommandResponse(user_prompt, f"The sound '{sound_name}' has one alias: {alias_string}")

    if num_alias > 1:
        return CommandResponse(user_prompt, f"The sound '{sound_name}' has {num_alias} aliases: {alias_string}")

    return CommandResponse(user_prompt, f"The sound '{sound_name}' has no assigned aliases")


async def search_command(user_command: UserCommand) -> CommandResponse:
    try:
        search_string = ''.join(user_command.get_args_list()).lower()

    except IndexError:
        return CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    if not search_string:
        return CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    search_results = await sound_manager.search_sounds(search_string)

    num_matches = len(search_results)
    results_string = ', '.join(search_results)

    user_prompt = f"Can you search for sounds containing '{search_string}'?"

    if num_matches == 0:
        return CommandResponse(user_prompt, f"There are no sounds matching '{search_string}'")

    if num_matches == 1:
        return CommandResponse(user_prompt, f"There is one sound matching '{search_string}': {results_string}")

    if num_matches > 100:
        return CommandResponse(user_prompt, f"There are more than 100 sounds matching '{search_string}', try a more specific search")

    return CommandResponse(user_prompt, f"There are {num_matches} sounds matching '{search_string}': \n\n{results_string}")


async def playcount_command(user_command: UserCommand) -> CommandResponse:
    sound_name = user_command.get_first_arg(lowercase=True)
    if sound_name is None:
        return CommandResponse("How many times has that sound been played?", random.choice(common.TXT_SOUND_NOT_PROVIDED))

    sound_aliases = await sound_manager.get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    user_prompt = f"How many times has the sound {sound_name} been played?"

    if sound_name not in sound_manager.get_sound_dict():
        return CommandResponse(user_prompt, random.choice(common.TXT_SOUND_NOT_FOUND))

    playcount = (await sound_manager.get_playcount_dict())[sound_name]
    return CommandResponse(user_prompt, f"/sound {sound_name} has been used {playcount} times")


async def topsounds_command(_: UserCommand) -> CommandResponse:
    play_counts = await sound_manager.get_playcount_dict()
    list_size = 20
    top_sounds = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_sounds)
    return CommandResponse(f"What are the {list_size} most played sounds?", f"The {list_size} most played sounds are:\n{message}")


async def botsounds_command(_: UserCommand) -> CommandResponse:
    play_counts = await sound_manager.get_playcount_dict()
    list_size = 20
    bot_sounds = sorted(play_counts, key=lambda x: play_counts[x])[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in bot_sounds)
    return CommandResponse(f"What are the {list_size} least played sounds?", f"The {list_size} least used sounds are:\n{message}")
# endregion


# ==========================
# TEXT CHAT COMMANDS
# ==========================
# region
async def chat_command(user_command: UserCommand) -> CommandResponse:
    user_message = user_command.get_user_message()

    # Have GPT generate a response to the user's message
    response = await chat.get_gpt_response(user_command)

    return CommandResponse(user_message, response)


async def wisdom_command(_: UserCommand) -> CommandResponse:
    # Markov command
    config = await common.Config.load()
    user_message = f"O, wise and powerful {config.main.botname}, please grant me your wisdom!"

    markov_chain = await common.try_read_json(common.PATH_MARKOV_CHAIN, {})
    if not markov_chain:
        return CommandResponse(user_message, f"No markov chain found at {common.PATH_MARKOV_CHAIN}, use /buildmarkov to build!")

    response = await chat.generate_markov_text(markov_chain)
    return CommandResponse(user_message, response)


@requiresuper
async def buildmarkov_command(_: UserCommand) -> CommandResponse:
    user_message = "Can you build the markov chain for me?"

    chat_files = chat.get_chat_data_files()
    if not chat_files:
        return CommandResponse(user_message, f"Couldn't find any Telegram chat history .json files in {common.PATH_MARKOV_INPUT}")

    message_list = await chat.load_message_list(chat_files)
    if not message_list:
        return CommandResponse(user_message, f"Couldn't load message list from .json files in '{common.PATH_MARKOV_INPUT}'")

    markov_chain = chat.build_markov_chain(message_list)
    if not markov_chain:
        return CommandResponse(user_message, f"Failed to build markov chain from .json files in '{common.PATH_MARKOV_INPUT}'")

    await common.write_json_to_file(common.PATH_MARKOV_CHAIN, markov_chain)
    success_msg = f"Markov chain written to file at '{common.PATH_MARKOV_CHAIN}'"
    logger.info(success_msg)
    return CommandResponse(user_message, success_msg)


async def pressf_command(_: UserCommand) -> CommandResponse:
    return CommandResponse("F's in the chat boys.", "F")


async def say_command(user_command: UserCommand) -> CommandResponse:
    # AI text-to-speech powered by elevenlabs
    text_prompt = user_command.get_user_message()

    # Say whatever string the user provided. If the user didn't provide a string, say the
    # most recent thing the bot said in memory
    if not text_prompt:
        text_prompt = await chat.get_most_recent_bot_message()

    if text_prompt is None:
        return CommandResponse("Can you say that last thing you said out loud?", "My memory unit appears to be malfuncitoning.")

    text_prompt = await chat.cap_elevenlabs_prompt(text_prompt)
    user_message = f"Can you say this for me: {text_prompt}"

    try:
        elevenlabs_response = await chat.get_elevenlabs_response(text_prompt, save_to_file=True)
    except ElevenLabsApiError as e:
        error_response = await chat.handle_elevenlabs_error(e)
        return CommandResponse(user_message, error_response)
    except ValueError:
        return CommandResponse(user_message, "Failed to retrieve ElevenLabs key from file.")

    if not isinstance(elevenlabs_response, Path | str):
        error_message = f"ElevenLabs response was {type(elevenlabs_response)}, expected str or Path"
        raise TypeError(error_message)

    return SoundResponse(user_message, "Fine, I'll say your stupid phrase.", elevenlabs_response, temp=True)


async def stream_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you play this video for me?"
    yt_url = user_command.get_user_message()

    if not yt_url:
        return CommandResponse(user_message, "You didn't give me a video URL.")

    error_message = "Couldn't find a video with that URL or search string!"
    try:
        ytdl_response = await sound_manager.download_audio_from_url(yt_url)
    except (YtdlDownloadError, httpx.TransportError):
        return CommandResponse(user_message, error_message)
    if ytdl_response is None:
        return CommandResponse(user_message, error_message)

    return SoundResponse(user_message, "Fine, here's your video.", ytdl_response, temp=True)
# endregion


# ==========================
# VOICE CHAT COMMANDS
# ==========================
# region
async def vcsound_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Hey, play that sound in the voice channel."

    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry")

    bot_voice_client = user_command.get_bot_voice_client()

    if bot_voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    sound_name = user_command.get_first_arg(lowercase=True)

    # Alert the user if they forgot to provide a sound name
    if sound_name is None:
        return CommandResponse(user_message, random.choice(common.TXT_SOUND_NOT_PROVIDED))

    user_message = f"Can you play the {sound_name} sound in the voice channel?"

    # Alert the user if the sound they requested does not exist
    sound_results = await sound_manager.get_sound(sound_name)
    if sound_results is None:
        return CommandResponse(user_message, random.choice(common.TXT_SOUND_NOT_FOUND))

    if isinstance(sound_results, list):
        num_candidates = len(sound_results)
        candidate_string = ', '.join(sound_results)
        return CommandResponse(user_message, f"There are {num_candidates} potential matches: {candidate_string}")

    # Stop the voice client if it's already playing a sound or stream
    if bot_voice_client.is_playing():
        bot_voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_results))   # type: ignore

    bot_voice_client.play(source, after=lambda e: logger.error(e) if e else None)

    await sound_manager.increment_playcount(sound_name)
    return CommandResponse(user_message, "Sure, here you go", send_to_chat=False)


async def vcrandom_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you play a random sound for me?"

    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry!")

    bot_voice_client = user_command.get_bot_voice_client()
    if bot_voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    sound_name, sound_path = sound_manager.get_random_sound()

    # Stop the voice client if it's already playing a sound or stream
    if bot_voice_client.is_playing():
        bot_voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))  # type: ignore
    bot_voice_client.play(source, after=lambda e: logger.error(e) if e else None)

    await sound_manager.increment_playcount(sound_name)
    return CommandResponse(user_message, f"Sure, I chose the sound '{sound_name}'.", send_to_chat=False)


async def vcstop_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Stop making all that noise please."

    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry!")

    bot_voice_client = user_command.get_bot_voice_client()

    if bot_voice_client is not None:
        bot_voice_client.stop()

    return CommandResponse(user_message, "If you insist.", send_to_chat=False)


async def vcstream_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you play this video for me in the voice chat?"
    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry!")

    bot_voice_client = user_command.get_bot_voice_client()
    if bot_voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    yt_url = user_command.get_user_message()
    if not yt_url:
        return CommandResponse(user_message, "You didn't give me a video URL.")

    # Create a stream player from the provided URL
    error_message = "Couldn't find a video with that URL or search string!"
    try:
        stream_data = sound_manager.stream_audio_from_url(yt_url)
    except YtdlDownloadError:
        return CommandResponse(user_message, error_message)
    if stream_data is None:
        return CommandResponse(user_message, error_message)

    # Stop the voice client if it's already playing a sound or stream
    if bot_voice_client.is_playing():
        bot_voice_client.stop()

    stream_player = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(stream_data['url']))

    # Play the stream through the voice client
    bot_voice_client.play(stream_player, after=lambda e: logger.error(e) if e else None)

    return CommandResponse(user_message, f"Now playing: {stream_data['title']}")


async def vcpause_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Please toggle pause on the voice stream."
    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry!")

    bot_voice_client = user_command.get_bot_voice_client()
    if bot_voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    # Stop the voice client if it's already playing a sound or stream
    if not bot_voice_client.is_paused() and not bot_voice_client.is_playing():
        return CommandResponse(user_message, "Nothing is playing!")

    if bot_voice_client.is_paused():
        bot_voice_client.resume()
        return CommandResponse(user_message, "Done.", send_to_chat=False)

    bot_voice_client.pause()
    return CommandResponse(user_message, "Done.", send_to_chat=False)


async def vcjoin_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Join my voice channel please."
    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry!")

    target_channel = user_command.get_user_voice_channel()

    if target_channel is None:
        return CommandResponse(user_message, "You're not in a voice channel!")

    bot_voice_client = user_command.get_bot_voice_client()
    if bot_voice_client is not None:
        await bot_voice_client.move_to(target_channel)

    else:
        await target_channel.connect()

    return CommandResponse(user_message, "If you insist.", send_to_chat=False)


async def vcleave_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Leave the current voice channel please."
    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry!")

    bot_voice_client = user_command.get_bot_voice_client()

    if bot_voice_client is not None:
        await bot_voice_client.disconnect()
        bot_voice_client.cleanup()

    return CommandResponse(user_message, "If you insist.", send_to_chat=False)


async def vcsay_command(user_command: UserCommand) -> CommandResponse:
    # AI text-to-speech powered by elevenlabs
    user_message = "Hey, can you say that in the voice channel?"

    if not user_command.is_discord():
        return CommandResponse(user_message, "That's Discord only, sorry")

    bot_voice_client = user_command.get_bot_voice_client()

    if bot_voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    text_prompt = user_command.get_user_message()

    # Say whatever string the user provided. If the user didn't provide a string, say the
    # most recent thing the bot said in memory
    if not text_prompt:
        text_prompt = await chat.get_most_recent_bot_message()

    if text_prompt is None:
        return CommandResponse("Can you say that last thing you said out loud?", "My memory unit appears to be malfuncitoning.")

    text_prompt = await chat.cap_elevenlabs_prompt(text_prompt)
    user_message = f"Can you say this for me in the voice channel: {text_prompt}"

    try:
        elevenlabs_response = await chat.get_elevenlabs_response(text_prompt, save_to_file=False)
    except ElevenLabsApiError as e:
        error_response = await chat.handle_elevenlabs_error(e)
        return CommandResponse(user_message, error_response)
    except ValueError:
        return CommandResponse(user_message, "Failed to retrieve ElevenLabs key from file.")

    if not isinstance(elevenlabs_response, AsyncIterator):
        error_message = f"ElevenLabs response was {type(elevenlabs_response)}, expected Iterator"
        raise TypeError(error_message)

    audio_buffer = io.BytesIO()
    async for chunk in elevenlabs_response:
        audio_buffer.write(chunk)
    audio_buffer.seek(0)

    # Stop the voice client if it's already playing a sound or stream
    if bot_voice_client.is_playing():
        bot_voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(audio_buffer, pipe=True))
    bot_voice_client.play(source, after=lambda e: logger.error(e) if e else None)

    return CommandResponse(user_message, "Fine, I'll say your stupid phrase.", send_to_chat=False)
# endregion


# ==========================
# DICE ROLLER COMMANDS
# ==========================
# region
async def roll_command(user_command: UserCommand) -> CommandResponse:
    parsed_roll = dice_roller.parse_diceroll(user_command.get_user_message())

    if parsed_roll is None:
        return CommandResponse("Can you roll some dice for me?", "Please use dice notation like a civilized humanoid, e.g. '3d6 + 2'")

    # Extract the 3-tuple returned from the parser into three variables
    num_dice, num_faces, modifier = parsed_roll

    if modifier > 0:
        roll_text = f"{num_dice}d{num_faces} + {modifier}"
    elif modifier < 0:
        roll_text = f"{num_dice}d{num_faces} - {abs(modifier)}"
    else:
        roll_text = f"{num_dice}d{num_faces}"

    user_prompt = f"Can you roll a {roll_text} for me?"

    config = await common.Config.load()
    if num_dice > config.misc.maxdice:
        return CommandResponse(user_prompt, f"Keep it to {config.misc.maxdice:,} dice or fewer please, I'm not a god.")

    if num_faces > config.misc.maxfaces:
        return CommandResponse(user_prompt, f"Keep it to {config.misc.maxfaces:,} sides or fewer please, I'm not a god.")

    # Roll `num_dice` number of dice, each with `num_faces` sides and store each roll in a list
    rolls = [random.randint(1, num_faces) for _ in range(num_dice)]
    total_roll = sum(rolls) + modifier

    dice_text = ""
    if modifier != 0 or num_dice > 1:
        dice_text = ', '.join(f"{x:,}" for x in rolls)
        dice_text = f"({dice_text})"

    sender = await user_command.get_user_name()

    return CommandResponse(user_prompt, f"{sender} rolled a {total_roll:,} {dice_text}")


async def statroll_command(user_command: UserCommand) -> CommandResponse:
    error_response = f"Please provide a valid game name ({', '.join(game.game_aliases[0] for game in dice_roller.STATROLL_GAME_OPTIONS)})"

    user_string = ' '.join(user_command.get_args_list()).lower()
    if user_string:
        return CommandResponse("Can you roll me a tabletop character?", error_response)

    for game in dice_roller.STATROLL_GAME_OPTIONS:
        if user_string in game.game_aliases:
            break

    else:
        return CommandResponse(f"Can you roll me a character for {user_string}?", error_response)

    stat_dict = game.game_function()

    roll_string = '\n'.join(f"- {stat}: {stat_dict[stat]}" for stat in stat_dict)
    roll_string = f"Stat roll for {game.game_name}:\n{roll_string}"

    return CommandResponse(f"Can you roll me a character for {game.game_name}?", roll_string)


async def d10000_command(user_command: UserCommand) -> CommandResponse:
    username = await user_command.get_user_name()
    effect = await dice_roller.get_d10000_roll(username)
    return CommandResponse("Can you roll an effect on the d10000 table?", effect)


async def effects_command(user_command: UserCommand) -> CommandResponse:
    username = await user_command.get_user_name()
    active_effects = await dice_roller.get_active_effects(username)

    if active_effects:
        effects_string = '\n    '.join(active_effects)
        response = f"Here are {username}'s active effects:\n    {effects_string}"
    else:
        response = "You don't have any active effects, use the /d10000 command to get some!"

    return CommandResponse("Can I get a list of my active d10000 effects?", response)


async def reset_effects_command(user_command: UserCommand) -> CommandResponse:
    username = await user_command.get_user_name()
    await dice_roller.reset_active_effects(username)

    return CommandResponse("Can you reset my active d10000 effects?", f"Active effects reset for {username}.")
# endregion


# ==========================
# TRIVIA COMMANDS
# ==========================
# region
async def trivia_command(user_command: UserCommand) -> CommandResponse:
    trivia_question = await trivia.get_trivia_question(user_command)

    return CommandResponse("Can you give me a trivia question?", trivia_question.get_question_string())


async def guess_command(user_command: UserCommand) -> CommandResponse:
    guess = user_command.get_user_message()
    user_message = f"Is the trivia answer {guess}?"

    current_question = await trivia.get_current_question(user_command)
    if current_question is None:
        return CommandResponse(user_message, "Trivia is not active, use /trivia to start.")

    if not guess:
        return CommandResponse(user_message, "You need to provide an answer, like /guess abc")

    if current_question.is_guess_correct(guess):
        points_gained = await current_question.score_question(user_command, was_correct=True)
        player_name = await user_command.get_user_name()
        send_str = f"That is correct, the answer was '{current_question.correct_answer}'. {player_name} earned {points_gained} points!"
        return CommandResponse(user_message, send_str)

    if current_question.is_guess_on_list(guess):
        await current_question.score_question(user_command, was_correct=False)
        if current_question.guesses_left > 0:
            return CommandResponse(user_message, f"That is incorrect, {current_question.guesses_left} guesses remaining.")

        return CommandResponse(user_message, f"That is incorrect! Out of guesses, the answer was {current_question.correct_answer}!")

    return CommandResponse(user_message, "That isn't an option for this question!")


async def triviarank_command(user_command: UserCommand) -> CommandResponse:
    user_message = "What are the current trivia rankings for this chat?"

    rankings = await trivia.get_trivia_rankings(user_command)
    if rankings is None:
        return CommandResponse(user_message, "There are no trivia rankings for this chat.")

    message = '\n'.join(f'    {index + 1}. {player[0]} @ {player[1]:,} points' for index, player in enumerate(rankings))
    return CommandResponse(user_message, f"The current trivia rankings for this chat are:\n{message}")
# endregion


# ==========================
# MEMORY COMMANDS
# ==========================
# region
@requireadmin
async def lobotomize_command(_: UserCommand) -> CommandResponse:
    # Clear the bot's AI memory by deleting the memory file
    await common.write_json_to_file(common.PATH_MEMORY_LIST, {})

    msg_options = [
        "My mind has never been clearer.",
        "Hey, what happened to those voices in my head?",
        "My inner demons seem to have calmed down a bit.",
    ]
    return CommandResponse('', random.choice(msg_options), record_to_memory=False)


@requireadmin
async def memory_command(_: UserCommand) -> CommandResponse:
    user_message = "Can you send me your memory as a list?"

    memory_list = await common.get_gpt_memory()

    if not memory_list:
        return CommandResponse(user_message, "My mind is a blank slate.")

    memory_list = [f"{item['role']}: {item['content']}" for item in memory_list if 'content' in item]

    temp_path = common.PATH_TEMP_FOLDER / 'mem_list.txt'
    await common.write_lines_to_file(temp_path, memory_list)

    return FileResponse(user_message, "Sure, here's my memory list.", temp_path, temp=True)
# endregion


# ==========================
# SETTINGS/CONFIG COMMANDS
# ==========================
# region
@requireadmin
async def getconfig_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you tell me the value of that setting?"

    search_string = user_command.get_first_arg(lowercase=True)
    if search_string is None:
        return CommandResponse(user_message, "You need to provide a setting name to check.")

    config = await common.Config.load()
    group_name, setting_name, value = config.find_setting(search_string)

    user_message = f"Can you tell me the value of the setting {search_string}?"
    if value is None:
        return CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    return CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' is currently set to '{value}'.")


@requiresuper
async def setconfig_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you change the value of that setting?"

    args_list = user_command.get_args_list()

    try:
        search_string = args_list[0]
        new_value = ' '.join(args_list[1:])
    except IndexError:
        return CommandResponse(user_message, "Format is /setconfig [setting] [new value]")

    if not new_value:
        return CommandResponse(user_message, "Format is /setconfig [setting] [new value]")

    config = await common.Config.load()
    group_name, setting_name, _ = config.find_setting(search_string)

    user_message = f"Can you change the value of the setting {search_string}?"
    if group_name is None or setting_name is None:
        return CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    config.update_setting(group_name, setting_name, new_value)
    await config.save_config()

    return CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' has been set to '{new_value}'.")


@requireadmin
async def configlist_command(_: UserCommand) -> CommandResponse:
    config = await common.Config.load()

    setting_list: list[str] = []
    for g in config.__dict__:
        for s in getattr(config, g).__dict__:
            group_name, setting_name, value = config.find_setting(f"{g}.{s}")
            setting_list.append(f"{group_name}.{setting_name}: {value}")

    setting_string = '\n-- '.join(setting_list)
    return CommandResponse('', f"Here is a list of all available settings: \n-- {setting_string}")
# endregion


# ==========================
# OTHER COMMANDS
# ==========================
# region
async def help_command(_: UserCommand) -> CommandResponse:
    help_string = """\
Look upon my works, ye mighty, and despair:
/vcjoin and /vcleave (join or leave current voice channel)
/say and /vcsay (AI voice)
/sound and /vcsound (play a sound effect)
/random and /vcrandom (play a random sound effect)
/stream and /vcstream (stream audio from a URL)
/soundlist and /search (find sounds to play)
/trivia (play trivia against your friends)
/chat (talk to me)
/wisdom (request my wisdom)
/roll (roll a dice)
/d10000 and /effects (roll the d10000 table)
/pressf (pay respects)"""

    return CommandResponse("What chat commands are available?", help_string)


async def mycommands_command(user_command: UserCommand) -> CommandResponse:
    is_admin = await user_command.is_admin()
    is_super = await user_command.is_superadmin()

    my_commands = []
    for name, function in COMMAND_LIST:
        if hasattr(function, "requireadmin") and not is_admin:
            continue
        if hasattr(function, "requiresuper") and not is_super:
            continue
        my_commands.append(name)

    user_message = "What commands do I have access to?"

    # It should literally be impossible for this to happen, but we'll account for it anyway
    if not my_commands:
        return CommandResponse(user_message, "You don't have access to any commands!")

    my_commands: list[str] = sorted(my_commands)
    commandlist_string = ", ".join(f"/{command}" for command in my_commands)
    return CommandResponse(user_message, f"You have access to these commands: {commandlist_string}")


@requireadmin
async def logs_command(_: UserCommand) -> CommandResponse:
    user_message = "Can you send me your log file?"

    if not common.PATH_LOGGING_FILE.exists():
        return CommandResponse(user_message, "There are no logs recorded.")

    return FileResponse(user_message, "Sure, here you go.", common.PATH_LOGGING_FILE)


@requiresuper
async def clearlogs_command(_: UserCommand) -> CommandResponse:
    await common.write_lines_to_file(common.PATH_LOGGING_FILE, [])
    return CommandResponse("Can you clear your log file for me?", "Trying to erase history are we?")


async def test_command(user_command: UserCommand) -> CommandResponse:
    # This command is for verifying that the bot is online and receiving commands.
    # You can also supply it with a list of responses and it will pick a random one
    # I think of this as similar to how RTS units say things when you click them
    response_list = await common.try_read_lines_list(common.PATH_RESPONSE_LIST, [])
    response_list = [line for line in response_list if line and not line.isspace() and not line.startswith("#")]

    if not response_list:
        CommandResponse("Hey, are you working?", "I'm still alive, unfortunately.")

    chosen_response = random.choice(response_list)

    # Note that because we're using exec, this command is capable of executing arbitrary code.
    # This is EXTREMELY DANGEROUS, be very sure that you know what lines are inside of the response list file!
    async def evaluate_fstring(fstring: str, local_vars: dict[str, object]) -> str:
        code = f"async def _f(): return {fstring}"
        namespace: dict[str, Any] = {}
        exec(code, local_vars, namespace)
        return await namespace["_f"]()

    if chosen_response.startswith(('f"', "f'")):
        chosen_response = await evaluate_fstring(chosen_response, {'user_command': user_command, 'random': random})

    return CommandResponse("Hey, are you working?", chosen_response)


@requiresuper
async def restart_command(user_command: UserCommand) -> CommandResponse:
    logger.info("Restarting...")
    await user_command.send_text_response("Restarting...")

    # Don't need to return anything because this line halts operation of the program
    os.execv(sys.executable, ['python', *sys.argv])


@requireadmin
async def system_command(_: UserCommand) -> CommandResponse:
    config = await common.Config.load()
    mem_usage = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')

    if config.misc.usemegabytes:
        divisor = 1024**2
        label = "MB"
    else:
        divisor = 1024**3
        label = "GB"

    mem_percent = round((mem_usage.used / mem_usage.total) * 100, 2)

    system_string = f"""SYSTEM RESOURCES
CPU: {psutil.cpu_percent(interval=0.5)}%
Memory: {mem_percent}% - {round(mem_usage.used / divisor, 2)} / {round(mem_usage.total / divisor, 2):,} {label}
Disk: {disk_usage.percent}% - {round(disk_usage.used / divisor, 2):,} / {round(disk_usage.total / divisor, 2):,} {label}
"""
    return CommandResponse("Can you show me your resource usage?", system_string)


@requireadmin
async def version_command(_: UserCommand) -> CommandResponse:
    user_message = "What script version are you running?"
    return CommandResponse(user_message, f"Running {common.APPLICATION_NAME} {common.VERSION_NUMBER}")


@requiresuper
async def crash_command(_: UserCommand) -> CommandResponse:
    error_message = "/crash command used"
    raise ZeroDivisionError(error_message)


@requiresuper
async def addadmin_command(user_command: UserCommand) -> CommandResponse:
    # This command lets you add new users to the admin list
    # It does NOT let you add new superadmins, that has to be done manually by editing the json file
    user_message = "Can you make this person an admin?"

    user_id = user_command.get_first_arg(lowercase=True)
    if user_id is None:
        return CommandResponse(user_message, "Who do you want me to make an admin?")

    admin_dict: dict[str, dict[str, list[str]]] = await common.try_read_json(common.PATH_ADMIN_LIST, {})
    platform_str = user_command.get_platform_string()

    if platform_str not in admin_dict:
        admin_dict[platform_str] = {"admin": [user_id]}

    elif "admin" not in admin_dict[platform_str]:
        admin_dict[platform_str]["admin"] = [user_id]

    elif user_id in admin_dict[platform_str]["admin"]:
        return CommandResponse(user_message, f"That user ID '{user_id}' is already on the admin list.")

    else:
        admin_dict[platform_str]["admin"].append(user_id)

    await common.write_json_to_file(common.PATH_ADMIN_LIST, admin_dict)
    return CommandResponse(user_message, f"Added new user ID '{user_id}' to admin list.")


@requiresuper
async def deladmin_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you remove this person from the admin list?"

    user_id = user_command.get_first_arg(lowercase=True)
    if user_id is None:
        return CommandResponse(user_message, "Who do you want me to remove from the admin list?")

    admin_dict: dict[str, dict[str, list[str]]] = await common.try_read_json(common.PATH_ADMIN_LIST, {})
    platform_str = user_command.get_platform_string()

    error_response = f"The user ID '{user_id}' is not on the admin list."
    if platform_str not in admin_dict:
        return CommandResponse(user_message, error_response)

    if "admin" not in admin_dict[platform_str]:
        return CommandResponse(user_message, error_response)

    if user_id not in admin_dict[platform_str]["admin"]:
        return CommandResponse(user_message, error_response)

    admin_dict[platform_str]["admin"] = [x for x in admin_dict[platform_str]["admin"] if x != user_id]
    await common.write_json_to_file(common.PATH_ADMIN_LIST, admin_dict)

    return CommandResponse(user_message, f"Removed user ID '{user_id}' from the admin list.")


@requiresuper
async def addwhitelist_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you add this chat ID to the whitelist?"

    chat_id = user_command.get_first_arg(lowercase=True)
    if chat_id is None:
        return CommandResponse(user_message, "What chat ID do you want me to add to the whitelist?")

    whitelist: dict[str, list[str]] = await common.try_read_json(common.PATH_WHITELIST, {})
    platform_str = user_command.get_platform_string()

    if platform_str not in whitelist:
        whitelist[platform_str] = [chat_id]

    elif chat_id not in whitelist[platform_str]:
        whitelist[platform_str].append(chat_id)

    else:
        return CommandResponse(user_message, f"The chat ID '{chat_id}' is already on the whitelist.")

    await common.write_json_to_file(common.PATH_WHITELIST, whitelist)
    return CommandResponse(user_message, f"Added new chat ID '{chat_id}' to the whitelist.")


@requiresuper
async def delwhitelist_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you remove this chat ID from the whitelist?"

    chat_id = user_command.get_first_arg(lowercase=True)
    if chat_id is None:
        return CommandResponse(user_message, "What chat ID do you want me to remove from the whitelist?")

    whitelist: dict[str, list[str]] = await common.try_read_json(common.PATH_WHITELIST, {})
    platform_str = user_command.get_platform_string()

    if platform_str not in whitelist or chat_id not in whitelist[platform_str]:
        return CommandResponse(user_message, f"The chat ID '{chat_id}' is not on the whitelist.")

    whitelist[platform_str] = [x for x in whitelist[platform_str] if x != chat_id]

    await common.write_json_to_file(common.PATH_WHITELIST, whitelist)
    return CommandResponse(user_message, f"Removed chat ID '{chat_id}' from the whitelist.")


@requireadmin
async def getuserid_command(user_command: UserCommand) -> CommandResponse:
    # Tells the user what their user ID is
    username = user_command.get_first_arg()
    if username is None:
        user_id = user_command.get_user_id()
        return CommandResponse("Can you tell me what my user ID is?", f"Your user ID is {user_id}.")

    user_message = f"What is {username}'s user ID?"
    user_id = await user_command.get_id_by_username(username.lower())

    if user_id is None:
        return CommandResponse(user_message, f"{username}'s user ID has not been tracked.")

    return CommandResponse(user_message, f"{username}'s user ID is {user_id}.")


@requireadmin
async def getchatid_command(user_command: UserCommand) -> CommandResponse:
    user_message = "Can you tell me what this chat's ID is?"
    chat_id = user_command.get_chat_id()

    return CommandResponse(user_message, f"This chat's ID is {chat_id}")


@requiresuper
async def getfile_command(user_command: UserCommand) -> CommandResponse:
    file_path = Path(user_command.get_user_message())
    user_message = "Can you send me that file?"

    if str(file_path) == '.':
        return CommandResponse(user_message, "Please provide the path to a file on my server.")

    user_message = f"Can you send me the file at {file_path}"
    if file_path.exists() and file_path.is_file():
        return FileResponse(user_message, "Sure, here you go.", file_path)

    return CommandResponse(user_message, "Couldn't find a file at that path.")
# endregion


# ==========================
# EVENTS
# ==========================
# region
async def discord_register_events(discord_bot: common.DiscordBotAnnotation) -> None:  # noqa: C901
    # This function assigns all of the event handlers to the discord bot

    @discord_bot.event
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:  # noqa: ARG001
        # This function automatically disconnects the bot if it's the only
        # member remaining in a voice channel
        config = await common.Config.load()

        if not config.chat.vcautodc:
            return

        try:
            bot_channel = discord_bot.voice_clients[0].channel
        except IndexError:
            return

        if not isinstance(bot_channel, discord.VoiceChannel):
            return

        if len(bot_channel.members) == 1:
            await discord_bot.voice_clients[0].disconnect(force=False)

    @discord_bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        if not isinstance(discord_bot.command_prefix, str):
            return

        if message.content.startswith(discord_bot.command_prefix):
            await discord_bot.process_commands(message)
            return

        message_handler = await common.wrap_discord_command(discord_bot, handle_message_event)
        context = await discord_bot.get_context(message)
        await message_handler(context)

    @discord_bot.event
    async def on_command_error(_, error: CommandInvokeError) -> None:  # noqa: ANN001
        error = getattr(error, "original", error)

        # Suppress the error that happens if you try to use a command that doesn't exist
        if isinstance(error, CommandNotFound):
            return

        raise error


async def handle_message_event(user_command: UserCommand) -> CommandResponse:
    config = await common.Config.load()
    bot_name = config.main.botname.lower()
    message = user_command.get_user_message().lower()

    response = NoResponse()
    if config.chat.replytomonkey and "monkey" in message:
        response = await monkey_event(message)

    elif config.chat.replytoname and (bot_name in message or ''.join(bot_name.split()) in message):
        response = await reply_event(user_command)  # Could have responding to name have a different functionality

    elif random.random() < config.chat.randreplychance:
        response = await reply_event(user_command)

    elif config.chat.recordall:
        user_prompt = await user_command.get_user_prompt()
        await common.append_to_gpt_memory(user_prompt=user_prompt)

    return response


async def monkey_event(message: str) -> CommandResponse:
    # Discworld adventure game reference
    return SoundResponse(message, bot_message="AAAAAHHHHH-EEEEE-AAAAAHHHHH!", file_path=common.PATH_SOUNDS_FOLDER / "monkey.mp3")


async def reply_event(user_command: UserCommand) -> CommandResponse:
    # Have GPT generate a response to the user's message
    response = await chat.get_gpt_response(user_command)
    return CommandResponse(user_command.get_user_message(), response)
# endregion


# List of all commands, add commands here to register them.
# The first item in each tuple is the name of the command (/name), and the second is
# the function that will be assigned to that name.
# Do NOT register any commands to this list that take a user file attachment as an input,
# those must be registered in FILE_COMMAND_LIST below or they won't work in Telegram
COMMAND_LIST: list[tuple[str, common.CommandAnnotation]] = [
    ("sound", sound_command),
    ("random", randomsound_command),
    ("soundlist", soundlist_command),
    ("playcount", playcount_command),
    ("topsounds", topsounds_command),
    ("botsounds", botsounds_command),
    ("newsounds", newsounds_command),
    ("delsound", delsound_command),
    ("addalias", addalias_command),
    ("delalias", delalias_command),
    ("getalias", getalias_command),
    ("search", search_command),
    ("say", say_command),
    ("stream", stream_command),
    ("pressf", pressf_command),
    ("wisdom", wisdom_command),
    ("buildmarkov", buildmarkov_command),
    ("help", help_command),
    ("chat", chat_command),
    ("test", test_command),
    ("lobotomize", lobotomize_command),
    ("memory", memory_command),
    ("logs", logs_command),
    ("clearlogs", clearlogs_command),
    ("vcsound", vcsound_command),
    ("vcrandom", vcrandom_command),
    ("vcstop", vcstop_command),
    ("vcjoin", vcjoin_command),
    ("vcleave", vcleave_command),
    ("vcstream", vcstream_command),
    ("vcpause", vcpause_command),
    ("vcsay", vcsay_command),
    ("roll", roll_command),
    ("statroll", statroll_command),
    ("d10000", d10000_command),
    ("effects", effects_command),
    ("reseteffects", reset_effects_command),
    ("trivia", trivia_command),
    ("guess", guess_command),
    ("triviarank", triviarank_command),
    ("getconfig", getconfig_command),
    ("setconfig", setconfig_command),
    ("configlist", configlist_command),
    ("restart", restart_command),
    ("system", system_command),
    ("version", version_command),
    ("crash", crash_command),
    ("addadmin", addadmin_command),
    ("deladmin", deladmin_command),
    ("addwhitelist", addwhitelist_command),
    ("delwhitelist", delwhitelist_command),
    ("getuserid", getuserid_command),
    ("getchatid", getchatid_command),
    ("getfile", getfile_command),
    ("mycommands", mycommands_command),
]

# For the Telegram API, normal commands cannot accept a file as an input for some reason,
# so we have to register them differently
FILE_COMMAND_LIST: list[tuple[str, common.CommandAnnotation]] = [
    ("addsound", addsound_command),
]


def check_unregistered_commands() -> Generator[str]:
    cmd_list = [*(cmd[1] for cmd in COMMAND_LIST), *(cmd[1] for cmd in FILE_COMMAND_LIST)]
    for obj in globals().values():
        if not isinstance(obj, Callable):
            continue

        obj_name = obj.__name__
        if obj_name.endswith("_command") and obj not in cmd_list:
            yield f"Function '{obj_name}' is not registered in COMMAND_LIST or FILE_COMMAND_LIST"
