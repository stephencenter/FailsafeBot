import os
import sys
import random
import discord
from discord.ext import commands as discord_commands
import sound_manager
import chat
import settings
import dice_roller
import helpers

LOGGING_DIR_PATH = os.path.join("Data", "logging")
LOGGING_FILE_PATH = os.path.join(LOGGING_DIR_PATH, "log.txt")

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
    user_message = ' '.join(helpers.get_args_list(context, update))

    # Create a prompt for GPT that includes the user's name and message, as well as whether it was a private message or not
    user_prompt = chat.generate_user_prompt(user_message, context, update)

    # Have GPT generate a response to the user prompt
    response = chat.get_gpt_response(user_prompt)

    return CommandResponse(user_message, response)

async def wisdom_command(context, update=None) -> CommandResponse:
    response = chat.generate_markov_text()
    bot_name = settings.get_config().main.botname
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

    return CommandResponse(user_message, "Sure, I chose the sound '{sound_name}", send_to_chat=False)

async def vcstop_command(context, update=None) -> CommandResponse:
    if update is not None:
        return CommandResponse("Stop making all that noise please.", "That's Discord only, sorry!")

    try:
        context.voice_client.stop()
    except (AttributeError, TypeError, discord_commands.errors.CommandInvokeError):
        # For some reason this can throw a lot of exceptions, we just ignore them
        pass

    return CommandResponse("Stop making all that noise please.", "If you insist.", send_to_chat=False)

async def vcstream_command(context, update=None) -> CommandResponse:
    if update is not None:
        return CommandResponse("Stream this for me please.", "That's Discord only, sorry!")

    if context.voice_client is None:
        return CommandResponse("Stream this for me please.", "I'm not in a voice channel!")

    try:
        stream_url = ' '.join(helpers.get_args_list(context, update))
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
    except (AttributeError, discord_commands.errors.CommandInvokeError):
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

    config = settings.get_config()
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

    config = settings.get_config()
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

    config = settings.get_config()
    group_name, setting_name, _ = config.find_setting(search_string)

    user_message = f"Can you change the value of the setting {search_string}?"
    if group_name is None or setting_name is None:
        return CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    new_value = settings.parse_value_input(new_value)

    setattr(getattr(config, group_name), setting_name, new_value)
    settings.save_config(config)

    return CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' has been set to '{new_value}'.")

async def configlist_command(context, update=None) -> CommandResponse:
    config = settings.get_config()

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
async def logs_command(context, update=None) -> CommandResponse:
    output_path = os.path.join(LOGGING_DIR_PATH, "log.txt")
    return FileResponse("Can you send me your error log?", "Sure, here you go.", output_path)

async def test_command(context, update=None) -> CommandResponse:
    # This command is for verifying that the bot is online and receiving commands
    if not helpers.is_admin(context, update):
        return NoResponse()

    return CommandResponse("Hey, are you working?", "I'm still alive, unfortunately.")

async def help_command(context, update=None) -> CommandResponse:
    help_string = """\
Look upon my works, ye mighty, and despair:
/vcjoin and /vcleave (join or leave current voice channel)
/sound or /vcsound (play a sound effect)
/random or /vcrandom (play a random sound effect)
/soundlist (see what sounds are available)
/search (look for sounds)
/chat (talk to me)
/roll (roll a dice)
/pressf (pay respects)
/wisdom (request my wisdom)"""

    return CommandResponse("What chat commands are available?", help_string)

async def restart_command(context, update=None) -> CommandResponse:
    if not helpers.is_admin(context, update):
        return NoResponse()

    if update is None:
        return CommandResponse("Restart your script please.", "That's telegram only, sorry!")

    print("Restarting...")

    await update.message.reply_text("Restarting...")
    os.execv(sys.executable, ['python'] + sys.argv)
#endregion