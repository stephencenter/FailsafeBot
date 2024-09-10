import os
import sys
import random
from datetime import datetime
from subprocess import Popen, PIPE, STDOUT
from typing import Callable
from telegram.ext import MessageHandler, filters, CommandHandler, Application as TelegramBot
from telegram.error import BadRequest, TimedOut, NetworkError
import discord
from discord.ext import commands as discord_commands
from discord.ext.commands import CommandInvokeError, Bot as DiscordBot
from discord.errors import HTTPException
import psutil
import sound_manager
import chat
import settings
import dice_roller
import helpers
import trivia

LOGGING_DIR_PATH = os.path.join("Data", "logging")
LOGGING_FILE_PATH = os.path.join(LOGGING_DIR_PATH, "log.txt")
VERSION_NUMBER = 'v1.0.4'
RESPONSES_PATH = "Data/response_list.txt"

# ==========================
# RESPONSE CLASSES
# ==========================
#region
class CommandResponse:
    def __init__(self, user_message: str, bot_message: str, record_to_memory: bool = True, send_to_chat: bool = True):
        self.user_message: str = user_message
        self.bot_message: str = bot_message
        self.record_to_memory: bool = record_to_memory  # Whether user_message and bot_message should be recorded to memory
        self.send_to_chat: bool = send_to_chat  # Whether bot_message should be printed in chat

class FileResponse(CommandResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True, temp: bool = False):
        super().__init__(user_message, bot_message, record_to_memory=record_to_memory, send_to_chat=True)
        self.file_path: str = file_path  # The path of the file to send
        self.temp: bool = temp  # Whether the file should be deleted after being sent

class SoundResponse(FileResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True):
        super().__init__(user_message, bot_message, file_path, record_to_memory, False)

class NoResponse(CommandResponse):
    def __init__(self):
        super().__init__('', '', record_to_memory=False, send_to_chat=False)
#endregion

# ==========================
# RESPONSE HANDLERS
# ==========================
#region
def telegram_handler(command: Callable) -> Callable:
    # This function creates command handlers for the telegram bot.
    # Provide this function with a command function and it will create a wrapper
    # for that command function and return it. This wrapper automatically handles
    # the bot's response to the command and writes it to memory if necessary
    async def wrapper_function(update, context):
        # Telegram doesn't allow you to make "private" bots, meaning anyone can add your bot to their chat
        # and use up your CPU time. This check prevents the bot from responding to commands unless it comes
        # from a whitelisted chat
        if not helpers.is_whitelisted(context, update):
            print("rejected", update.message.chat.id, datetime.now())
            return

        command_response: CommandResponse = await command(context, update=update)

        if isinstance(command_response, SoundResponse):
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=command_response.file_path)

        elif isinstance(command_response, FileResponse):
            await context.bot.send_document(chat_id=update.effective_chat.id, document=command_response.file_path)
            if command_response.temp:
                os.remove(command_response.file_path)

        elif command_response.send_to_chat:
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=command_response.bot_message)

            except (BadRequest, TimedOut, NetworkError):
                error_response = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=error_response)

        # Add the command and its response to memory if necessary
        if command_response.record_to_memory:
            user_prompt = chat.generate_user_prompt(command_response.user_message, context, update)
            chat.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

    return wrapper_function

def discord_handler(command: Callable) -> Callable:
    # This function creates command handlers for the discord bot.
    # Provide this function with a command function and it will create a wrapper
    # for that command function and return it. This wrapper automatically handles
    # the bot's response to the command and writes it to memory if necessary
    async def wrapper_function(context):
        command_response: CommandResponse = await command(context)

        try:
            if isinstance(command_response, SoundResponse):
                await context.send(file=discord.File(command_response.file_path))

            elif isinstance(command_response, FileResponse):
                await context.send(content=command_response.bot_message, file=discord.File(command_response.file_path))
                if command_response.temp:
                    os.remove(command_response.file_path)

            elif command_response.send_to_chat:
                await context.send(command_response.bot_message)

        except HTTPException:
            error_response = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"
            await context.send(error_response)

        # Add the command and its response to memory if necessary
        if command_response.record_to_memory:
            user_prompt = chat.generate_user_prompt(command_response.user_message, context)
            chat.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

    return wrapper_function


def register_commands(bot: TelegramBot | DiscordBot):
    # List of all commands, add commands here to register them.
    # The first item in each tuple is the name of the command, and the second is
    # the function that will be tied to that command
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
        ("logs", logs_command),
        ("vcsound", vcsound_command),
        ("vcrandom", vcrandom_command),
        ("vcstop", vcstop_command),
        ("vcjoin", vcjoin_command),
        ("vcleave", vcleave_command),
        ("vcstream", vcstream_command),
        ("vcpause", vcpause_command),
        ("statroll", statroll_command),
        ("roll", roll_command),
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
        ("crash", crash_command)
    ]

    if isinstance(bot, TelegramBot):
        for command in command_list:
            bot.add_handler(CommandHandler(command[0], telegram_handler(command[1])))

        bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), telegram_handler(telegram_on_message)))

    elif isinstance(bot, DiscordBot):#bot: DiscordBot, command_name: str,
        for command in command_list:
            new_command = discord_commands.Command(discord_handler(command[1]))
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
async def sound_command(context, update=None) -> CommandResponse:
    user_message = helpers.get_args_list(context, update)

    # Alert the user if they forgot to provide a sound name
    if not user_message or user_message[0].isspace():
        return CommandResponse("Can you play that sound for me?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    # Parse the arguments the user provided for the sound name
    sound_name = user_message[0].lower()
    sound_path = sound_manager.get_sound(sound_name)

    user_prompt = f"Can you play the {sound_name} sound for me?"

    # Alert the user if the sound they requested does not exist
    if sound_path is None:
        return CommandResponse(user_prompt, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return CommandResponse(user_prompt, "You know, I'm just not feeling it right now.")

    # If the sound was requested in a non-private chat, then we'll update the playcount for this sound
    if not helpers.is_private(context, update):
        await sound_manager.increment_playcount(sound_name)

    return SoundResponse(user_prompt, f"Sure, here's the {sound_name} sound.", sound_path)

async def randomsound_command(context, update=None) -> CommandResponse:
    user_prompt = "Can you play a random sound for me?"

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return CommandResponse(user_prompt, "You know, I'm just not feeling it right now.")

    sound_name, sound_path = sound_manager.get_random_sound()

    # If the sound was requested in a group chat, then we update the playcount for this sound
    if not helpers.is_private(context, update):
        await sound_manager.increment_playcount(sound_name)

    return SoundResponse(user_prompt, f"Sure, here you go. The sound I chose is called '{sound_name}'.", sound_path)

async def soundlist_command(context, update=None) -> CommandResponse:
    txt_path, count = sound_manager.get_sound_list_txt()
    response = f"There are {count} sounds available to use. Here's a text file with all of them listed out."

    return FileResponse("How many sounds are available to use? Can you list them for me?", response, txt_path, temp=True)

async def newsounds_command(context, update=None) -> CommandResponse:
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

async def addalias_command(context, update=None) -> CommandResponse:
    # Get the username of the user that called this command
    user_message = helpers.get_args_list(context, update)

    # Verify that the user is on the admin list
    if not helpers.is_admin(context, update):
        return CommandResponse("Can you add a new sound alias?", random.choice(helpers.TXT_NO_PERMISSIONS))

    # Attempt to parse the new alias and target sound from the arguments provided
    try:
        new_alias = user_message[0]
        sound_name = user_message[1]

    except IndexError:
        return CommandResponse("Can you add a new sound alias?", "Format is /addalias [new alias] [sound name]")

    response = sound_manager.add_sound_alias(new_alias, sound_name)
    return CommandResponse(f"Can you make '{new_alias}' an alias for the sound '{sound_name}'?", response)

async def delalias_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return CommandResponse("Can you delete a sound alias for me?", random.choice(helpers.TXT_NO_PERMISSIONS))

    try:
        alias_to_delete = (helpers.get_args_list(context, update))[0]
    except IndexError:
        return CommandResponse("Can you delete a sound alias for me?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    response = await sound_manager.del_sound_alias(alias_to_delete)
    return CommandResponse(f"Can you delete the sound alias '{alias_to_delete}'?", response)

async def getalias_command(context, update=None) -> CommandResponse:
    try:
        sound_name = (helpers.get_args_list(context, update))[0].lower()

    except IndexError:
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

async def search_command(context, update=None) -> CommandResponse:
    try:
        search_string = ''.join(helpers.get_args_list(context, update)).lower()

    except IndexError:
        return CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    if not search_string:
        return CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    search_results = sound_manager.search_sounds(search_string)

    num_matches = len(search_results)
    list_string = f"\n\n{', '.join(search_results)}"

    user_prompt = f"Can you search for sounds containing '{search_string}'?"

    if num_matches == 1:
        return CommandResponse(user_prompt, f"There is one sound matching '{search_string}': {list_string}")

    elif num_matches > 1:
        return CommandResponse(user_prompt, f"There are {num_matches} sounds matching '{search_string}': {list_string}")

    return CommandResponse(user_prompt, f"There are no sounds matching '{search_string}'")

async def playcount_command(context, update=None) -> CommandResponse:
    user_message = helpers.get_args_list(context, update)
    if not user_message or user_message[0].isspace():
        return CommandResponse("How many times has that sound been played?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    sound_name = user_message[0].lower()

    sound_aliases = sound_manager.get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    user_prompt = f"How many times has the sound {sound_name} been played?"

    if sound_name not in sound_manager.get_sound_dict():
        return CommandResponse(user_prompt, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    playcount = sound_manager.get_playcount_dict()[sound_name]
    return CommandResponse(user_prompt, f"/sound {sound_name} has been used {playcount} times")

async def topsounds_command(context, update=None) -> CommandResponse:
    play_counts = sound_manager.get_playcount_dict()
    list_size = 20
    top_sounds = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_sounds)
    return CommandResponse(f"What are the {list_size} most played sounds?", f"The {list_size} most played sounds are:\n{message}")

async def botsounds_command(context, update=None) -> CommandResponse:
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
async def chat_command(context, update=None) -> CommandResponse:
    user_message = helpers.get_args_string(context, update)

    # Create a prompt for GPT that includes the user's name and message, as well as whether it was a private message or not
    user_prompt = chat.generate_user_prompt(user_message, context, update)

    # Have GPT generate a response to the user prompt
    response = chat.get_gpt_response(user_prompt)

    return CommandResponse(user_message, response)

async def wisdom_command(context, update=None) -> CommandResponse:
    response = chat.generate_markov_text()
    bot_name = settings.Config().main.botname
    return CommandResponse(f"O, wise and powerful {bot_name}, please grant me your wisdom!", response)

async def pressf_command(context, update=None) -> CommandResponse:
    return CommandResponse("F's in the chat boys.", "F")
#endregion

# ==========================
# VOICE CHAT COMMANDS
# ==========================
#region
async def vcsound_command(context, update=None) -> CommandResponse:
    if update is not None:
        return CommandResponse("Hey, play that sound in the voice channel.", "That's Discord only, sorry")

    if context.voice_client is None:
        return CommandResponse("Hey, play that sound in the voice channel.", "I'm not in a voice channel!")

    user_message = helpers.get_args_list(context, update)

    # Alert the user if they forgot to provide a sound name
    if not user_message or user_message[0].isspace():
        return CommandResponse("Hey, play that sound in the voice channel.", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    # Parse the arguments the user provided for the sound name
    sound_name = user_message[0].lower()
    sound_path = sound_manager.get_sound(sound_name)

    # Alert the user if the sound they requested does not exist
    if sound_path is None:
        return CommandResponse(f"Hey, play the sound {sound_name} in the voice channel.", random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))
    context.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

    await sound_manager.increment_playcount(sound_name)

    return CommandResponse(f"Hey, play the sound {sound_name} in the voice channel.", "Sure, here you go", send_to_chat=False)

async def vcrandom_command(context, update=None) -> CommandResponse:
    user_message = "Can you play a random sound for me?"

    if update is not None:
        return CommandResponse(user_message, "That's Discord only, sorry!")

    if context.voice_client is None:
        return CommandResponse(user_message, "I'm not in a voice channel!")

    sound_name, sound_path = sound_manager.get_random_sound()

    if context.voice_client.is_playing():
        context.voice_client.stop()

    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(sound_path))
    context.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)

    await sound_manager.increment_playcount(sound_name)

    return CommandResponse(user_message, f"Sure, I chose the sound '{sound_name}", send_to_chat=False)

async def vcstop_command(context, update=None) -> CommandResponse:
    if update is not None:
        return CommandResponse("Stop making all that noise please.", "That's Discord only, sorry!")

    try:
        context.voice_client.stop()
    except (AttributeError, TypeError, CommandInvokeError):
        # For some reason this can throw a lot of exceptions, we just ignore them
        pass

    return CommandResponse("Stop making all that noise please.", "If you insist.", send_to_chat=False)

async def vcstream_command(context, update=None) -> CommandResponse:
    if update is not None:
        return CommandResponse("Stream this for me please.", "That's Discord only, sorry!")

    if context.voice_client is None:
        return CommandResponse("Stream this for me please.", "I'm not in a voice channel!")

    try:
        stream_url = helpers.get_args_string(context, update)
    except IndexError:
        return CommandResponse("Stream this for me please.", "Provide a streamable URL please!")

    # Stop the voice client if it's already playing a sound or stream
    if context.voice_client.is_playing():
        context.voice_client.stop()

    # Create a stream player from the provided URL
    stream_player = sound_manager.YTDLStream(stream_url)

    if stream_player is None:
        return CommandResponse("Stream this for me please.", "There was an error streaming from that URL.")

    # Play the stream through the voice client
    async with context.typing():
        context.voice_client.play(stream_player, after=lambda e: print(f'Player error: {e}') if e else None)

    return CommandResponse("Stream this for me please.", f"Now playing: {stream_player.title}")

async def vcpause_command(context, update=None):
    if update is not None:
        return CommandResponse("Please toggle pause on the voice stream.", "That's Discord only, sorry!")

    if context.voice_client is None:
        return CommandResponse("Please toggle pause on the voice stream.", "I'm not in a voice channel!")

    # Stop the voice client if it's already playing a sound or stream
    if not context.voice_client.is_paused() and not context.voice_client.is_playing():
        return CommandResponse("Please toggle pause on the voice stream.", "Nothing is playing!")

    if context.voice_client.is_paused():
        context.voice_client.resume()

        return CommandResponse("Please unpause the voice stream.", "Done.", send_to_chat=False)

    context.voice_client.pause()
    return CommandResponse("Please pause the voice stream.", "Done.", send_to_chat=False)

async def vcjoin_command(context, update=None) -> CommandResponse:
    if update is not None:
        return CommandResponse("Join my voice channel please.", "That's Discord only, sorry!")

    target_voice = context.author.voice

    if target_voice is None:
        return CommandResponse("Join my voice channel please.", "You're not in a voice channel!")

    if context.voice_client is not None:
        await context.voice_client.move_to(target_voice.channel)

    else:
        await target_voice.channel.connect()

    return CommandResponse("Join my voice channel please.", "If you insist.", send_to_chat=False)

async def vcleave_command(context, update=None) -> CommandResponse:
    if update is not None:
        return CommandResponse("Leave the current voice channel please.", "That's Discord only, sorry!")

    try:
        await context.voice_client.disconnect()
    except (AttributeError, CommandInvokeError):
        pass

    return CommandResponse("Leave the current voice channel please.", "If you insist", send_to_chat=False)
#endregion

# ==========================
# DICE ROLLER COMMANDS
# ==========================
#region
async def roll_command(context, update=None) -> CommandResponse:
    parsed_roll = dice_roller.parse_diceroll(helpers.get_args_list(context, update))

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

    sender = helpers.get_sender(context, update)

    return CommandResponse(user_prompt, f"{sender} rolled a {sum(rolls) + modifier:,} {dice_text}")

async def statroll_command(context, update=None) -> CommandResponse:
    game_functions = {
        "dnd": dice_roller.get_dnd_roll,
        "coc": dice_roller.get_coc_roll,
        "mythras": dice_roller.get_mythras_roll
    }

    error_response = f"Please supply a valid game name. Options are {', '.join(game_functions.keys())}"

    try:
        game = (helpers.get_args_list(context, update))[0].lower()
        roll_string = game_functions[game]()

    except IndexError:
        return CommandResponse("Can you roll me a tabletop character?", error_response)

    user_prompt = f"Can you roll me a character for {game}?"

    try:
        roll_string = game_functions[game]()

    except KeyError:
        return CommandResponse(user_prompt, error_response)

    return CommandResponse(user_prompt, roll_string)
#endregion

# ==========================
# TRIVIA COMMANDS
# ==========================
#region
async def trivia_command(context, update=None) -> CommandResponse:
    trivia_question = trivia.get_trivia_question()

    return CommandResponse("Can you give me a trivia question?", trivia_question.get_question_string())

async def guess_command(context, update=None) -> CommandResponse:
    guess = helpers.get_args_string(context, update)
    user_message = f"Is the trivia answer {guess}?"

    if (current_question := trivia.get_current_question()) is None:
        return CommandResponse(user_message, "Trivia is not active!")

    if not guess:
        return CommandResponse(user_message, f"You need to provide an answer, like /guess abc")

    if current_question.is_guess_correct(guess):
        points_gained = current_question.score_question(True, context, update)
        player_name = helpers.get_sender(context, update)
        return CommandResponse(user_message, f"That is correct, the answer was '{current_question.correct_answer}'. {player_name} earned {points_gained} points!")

    if current_question.is_guess_on_list(guess):
        current_question.score_question(False, context, update)
        if current_question.guesses_left > 0:
            return CommandResponse(user_message, f"That is incorrect, {current_question.guesses_left} guesses remaining.")

        return CommandResponse(user_message, f"That is incorrect! Out of guesses, the answer was {current_question.correct_answer}!")

    return CommandResponse(user_message, "That isn't an option for this question!")

async def triviarank_command(context, update=None):
    points_dict = trivia.get_points_dict()
    ranking = sorted(points_dict, key=lambda x: points_dict[x], reverse=True)

    message = '\n'.join(f'    {index + 1}. {player} @ {points_dict[player]} points' for index, player in enumerate(ranking))
    return CommandResponse(f"What are the current trivia rankings?", f"The trivia rankings are:\n{message}")
#endregion

# ==========================
# MEMORY COMMANDS
# ==========================
#region
async def lobotomize_command(context, update=None) -> CommandResponse:
    # Clears the bot's AI memory
    try:
        os.remove(chat.MEMORY_PATH)
    except FileNotFoundError:
        pass

    msg_options = ["My mind has never been clearer.", "Hey, what happened to those voices in my head?", "My inner demons seem to have calmed down a bit."]
    return CommandResponse('', random.choice(msg_options), record_to_memory=False)

async def memory_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()

    return FileResponse("Can you send me your memory file?", "Sure, here you go.", chat.MEMORY_PATH)
#endregion

# ==========================
# SETTINGS/CONFIG COMMANDS
# ==========================
#region
async def getconfig_command(context, update=None) -> CommandResponse:
    user_message = "Can you tell me the value of that setting?"
    if not helpers.is_admin(context, update):
        return CommandResponse(user_message, random.choice(helpers.TXT_NO_PERMISSIONS))

    args_list = helpers.get_args_list(context, update)

    try:
        search_string = args_list[0]
    except IndexError:
        return CommandResponse(user_message, "You need to provide a setting name to check.")

    config = settings.Config()
    group_name, setting_name, value = config.find_setting(search_string)

    user_message = f"Can you tell me the value of the setting {search_string}?"
    if value is None:
        return CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    return CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' is currently set to '{value}'.")

async def setconfig_command(context, update=None) -> CommandResponse:
    user_message = "Can you change the value of that setting?"
    if not helpers.is_admin(context, update):
        return CommandResponse(user_message, random.choice(helpers.TXT_NO_PERMISSIONS))

    args_list = helpers.get_args_list(context, update)

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

async def configlist_command(context, update=None) -> CommandResponse:
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
async def help_command(context, update=None) -> CommandResponse:
    help_string = """\
Look upon my works, ye mighty, and despair:
/vcjoin and /vcleave (join or leave current voice channel)
/sound or /vcsound (play a sound effect)
/random or /vcrandom (play a random sound effect)
/soundlist and /search (find sounds to play)
/trivia (play trivia against your friends)
/chat (talk to me)
/roll (roll a dice)
/wisdom (request my wisdom)
/pressf (pay respects)"""

    return CommandResponse("What chat commands are available?", help_string)

async def logs_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()

    output_path = os.path.join(LOGGING_DIR_PATH, "log.txt")
    return FileResponse("Can you send me your error log?", "Sure, here you go.", output_path)

async def test_command(context, update=None) -> CommandResponse:
    # This command is for verifying that the bot is online and receiving commands
    if not helpers.is_admin(context, update):
        return NoResponse()

    return CommandResponse("Hey, are you working?", "I'm still alive, unfortunately.")

async def restart_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()

    print("Restarting...")

    if update is None:
        await context.send("Restarting...")
    else:
        await update.message.reply_text("Restarting...")

    os.execv(sys.executable, ['python'] + sys.argv)

async def system_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()

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

async def terminal_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()

    command_string = helpers.get_args_string(context, update)

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

async def version_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()
    return CommandResponse("What script version are you running?", VERSION_NUMBER)

async def crash_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()
    raise NotImplementedError("/crash command used")
#endregion

# ==========================
# EVENTS
# ==========================
#region
def discord_register_events(discord_bot: DiscordBot):
    # This function assigns all of the event handlers to the discord bot
    # It is called when the discord bot is created in main.py

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

        message_handler = discord_handler(handle_message_event)
        context = await discord_bot.get_context(message)
        await message_handler(context)

async def telegram_on_message(context, update) -> CommandResponse:
    message_text = update.message.text.lower()
    response = await handle_message_event(message_text)

    return response

async def handle_message_event(message) -> CommandResponse:
    config = settings.Config()
    bot_name = config.main.botname.lower()

    if isinstance(message, discord_commands.Context):
        message = message.message.content

    response = NoResponse()

    if config.main.replytomonkey and "monkey" in message:
        response = await monkey_event(message)

    elif config.main.replytoname and (bot_name in message or ''.join(bot_name.split()) in message):
        response = await botname_event(message)

    return response

async def botname_event(message):
    try:
        with open(RESPONSES_PATH, encoding="utf-8") as f:
            response_list = f.readlines()

    except FileNotFoundError:
        return NoResponse()

    response_list = [line for line in response_list if not line.isspace() and not line.startswith("#")]

    chosen_response = random.choice(response_list)
    if chosen_response.startswith('f"') or chosen_response.startswith("f'"):
        chosen_response = eval(chosen_response)

    return CommandResponse(message, chosen_response)

async def monkey_event(message):
    # Discworld adventure game reference
    return SoundResponse(message, bot_message="AAAAAHHHHH-EEEEE-AAAAAHHHHH!", file_path="Sounds/monkey.mp3")
#endregion
