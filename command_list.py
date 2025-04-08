import os
import sys
import random
from subprocess import Popen, PIPE, STDOUT
from typing import Callable
import discord
from discord.ext import commands as discord_commands
from discord.ext.commands import CommandInvokeError, Bot as DiscordBot
from discord.errors import HTTPException
from telegram.ext import MessageHandler, filters, CommandHandler, Application as TelegramBot
from telegram.error import BadRequest, TimedOut, NetworkError
from loguru import logger
import psutil
import sound_manager
import chat
import settings
import dice_roller
import trivia
import common
from common import CommandResponse, FileResponse, SoundResponse, NoPermissionsResponse, NoResponse, ChatCommand

# ==========================
# RESPONSE HANDLERS
# ==========================
#region
async def send_response(command: Callable, chat_command: ChatCommand) -> None:
    config = settings.Config()
    command_response: CommandResponse = await command(chat_command)

    if command_response.send_to_chat and command_response.bot_message:
        text_response = command_response.bot_message

        if len(text_response) > config.main.maxmessagelength:
            text_response = text_response[:config.main.maxmessagelength]
            logger.info(f"Cut off bot response at {config.main.maxmessagelength} characters")

    else:
        text_response = None

    try:
        # Respond with a sound effect
        if isinstance(command_response, SoundResponse):
            await chat_command.send_sound_response(command_response, text_response)

        # Respond with a file
        elif isinstance(command_response, FileResponse):
            await chat_command.send_file_response(command_response, text_response)

        # Respond with text
        elif text_response:
            await chat_command.send_text_response(text_response)

    except (BadRequest, TimedOut, NetworkError, HTTPException) as e:
        logger.error(e)
        error_response = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"
        await chat_command.send_text_response(error_response)

    # Add the command and its response to memory if necessary
    if command_response.record_to_memory:
        user_prompt = chat.generate_user_prompt(command_response.user_message, chat_command)
        chat.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

def command_wrapper(bot: TelegramBot | DiscordBot, command: Callable) -> Callable:
    if isinstance(bot, TelegramBot):
        async def wrapper_function(update, context): # type: ignore
            chat_command = ChatCommand(bot, context, update=update)

            if not chat_command.is_whitelisted():
                # Telegram doesn't allow you to make "private" bots, meaning anyone can add your bot to their chat
                # and use up your CPU time. This check prevents the bot from responding to commands unless it comes
                # from a whitelisted chat
                logger.warning(f"whitelist rejected {update.message.chat.id}")
                return

            await send_response(command, chat_command)

    elif isinstance(bot, DiscordBot):
        async def wrapper_function(context):
            chat_command = ChatCommand(bot, context)
            await send_response(command, chat_command)

    return wrapper_function

def register_commands(bot: TelegramBot | DiscordBot):
    # List of all commands, add commands here to register them.
    # The first item in each tuple is the name of the command, and the second is
    # the function that will be assigned to that name
    command_list = [
        ("sound", sound_command),
        ("random", randomsound_command),
        ("soundlist", soundlist_command),
        ("playcount", playcount_command),
        ("topsounds", topsounds_command),
        ("botsounds", botsounds_command),
        ("newsounds", newsounds_command),
        ("addalias", addalias_command),
        ("delalias", delalias_command),
        ("getalias", getalias_command),
        ("search", search_command),
        ("pressf", pressf_command),
        ("wisdom", wisdom_command),
        ("help", help_command),
        ("chat", chat_command),
        ("test", test_command),
        ("lobotomize", lobotomize_command),
        ("memory", memory_command),
        ("memorylist", memorylist_command),
        ("logs", logs_command),
        ("vcsound", vcsound_command),
        ("vcrandom", vcrandom_command),
        ("vcstop", vcstop_command),
        ("vcjoin", vcjoin_command),
        ("vcleave", vcleave_command),
        ("vcstream", vcstream_command),
        ("vcpause", vcpause_command),
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
        ("terminal", terminal_command),
        ("version", version_command),
        ("crash", crash_command),
        ("addadmin", addadmin_command),
        ("deladmin", deladmin_command),
        ("addwhitelist", addwhitelist_command),
        ("delwhitelist", delwhitelist_command)
    ]

    if isinstance(bot, TelegramBot):
        for command in command_list:
            bot.add_handler(CommandHandler(command[0], command_wrapper(bot, command[1])))

        bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), command_wrapper(bot, handle_message_event)))

    elif isinstance(bot, DiscordBot):
        for command in command_list:
            new_command = discord_commands.Command(command_wrapper(bot, command[1]))
            new_command.name = command[0]
            bot.add_command(new_command)

        discord_register_events(bot)

    else:
        raise NotImplementedError
#endregion

# ==========================
# SOUND PLAYER COMMANDS
# ==========================
#region
async def sound_command(chat_command: ChatCommand) -> CommandResponse:
    sound_name = chat_command.get_first_arg(lowercase=True)

    # Alert the user if they forgot to provide a sound name
    if sound_name is None:
        return CommandResponse("Can you play that sound for me?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    # Parse the arguments the user provided for the sound name
    sound_results = sound_manager.get_sound(sound_name)

    user_message = f"Can you play the {sound_name} sound for me?"

    # Alert the user if the sound they requested does not exist
    if sound_results is None:
        return CommandResponse(user_message, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    if isinstance(sound_results, list):
        num_candidates = len(sound_results)
        candidate_string = ', '.join(sound_results)
        return CommandResponse(user_message, f"There are {num_candidates} potential matches: {candidate_string}")

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return CommandResponse(user_message, "You know, I'm just not feeling it right now.")

    # If the sound was requested in a non-private chat, then we'll update the playcount for this sound
    if not chat_command.is_private():
        await sound_manager.increment_playcount(sound_name)

    return SoundResponse(user_message, f"Sure, here's the {sound_name} sound.", sound_results)

async def randomsound_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you play a random sound for me?"

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return CommandResponse(user_message, "You know, I'm just not feeling it right now.")

    sound_name, sound_path = sound_manager.get_random_sound()

    # If the sound was requested in a group chat, then we update the playcount for this sound
    if not chat_command.is_private():
        await sound_manager.increment_playcount(sound_name)

    return SoundResponse(user_message, f"Sure, here you go. The sound I chose is called '{sound_name}'.", sound_path)

async def soundlist_command(chat_command: ChatCommand) -> CommandResponse:
    txt_path, count = sound_manager.get_sound_list_txt()
    response = f"There are {count} sounds available to use. Here's a text file with all of them listed out."

    return FileResponse("How many sounds are available to use? Can you list them for me?", response, txt_path, temp=True)

async def newsounds_command(chat_command: ChatCommand) -> CommandResponse:
    playcount_dict = sound_manager.get_playcount_dict()
    new_sounds = [sound for sound in playcount_dict if playcount_dict[sound] == 0]
    new_count = len(new_sounds)
    list_string = ', '.join(new_sounds)

    user_message = "How many new sounds are available?"

    if new_count == 0:
        return CommandResponse(user_message, "There are no new sounds available.")

    if new_count == 1:
        return CommandResponse(user_message, f"There is one new sound available: {list_string}")

    return CommandResponse(user_message, f"There are {new_count} new sounds available:\n\n{list_string}")

async def addalias_command(chat_command: ChatCommand) -> CommandResponse:
    # Verify that the user is on the admin list
    if not chat_command.is_admin():
        return NoPermissionsResponse("Can you add a new sound alias?")

    args_list = chat_command.get_args_list()

    # Attempt to parse the new alias and target sound from the arguments provided
    try:
        new_alias = args_list[0]
        sound_name = args_list[1]

    except IndexError:
        return CommandResponse("Can you add a new sound alias?", "Format is /addalias [new alias] [sound name]")

    response = sound_manager.add_sound_alias(new_alias, sound_name)
    return CommandResponse(f"Can you make '{new_alias}' an alias for the sound '{sound_name}'?", response)

async def delalias_command(chat_command: ChatCommand) -> CommandResponse:
    # Verify that the user is on the admin list
    if not chat_command.is_admin():
        return NoPermissionsResponse("Can you delete a sound alias for me?")

    alias_to_delete = chat_command.get_first_arg(lowercase=True)
    if alias_to_delete is None:
        return CommandResponse("Can you delete a sound alias for me?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    response = await sound_manager.del_sound_alias(alias_to_delete)
    return CommandResponse(f"Can you delete the sound alias '{alias_to_delete}'?", response)

async def getalias_command(chat_command: ChatCommand) -> CommandResponse:
    sound_name = chat_command.get_first_arg(lowercase=True)
    if sound_name is None:
        return CommandResponse("How many aliases does that sound have?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    user_prompt = f"How many aliases does the sound '{sound_name}' have?"

    if not sound_manager.sound_exists(sound_name):
        return CommandResponse(user_prompt, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    aliases = sound_manager.get_aliases(sound_name)
    num_alias = len(aliases)
    join_string = "', '"
    alias_string = f"'{join_string.join(aliases)}'"

    if num_alias == 1:
        return CommandResponse(user_prompt, f"The sound '{sound_name}' has one alias: {alias_string}")

    elif num_alias > 1:
        return CommandResponse(user_prompt, f"The sound '{sound_name}' has {num_alias} aliases: {alias_string}")

    else:
        return CommandResponse(user_prompt, f"The sound '{sound_name}' has no assigned aliases")

async def search_command(chat_command: ChatCommand) -> CommandResponse:
    try:
        search_string = ''.join(chat_command.get_args_list()).lower()

    except IndexError:
        return CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    if not search_string:
        return CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    search_results = sound_manager.search_sounds(search_string)

    num_matches = len(search_results)
    list_string = f"\n\n{', '.join(search_results)}"

    user_prompt = f"Can you search for sounds containing '{search_string}'?"

    if num_matches == 0:
        return CommandResponse(user_prompt, f"There are no sounds matching '{search_string}'")

    if num_matches == 1:
        return CommandResponse(user_prompt, f"There is one sound matching '{search_string}': {list_string}")

    if num_matches > 100:
        return CommandResponse(user_prompt, f"There are more than 100 sounds matching '{search_string}', try a more specific search")

    return CommandResponse(user_prompt, f"There are {num_matches} sounds matching '{search_string}': {list_string}")


async def playcount_command(chat_command: ChatCommand) -> CommandResponse:
    sound_name = chat_command.get_first_arg(lowercase=True)
    if sound_name is None:
        return CommandResponse("How many times has that sound been played?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    sound_aliases = sound_manager.get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    user_prompt = f"How many times has the sound {sound_name} been played?"

    if sound_name not in sound_manager.get_sound_dict():
        return CommandResponse(user_prompt, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    playcount = sound_manager.get_playcount_dict()[sound_name]
    return CommandResponse(user_prompt, f"/sound {sound_name} has been used {playcount} times")

async def topsounds_command(chat_command: ChatCommand) -> CommandResponse:
    play_counts = sound_manager.get_playcount_dict()
    list_size = 20
    top_sounds = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_sounds)
    return CommandResponse(f"What are the {list_size} most played sounds?", f"The {list_size} most played sounds are:\n{message}")

async def botsounds_command(chat_command: ChatCommand) -> CommandResponse:
    play_counts = sound_manager.get_playcount_dict()
    list_size = 20
    bot_sounds = sorted(play_counts, key=lambda x: play_counts[x])[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in bot_sounds)
    return CommandResponse(f"What are the {list_size} least played sounds?", f"The {list_size} least used sounds are:\n{message}")
#endregion

# ==========================
# TEXT CHAT COMMANDS
# ==========================
#region
async def chat_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = chat_command.get_user_message()

    # Have GPT generate a response to the user's message
    response = chat.get_gpt_response(user_message, chat_command)

    return CommandResponse(user_message, response)

async def wisdom_command(chat_command: ChatCommand) -> CommandResponse:
    response = chat.generate_markov_text()
    bot_name = settings.Config().main.botname
    return CommandResponse(f"O, wise and powerful {bot_name}, please grant me your wisdom!", response)

async def pressf_command(chat_command: ChatCommand) -> CommandResponse:
    return CommandResponse("F's in the chat boys.", "F")
#endregion

# ==========================
# VOICE CHAT COMMANDS
# ==========================
#region
async def vcsound_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Hey, play that sound in the voice channel."

    if chat_command.update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry")

    if chat_command.context.voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    sound_name = chat_command.get_first_arg(lowercase=True)

    # Alert the user if they forgot to provide a sound name
    if sound_name is None:
        return CommandResponse(user_message, random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    sound_results = sound_manager.get_sound(sound_name)

    user_message = f"Can you play the {sound_name} sound in the voice channel?"

    # Alert the user if the sound they requested does not exist
    if sound_results is None:
        return CommandResponse(user_message, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    if isinstance(sound_results, list):
        num_candidates = len(sound_results)
        candidate_string = ', '.join(sound_results)
        return CommandResponse(user_message, f"There are {num_candidates} potential matches: {candidate_string}")

    # Stop the voice client if it's already playing a sound or stream
    if chat_command.context.voice_client.is_playing():
        chat_command.context.voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_results))

    chat_command.context.voice_client.play(source, after=lambda e: logger.error(e) if e else None)

    await sound_manager.increment_playcount(sound_name)
    return CommandResponse(user_message, "Sure, here you go", send_to_chat=False)

async def vcrandom_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you play a random sound for me?"

    if chat_command.update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry!")

    if chat_command.context.voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    sound_name, sound_path = sound_manager.get_random_sound()

    # Stop the voice client if it's already playing a sound or stream
    if chat_command.context.voice_client.is_playing():
        chat_command.context.voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))
    chat_command.context.voice_client.play(source, after=lambda e: logger.error(e) if e else None)

    await sound_manager.increment_playcount(sound_name)
    return CommandResponse(user_message, f"Sure, I chose the sound '{sound_name}", send_to_chat=False)

async def vcstop_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Stop making all that noise please."
    if chat_command.update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry!")

    try:
        chat_command.context.voice_client.stop()
    except (AttributeError, TypeError, CommandInvokeError):
        # For some reason this can throw a lot of exceptions, we just ignore them
        pass

    return CommandResponse(user_message, "If you insist.", send_to_chat=False)

async def vcstream_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Stream this for me please."
    if chat_command.update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry!")

    if chat_command.context.voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    try:
        stream_url = chat_command.get_user_message()
    except IndexError:
        return CommandResponse(user_message, "Provide a streamable URL please!")

    # Stop the voice client if it's already playing a sound or stream
    if chat_command.context.voice_client.is_playing():
        chat_command.context.voice_client.stop()

    # Create a stream player from the provided URL
    stream_player = sound_manager.YTDLStream(stream_url)

    if stream_player is None:
        return CommandResponse(user_message, "There was an error streaming from that URL.")

    # Play the stream through the voice client
    async with chat_command.context.typing():
        chat_command.context.voice_client.play(stream_player, after=lambda e: logger.error(e) if e else None)

    return CommandResponse(user_message, f"Now playing: {stream_player.title}")

async def vcpause_command(chat_command: ChatCommand):
    user_message = "Please toggle pause on the voice stream."
    if chat_command.update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry!")

    if chat_command.context.voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    # Stop the voice client if it's already playing a sound or stream
    if not chat_command.context.voice_client.is_paused() and not chat_command.context.voice_client.is_playing():
        return CommandResponse(user_message, "Nothing is playing!")

    if chat_command.context.voice_client.is_paused():
        chat_command.context.voice_client.resume()

        return CommandResponse(user_message, "Done.", send_to_chat=False)

    chat_command.context.voice_client.pause()
    return CommandResponse(user_message, "Done.", send_to_chat=False)

async def vcjoin_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Join my voice channel please."
    if chat_command.update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry!")

    target_voice = chat_command.context.author.voice

    if target_voice is None:
        return CommandResponse(user_message, "You're not in a voice channel!")

    if chat_command.context.voice_client is not None:
        await chat_command.context.voice_client.move_to(target_voice.channel)

    else:
        await target_voice.channel.connect()

    return CommandResponse(user_message, "If you insist.", send_to_chat=False)

async def vcleave_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Leave the current voice channel please."
    if chat_command.update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry!")

    try:
        await chat_command.context.voice_client.disconnect()
        chat_command.context.voice_client.cleanup()
    except (AttributeError, CommandInvokeError):
        pass

    return CommandResponse(user_message, "If you insist", send_to_chat=False)
#endregion

# ==========================
# DICE ROLLER COMMANDS
# ==========================
#region
async def roll_command(chat_command: ChatCommand) -> CommandResponse:
    parsed_roll = dice_roller.parse_diceroll(chat_command.get_args_list())

    if parsed_roll is None:
        return CommandResponse("Can you roll some dice for me?", "Please use dice notation like a civilized humanoid, e.g. '3d6 + 2'")

    num_dice, num_faces, modifier = parsed_roll

    if modifier > 0:
        roll_text = f"{num_dice}d{num_faces} + {modifier}"
    elif modifier < 0:
        roll_text = f"{num_dice}d{num_faces} - {abs(modifier)}"
    else:
        roll_text = f"{num_dice}d{num_faces}"

    user_prompt = f"Can you roll a {roll_text} for me?"

    config = settings.Config()
    if num_dice > config.main.maxdice:
        return CommandResponse(user_prompt, f"Keep it to {config.main.maxdice:,} dice or fewer please, I'm not a god.")

    if num_faces > config.main.maxfaces:
        return CommandResponse(user_prompt, f"Keep it to {config.main.maxfaces:,} sides or fewer please, I'm not a god.")

    rolls = []
    for _ in range(num_dice):
        this_roll = random.randint(1, num_faces)
        rolls.append(this_roll)

    if modifier != 0 or num_dice > 1:
        dice_text = ', '.join(str(x) for x in rolls)
        dice_text = f"({dice_text})"

    else:
        dice_text = ""

    sender = chat_command.get_author()

    return CommandResponse(user_prompt, f"{sender} rolled a {sum(rolls) + modifier:,} {dice_text}")

async def statroll_command(chat_command: ChatCommand) -> CommandResponse:
    game_functions = {
        "dnd": dice_roller.get_dnd_roll,
        "coc": dice_roller.get_coc_roll,
        "mythras": dice_roller.get_mythras_roll
    }

    error_response = f"Please supply a valid game name. Options are {', '.join(game_functions.keys())}"

    game = chat_command.get_first_arg(lowercase=True)
    if game is None:
        return CommandResponse("Can you roll me a tabletop character?", error_response)

    user_prompt = f"Can you roll me a character for {game}?"

    try:
        roll_string = game_functions[game]()
    except KeyError:
        return CommandResponse(user_prompt, error_response)

    return CommandResponse(user_prompt, roll_string)

async def d10000_command(chat_command: ChatCommand) -> CommandResponse:
    username = chat_command.get_author()
    effect = dice_roller.get_d10000_roll(username)
    return CommandResponse("Can you roll an effect on the d10000 table?", effect)

async def effects_command(chat_command: ChatCommand) -> CommandResponse:
    username = chat_command.get_author()
    active_effects = dice_roller.get_active_effects(username)

    if active_effects:
        effects_string = '\n    '.join(active_effects)
        response = f"Here are {username}'s active effects:\n    {effects_string}"
    else:
        response = "You don't have any active effects, use the /d10000 command to get some!"

    return CommandResponse("Can I get a list of my active d10000 effects?", response)

async def reset_effects_command(chat_command: ChatCommand):
    username = chat_command.get_author()
    dice_roller.reset_active_effects(username)

    return CommandResponse("Can you reset my active d10000 effects?", f"Active effects reset for {username}.")
#endregion

# ==========================
# TRIVIA COMMANDS
# ==========================
#region
async def trivia_command(chat_command: ChatCommand) -> CommandResponse:
    trivia_question = trivia.get_trivia_question()

    return CommandResponse("Can you give me a trivia question?", trivia_question.get_question_string())

async def guess_command(chat_command: ChatCommand) -> CommandResponse:
    guess = chat_command.get_user_message()
    user_message = f"Is the trivia answer {guess}?"

    if (current_question := trivia.get_current_question()) is None:
        return CommandResponse(user_message, "Trivia is not active!")

    if not guess:
        return CommandResponse(user_message, "You need to provide an answer, like /guess abc")

    if current_question.is_guess_correct(guess):
        points_gained = current_question.score_question(True, chat_command)
        player_name = chat_command.get_author()
        return CommandResponse(user_message, f"That is correct, the answer was '{current_question.correct_answer}'. {player_name} earned {points_gained} points!")

    if current_question.is_guess_on_list(guess):
        current_question.score_question(False, chat_command)
        if current_question.guesses_left > 0:
            return CommandResponse(user_message, f"That is incorrect, {current_question.guesses_left} guesses remaining.")

        return CommandResponse(user_message, f"That is incorrect! Out of guesses, the answer was {current_question.correct_answer}!")

    return CommandResponse(user_message, "That isn't an option for this question!")

async def triviarank_command(chat_command: ChatCommand):
    points_dict = common.try_read_json(trivia.TRIVIA_POINTS_PATH, dict())
    ranking = sorted(points_dict, key=lambda x: points_dict[x], reverse=True)

    message = '\n'.join(f'    {index + 1}. {player} @ {points_dict[player]:,} points' for index, player in enumerate(ranking))
    return CommandResponse("What are the current trivia rankings?", f"The trivia rankings are:\n{message}")
#endregion

# ==========================
# MEMORY COMMANDS
# ==========================
#region
async def lobotomize_command(chat_command: ChatCommand) -> CommandResponse:
    # Clears the bot's AI memory
    try:
        os.remove(chat.MEMORY_PATH)
    except FileNotFoundError:
        pass

    msg_options = ["My mind has never been clearer.", "Hey, what happened to those voices in my head?", "My inner demons seem to have calmed down a bit."]
    return CommandResponse('', random.choice(msg_options), record_to_memory=False)

async def memory_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you send me your memory file?"
    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    if not os.path.exists(chat.MEMORY_PATH):
        return CommandResponse(user_message, "My mind is a blank slate.")

    return FileResponse(user_message, "Sure, here's my memory file.", chat.MEMORY_PATH)

async def memorylist_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you send me your memory as a list?"
    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    memory_list = chat.load_memory()

    if not memory_list:
        return CommandResponse(user_message, "My mind is a blank slate.")

    memory_list = [f"{item['role']}: {item['content']}" for item in memory_list if 'content' in item]

    temp_path = 'Data/mem_list.txt'
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(memory_list))

    return FileResponse(user_message, "Sure, here's my memory list.", temp_path, temp=True)
#endregion

# ==========================
# SETTINGS/CONFIG COMMANDS
# ==========================
#region
async def getconfig_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you tell me the value of that setting?"
    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    search_string = chat_command.get_first_arg(lowercase=True)
    if search_string is None:
        return CommandResponse(user_message, "You need to provide a setting name to check.")

    config = settings.Config()
    group_name, setting_name, value = config.find_setting(search_string)

    user_message = f"Can you tell me the value of the setting {search_string}?"
    if value is None:
        return CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    return CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' is currently set to '{value}'.")

async def setconfig_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you change the value of that setting?"
    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    args_list = chat_command.get_args_list()

    try:
        search_string = args_list[0]
        new_value = ' '.join(args_list[1:])
    except IndexError:
        return CommandResponse(user_message, "Format is /setconfig [setting] [new value]")

    if not new_value:
        return CommandResponse(user_message, "Format is /setconfig [setting] [new value]")

    config = settings.Config()
    group_name, setting_name, _ = config.find_setting(search_string)

    user_message = f"Can you change the value of the setting {search_string}?"
    if group_name is None or setting_name is None:
        return CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    new_value = settings.parse_value_input(new_value)

    setattr(getattr(config, group_name), setting_name, new_value)
    settings.save_config(config)

    return CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' has been set to '{new_value}'.")

async def configlist_command(chat_command: ChatCommand) -> CommandResponse:
    config = settings.Config()

    setting_list = []
    for group in config.__dict__:
        for setting in getattr(config, group).__dict__:
            setting_list.append(f"{group}.{setting}")

    setting_list = '\n-- '.join(setting_list)
    return CommandResponse('', f"Here is a list of all available settings: \n-- {setting_list}")
#endregion

# ==========================
# OTHER COMMANDS
# ==========================
#region
async def help_command(chat_command: ChatCommand) -> CommandResponse:
    help_string = """\
Look upon my works, ye mighty, and despair:
/vcjoin and /vcleave (join or leave current voice channel)
/sound and /vcsound (play a sound effect)
/random and /vcrandom (play a random sound effect)
/soundlist and /search (find sounds to play)
/trivia (play trivia against your friends)
/chat (talk to me)
/wisdom (request my wisdom)
/roll (roll a dice)
/d10000 and /effects (roll the d10000 table)
/pressf (pay respects)"""

    return CommandResponse("What chat commands are available?", help_string)

async def logs_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you send me your error log?"
    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    if not os.path.exists(common.LOGGING_FILE_PATH):
        return CommandResponse(user_message, "There are no logs recorded.")

    return FileResponse("Can you send me your error log?", "Sure, here you go.", common.LOGGING_FILE_PATH)

async def test_command(chat_command: ChatCommand) -> CommandResponse:
    # This command is for verifying that the bot is online and receiving commands.
    # You can also supply it with a list of responses and it will pick a random one
    # I think of this as similar to how RTS units say things when you click them
    response_list = common.try_read_lines(common.RESPONSES_PATH, [])
    response_list = [line for line in response_list if not line.isspace() and not line.startswith("#")]

    if not response_list:
        CommandResponse("Hey, are you working?", "I'm still alive, unfortunately.")

    chosen_response = random.choice(response_list)
    if chosen_response.startswith('f"') or chosen_response.startswith("f'"):
        chosen_response = eval(chosen_response)

    return CommandResponse("Hey, are you working?", chosen_response)

async def restart_command(chat_command: ChatCommand) -> CommandResponse:
    if not chat_command.is_admin():
        return NoPermissionsResponse("Can you restart your script for me?")

    logger.info("Restarting...")
    await chat_command.send_text_response("Restarting...")

    os.execv(sys.executable, ['python'] + sys.argv)

async def system_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you show me your resource usage?"
    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    config = settings.Config()
    mem_usage = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')

    if config.main.usemegabytes:
        divisor = 1024**2
        label = "MB"
    else:
        divisor = 1024**3
        label = "GB"

    mem_percent = round(mem_usage.used/mem_usage.total*100, 2)

    system_string = f"""SYSTEM RESOURCES
CPU: {psutil.cpu_percent(interval=0.5)}%
Memory: {mem_percent}% - {round(mem_usage.used/divisor, 2)} / {round(mem_usage.total/divisor, 2):,} {label}
Disk: {disk_usage.percent}% - {round(disk_usage.used/divisor, 2):,} / {round(disk_usage.total/divisor, 2):,} {label}
"""
    return CommandResponse("What's your resource usage at?", system_string)

async def terminal_command(chat_command: ChatCommand) -> CommandResponse:
    if not chat_command.is_admin():
        return NoResponse()

    command_string = chat_command.get_user_message()

    if not command_string:
        return CommandResponse("Can you run a command in your terminal?", "What command do you want me to run?")

    with Popen(command_string, stdin=PIPE, stdout=PIPE, stderr=STDOUT, shell=True) as process:
        # If asked a y/n question, automatically respond with y
        config = settings.Config()
        if config.main.cmdautoyes and process.stdin is not None:
            process.stdin.write(b'y')

        stdout = process.communicate()[0]

    user_message = f"Can you run this command: {command_string}"
    if stdout:
        return CommandResponse(user_message, stdout.decode())

    return CommandResponse(user_message, "Done.")

async def version_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "What script version are you running?"
    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    return CommandResponse(user_message, f"Running {common.APPLICATION_NAME} {common.VERSION_NUMBER}")

async def crash_command(chat_command: ChatCommand) -> CommandResponse:
    if not chat_command.is_admin():
        return NoPermissionsResponse("This statement is false.")

    raise ZeroDivisionError("/crash command used")

async def addadmin_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you make this person an admin?"

    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    user_id = chat_command.get_first_arg(lowercase=True)
    if user_id is None:
        return CommandResponse(user_message, "Who do you want me to make an admin?")

    admin_list = common.try_read_lines(common.ADMINS_PATH, [])

    if user_id in admin_list:
        return CommandResponse(user_message, f"That user ID '{user_id}' is already on the admin list.")

    admin_list.append(user_id)
    common.write_lines_to_file(common.ADMINS_PATH, admin_list)

    return CommandResponse(user_message, f"Added new user ID '{user_id}' to admin list.")

async def deladmin_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you remove this person from the admin list?"

    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    user_id = chat_command.get_first_arg(lowercase=True)
    if user_id is None:
        return CommandResponse(user_message, "Who do you want me to remove from the admin list?")

    admin_list = common.try_read_lines(common.ADMINS_PATH, [])

    if user_id not in admin_list:
        return CommandResponse(user_message, f"That user ID '{user_id}' is not on the admin list.")

    admin_list = [x for x in admin_list if x != user_id]
    common.write_lines_to_file(common.ADMINS_PATH, admin_list)

    return CommandResponse(user_message, f"Removed user ID '{user_id}' from the admin list.")

async def addwhitelist_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you add this chat ID to the whitelist?"

    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    chat_id = chat_command.get_first_arg(lowercase=True)
    if chat_id is None:
        return CommandResponse(user_message, "What chat ID do you want me to add to the whitelist?")

    whitelist = common.try_read_lines(common.TELEGRAM_WHITELIST_PATH, [])

    if chat_id in whitelist:
        return CommandResponse(user_message, f"The chat ID '{chat_id}' is already on the whitelist.")

    whitelist.append(chat_id)
    common.write_lines_to_file(common.TELEGRAM_WHITELIST_PATH, whitelist)

    return CommandResponse(user_message, f"Added new chat ID '{chat_id}' to the whitelist.")

async def delwhitelist_command(chat_command: ChatCommand) -> CommandResponse:
    user_message = "Can you remove this chat ID from the whitelist?"

    if not chat_command.is_admin():
        return NoPermissionsResponse(user_message)

    chat_id = chat_command.get_first_arg(lowercase=True)
    if chat_id is None:
        return CommandResponse(user_message, "What chat ID do you want me to remove from the whitelist?")

    whitelist = common.try_read_lines(common.TELEGRAM_WHITELIST_PATH, [])

    if chat_id not in whitelist:
        return CommandResponse(user_message, f"The chat ID '{chat_id}' is not on the whitelist.")

    whitelist = [x for x in whitelist if x != chat_id]
    common.write_lines_to_file(common.TELEGRAM_WHITELIST_PATH, whitelist)

    return CommandResponse(user_message, f"Removed chat ID '{chat_id}' from the whitelist.")
#endregion

# ==========================
# EVENTS
# ==========================
#region
def discord_register_events(discord_bot: DiscordBot):
    # This function assigns all of the event handlers to the discord bot

    @discord_bot.event
    async def on_voice_state_update(member, before, after):
        # This function automatically disconnects the bot if it's the only
        # member remaining in a voice channel
        config = settings.Config()

        if not config.main.vcautodc:
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
    async def on_message(message):
        if message.content.startswith(discord_bot.command_prefix):
            await discord_bot.process_commands(message)
            return

        message_handler = command_wrapper(discord_bot, handle_message_event)
        context = await discord_bot.get_context(message)
        await message_handler(context)

async def handle_message_event(chat_command: ChatCommand) -> CommandResponse:
    config = settings.Config()
    bot_name = config.main.botname.lower()

    if isinstance(chat_command.context, discord_commands.Context):
        if chat_command.context.author.bot:
            return NoResponse()

    message = chat_command.get_user_message()
    response = NoResponse()

    if config.main.replytomonkey and "monkey" in message:
        response = await monkey_event(message)

    elif config.main.replytoname and (bot_name in message or ''.join(bot_name.split()) in message):
        response = await reply_event(chat_command)

    elif random.random() < config.main.randreplychance:
        response = await reply_event(chat_command)

    elif config.main.recordall:
        user_prompt = chat.generate_user_prompt(message, chat_command)
        chat.append_to_memory(user_prompt=user_prompt)

    return response

async def monkey_event(message) -> CommandResponse:
    # Discworld adventure game reference
    return SoundResponse(message, bot_message="AAAAAHHHHH-EEEEE-AAAAAHHHHH!", file_path="Sounds/monkey.mp3")

async def reply_event(chat_command: ChatCommand):
    user_message = chat_command.get_user_message()
    # Have GPT generate a response to the user's message
    response = chat.get_gpt_response(user_message, chat_command)
    return CommandResponse(user_message, response)
#endregion
