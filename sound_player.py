import random
import sound_manager
import helpers

async def sound_command(context, update=None) -> helpers.CommandResponse:
    user_message = await helpers.get_args_list(context, update)

    # Alert the user if they forgot to provide a sound name
    if not user_message or user_message[0].isspace():
        return helpers.CommandResponse("Can you play that sound for me?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    # Parse the arguments the user provided for the sound name
    sound_name = user_message[0].lower()
    sound_path = sound_manager.get_sound(sound_name)

    user_prompt = f"Can you play the {sound_name} sound for me?"

    # Alert the user if the sound they requested does not exist
    if sound_path is None:
        return helpers.CommandResponse(user_prompt, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return helpers.CommandResponse(user_prompt, "You know, I'm just not feeling it right now.")

    # If the sound was requested in a non-private chat, then we'll update the playcount for this sound
    if not await helpers.is_private(context, update):
        await sound_manager.increment_playcount(sound_name)

    return helpers.SoundResponse(user_prompt, f"Sure, here's the {sound_name} sound.", sound_path)

async def randomsound_command(context, update=None) -> helpers.CommandResponse:
    user_prompt = "Can you play a random sound for me?"

    # The bot has a 1 in 1000 chance of refusing to play a sound.
    # Have to keep the users on their toes
    if random.randint(1, 1000) == 555:
        return helpers.CommandResponse(user_prompt, "You know, I'm just not feeling it right now.")

    sound_name, sound_path = sound_manager.get_random_sound()

    # If the sound was requested in a group chat, then we update the playcount for this sound
    if not await helpers.is_private(context, update):
        await sound_manager.increment_playcount(sound_name)

    return helpers.SoundResponse(user_prompt, f"Sure, here you go. The sound I chose is called '{sound_name}'.", sound_path)

async def soundlist_command(context, update=None) -> helpers.CommandResponse:
    txt_path, count = sound_manager.get_sound_list_txt()
    response = f"There are {count} sounds available to use. Here's a text file with all of them listed out."

    return helpers.FileResponse("How many sounds are available to use? Can you list them for me?", response, txt_path, temp=True)

async def addalias_command(context, update=None) -> helpers.CommandResponse:
    # Get the username of the user that called this command
    username = await helpers.get_sender(context, update)
    user_message = await helpers.get_args_list(context, update)

    # Verify that the user is on the admin list
    if not await helpers.is_admin(username):
        return helpers.CommandResponse("Can you add a new sound alias?", random.choice(helpers.TXT_NO_PERMISSIONS))

    # Attempt to parse the new alias and target sound from the arguments provided
    try:
        new_alias = user_message[0]
        sound_name = user_message[1]

    except IndexError:
        return helpers.CommandResponse("Can you add a new sound alias?", "Format is /addalias [new alias] [sound name]")

    response = sound_manager.add_sound_alias(new_alias, sound_name)
    return helpers.CommandResponse(f"Can you make '{new_alias}' an alias for the sound '{sound_name}'?", response)

async def delalias_command(context, update=None) -> helpers.CommandResponse:
    username = await helpers.get_sender(context, update)

    if not await helpers.is_admin(username):
        return helpers.CommandResponse("Can you delete a sound alias for me?", random.choice(helpers.TXT_NO_PERMISSIONS))

    try:
        alias_to_delete = (await helpers.get_args_list(context, update))[0]
    except IndexError:
        return helpers.CommandResponse("Can you delete a sound alias for me?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    response = await sound_manager.del_sound_alias(alias_to_delete)
    return helpers.CommandResponse(f"Can you delete the sound alias '{alias_to_delete}'?", response)

async def newsounds_command(context, update=None) -> helpers.CommandResponse:
    playcount_dict = sound_manager.get_playcount_dict()
    new_sounds = [sound for sound in playcount_dict if playcount_dict[sound] == 0]
    new_count = len(new_sounds)
    list_string = ', '.join(new_sounds)

    user_message = "How many new sounds are available?"

    if new_count == 0:
        return helpers.CommandResponse(user_message, "There are no new sounds available.")

    if new_count == 1:
        return helpers.CommandResponse(user_message, f"There is one new sound available: {list_string}")

    return helpers.CommandResponse(user_message, f"There are {new_count} new sounds available:\n\n{list_string}")

async def getalias_command(context, update=None) -> helpers.CommandResponse:
    try:
        sound_name = (await helpers.get_args_list(context, update))[0].lower()

    except IndexError:
        return helpers.CommandResponse("How many aliases does that sound have?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    user_prompt = f"How many aliases does the sound '{sound_name}' have?"

    if not sound_manager.sound_exists(sound_name):
        return helpers.CommandResponse(user_prompt, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    aliases = sound_manager.get_aliases(sound_name)
    num_alias = len(aliases)
    join_string = "', '"
    alias_string = f"'{join_string.join(aliases)}'"

    if num_alias == 1:
        return helpers.CommandResponse(user_prompt, f"The sound '{sound_name}' has one alias: {alias_string}")

    elif num_alias > 1:
        return helpers.CommandResponse(user_prompt, f"The sound '{sound_name}' has {num_alias} aliases: {alias_string}")

    else:
        return helpers.CommandResponse(user_prompt, f"The sound '{sound_name}' has no assigned aliases")

async def search_command(context, update=None) -> helpers.CommandResponse:
    try:
        search_string = ''.join(await helpers.get_args_list(context, update)).lower()

    except IndexError:
        return helpers.CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    if not search_string:
        return helpers.CommandResponse("Can you search for a sound?", "What sound do you want to search for?")

    search_results = sound_manager.search_sounds(search_string)

    num_matches = len(search_results)
    list_string = f"\n\n{', '.join(search_results)}"

    user_prompt = f"Can you search for sounds containing '{search_string}'?"

    if num_matches == 1:
        return helpers.CommandResponse(user_prompt, f"There is one sound matching '{search_string}': {list_string}")

    elif num_matches > 1:
        return helpers.CommandResponse(user_prompt, f"There are {num_matches} sounds matching '{search_string}': {list_string}")

    return helpers.CommandResponse(user_prompt, f"There are no sounds matching '{search_string}'")

async def playcount_command(context, update=None) -> helpers.CommandResponse:
    user_message = await helpers.get_args_list(context, update)
    if not user_message or user_message[0].isspace():
        return helpers.CommandResponse("How many times has that sound been played?", random.choice(sound_manager.TXT_SOUND_NOT_PROVIDED))

    sound_name = user_message[0].lower()

    sound_aliases = sound_manager.get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]

    user_prompt = f"How many times has the sound {sound_name} been played?"

    if sound_name not in sound_manager.get_sound_dict():
        return helpers.CommandResponse(user_prompt, random.choice(sound_manager.TXT_SOUND_NOT_FOUND))

    playcount = sound_manager.get_playcount_dict()[sound_name]
    return helpers.CommandResponse(user_prompt, f"/sound {sound_name} has been used {playcount} times")

async def topsounds_command(context, update=None) -> helpers.CommandResponse:
    play_counts = sound_manager.get_playcount_dict()
    list_size = 20
    top_sounds = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_sounds)
    return helpers.CommandResponse(f"What are the {list_size} most played sounds?", f"The {list_size} most played sounds are:\n{message}")

async def botsounds_command(context, update=None) -> helpers.CommandResponse:
    play_counts = sound_manager.get_playcount_dict()
    list_size = 20
    bot_sounds = sorted(play_counts, key=lambda x: play_counts[x])[:list_size]

    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in bot_sounds)
    return helpers.CommandResponse(f"What are the {list_size} least played sounds?", f"The {list_size} least used sounds are:\n{message}")
