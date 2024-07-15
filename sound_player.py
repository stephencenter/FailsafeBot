import random
import sound_manager
import memory
import helpers

async def sound_command(context, update=None):
    user_message = await helpers.get_args_list(context, update)

    # Alert the user if they forgot to provide a sound name
    if not user_message or user_message[0].isspace():
        return random.choice(sound_manager.txt_sound_not_provided)

    # Parse the arguments the user provided for the sound name
    sound_name = user_message[0].lower()
    sound_path = sound_manager.get_sound(sound_name)

    # Alert the user if the sound they requested does not exist
    if sound_path is None:
        return random.choice(sound_manager.txt_sound_not_found)

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
        await sound_manager.increment_playcount(sound_name)

    memory.append_to_memory(user_prompt, "Sure, here you go.")

    return helpers.SoundResponse(sound_path)

async def randomsound_command(context, update=None):
    user_prompt = await memory.generate_user_prompt("Can you play a random sound for me?", context, update)

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        response = "You know, I'm just not feeling it right now."
        memory.append_to_memory(user_prompt, response)
        return response

    sound_name, sound_path = sound_manager.get_random_sound()

    # If the sound was requested in a group chat, then we update the playcount for this sound
    if not await helpers.is_private(context, update):
        await sound_manager.increment_playcount(sound_name)

    memory.append_to_memory(user_prompt, f"Sure, here you go. The sound I chose is called '{sound_name}'.")

    return helpers.SoundResponse(sound_path)

async def soundlist_command(context, update=None):
    txt_path, count = sound_manager.get_sound_list_txt()

    user_prompt = await memory.generate_user_prompt("How many sounds are available to use? Can you list them for me?", context, update)
    response = f"There are {count} sounds available to use. Here's a text file with all of them listed out."
    memory.append_to_memory(user_prompt, response)

    return helpers.FileResponse(txt_path, message=f"There are {count} sounds to choose from:", temp=True)

async def addalias_command(context, update=None):
    # Get the username of the user that called this command
    username = await helpers.get_sender(context, update)
    user_message = await helpers.get_args_list(context, update)

    # Verify that the user is on the admin list
    if not await helpers.is_admin(username):
        return random.choice(helpers.txt_no_permissions)

    # Attempt to parse the new alias and target sound from the arguments provided
    try:
        new_alias = user_message[0]
        sound_name = user_message[1]

    except IndexError:
        return "Format is /alias [new alias] [sound name]"

    response = sound_manager.add_sound_alias(new_alias, sound_name)
    return response

async def delalias_command(context, update=None):
    username = await helpers.get_sender(context, update)

    if not await helpers.is_admin(username):
        return random.choice(helpers.txt_no_permissions)

    alias_to_delete = (await helpers.get_args_list(context, update))[0]

    response = await sound_manager.del_sound_alias(alias_to_delete)
    return response

async def newsounds_command(context, update=None):
    playcount_dict = sound_manager.get_playcount_dict()
    new_sounds = [sound for sound in playcount_dict if playcount_dict[sound] == 0]
    new_count = len(new_sounds)
    list_string = ', '.join(new_sounds)

    if new_count == 0:
        return "There are no new sounds available."

    elif new_count == 1:
        return f"There is one new sound available: {list_string}"

    else:
        return f"There are {new_count} new sounds available:\n\n{list_string}"

async def getalias_command(context, update=None):
    try:
        sound_name = (await helpers.get_args_list(context, update))[0].lower()
    except IndexError:
        return random.choice(sound_manager.txt_sound_not_provided)

    if not sound_manager.sound_exists(sound_name):
        return random.choice(sound_manager.txt_sound_not_found)

    aliases = sound_manager.get_aliases(sound_name)
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

    search_results = sound_manager.search_sounds(search_string)

    num_matches = len(search_results)
    list_string = f"\n\n{', '.join(search_results)}"
    if num_matches == 1:
        return f"There is one sound matching '{search_string}': {list_string}"

    elif num_matches > 1:
        return f"There are {num_matches} sounds matching '{search_string}': {list_string}"

    else:
        return f"There are no sounds matching '{search_string}'"

async def playcount_command(context, update=None):
    user_message = await helpers.get_args_list(context, update)
    if not user_message or user_message[0].isspace():
        return random.choice(sound_manager.txt_sound_not_provided)

    sound_name = user_message[0].lower()

    sound_aliases = sound_manager.get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    if sound_name not in sound_manager.get_sound_dict():
        return random.choice(sound_manager.txt_sound_not_found)

    playcount = sound_manager.get_playcount_dict()[sound_name]
    return f"/sound {sound_name} has been used {playcount} times"

async def topsounds_command(context, update=None):
    play_counts = sound_manager.get_playcount_dict()
    list_size = 20
    top_sounds = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_sounds)
    return f"The {list_size} most used sounds are:\n{message}"

async def botsounds_command(context, update=None):
    play_counts = sound_manager.get_playcount_dict()
    list_size = 20
    bot_sounds = sorted(play_counts, key=lambda x: play_counts[x])[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in bot_sounds)
    return f"The {list_size} least used sounds are:\n{message}"
