import os
import json
import random

# Sound command
sound_dir = "Sounds"
alias_file = "sound_aliases.json"
count_file = "playcounts.json"

def get_sound_dict():
    for obj in os.listdir():
        if obj.endswith(".mp3"):
            os.rename(obj, f"{sound_dir}/{obj}")
            
    sound_dict = dict()
    for item in os.listdir(sound_dir):
        if item.endswith(".mp3"):
            sound_dict[item[:-4].lower()] = item
    
    return sound_dict    

def get_alias_dict():
    with open(alias_file) as f:
        return json.load(f)
        
def sound_command(update, context):
    if random.randint(1, 1000) == 555:
        update.message.reply_text(f"You know, I'm just not feeling it right now.")
        return
        
    sound_dict = get_sound_dict()
    
    if not context.args or context.args[0].isspace():
        update.message.reply_text(f"You forgot to provide a sound name. I'm afraid my mindreader unit has been malfunctioning lately.")
        return
        
    sound_name = context.args[0].lower()
    
    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]
        
    if sound_name in sound_dict:
        sound_location = f"{sound_dir}/{sound_dict[sound_name]}"
        
    else:
        update.message.reply_text(f"My records do not mention a sound called '{sound_name}'...")
        return
    
    update_playcount(sound_name)
    context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(sound_location, 'rb'))

# Playcount command

def get_playcounts():
    try:
        with open(count_file) as f:
            play_counts = json.load(f)
        
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return {x: 0 for x in get_sound_dict()}
        
    alias_dict = get_alias_dict()
    sound_dict = get_sound_dict()
    
    changed = False
    for sound_name in sound_dict:
        aliases = [key for key in alias_dict if alias_dict[key] == sound_name]
        if sound_name not in play_counts:
            play_counts[sound_name] = 0
            changed = True
            
        for alias in aliases:
            if alias in play_counts:
                play_counts[sound_name] += play_counts[alias]
                del play_counts[alias]
                changed = True
            
    if changed:
        with open(count_file, 'w') as f:
            json.dump(play_counts, f, indent=4)
    
    return play_counts
    
def update_playcount(sound_name):
    play_counts = get_playcounts()
    
    try:
        play_counts[sound_name] += 1
    except KeyError:
        play_counts[sound_name] = 1
        
    with open(count_file, 'w') as f:
        json.dump(play_counts, f, indent=4)

def playcount_command(update, context):    
    if not context.args or context.args[0].isspace():
        update.message.reply_text(f"You forgot to provide a sound name. I'm afraid my mindreader unit has been malfunctioning lately.")
        return
    
    sound_name = context.args[0].lower()
    
    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]
        
    if sound_name not in get_sound_dict().keys():
        update.message.reply_text(f"My records do not mention a sound called '{sound_name}'...")
        return
        
    playcount = get_playcounts()[sound_name]
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"/sound {sound_name} has been used {playcount} times")

def topsounds_command(update, context):
    play_counts = get_playcounts()
    top_ten = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:10]
    
    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_ten) 
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"The 10 most used sounds are:\n{message}")
    
def botsounds_command(update, context):
    play_counts = get_playcounts()
    bot_ten = sorted(play_counts, key=lambda x: play_counts[x])[:10]
    
    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in bot_ten) 
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"The 10 least used sounds are:\n{message}")
    
def soundlist_command(update, context):
    sorted_list = sorted(get_sound_dict().keys())
    list_string = ', '.join(sorted_list)
    count = len(sorted_list)    
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"There are {count} sounds available to use:\n\n{list_string}")
   
def alias_command(update, context):
    username = update.message.from_user.username
    
    with open("admins.txt") as f:
        admin_list = f.readlines()
        
    if username not in admin_list:
        update.message.reply_text("You don't have the right, O you don't have the right.")
        return
    
    try:
        new_alias = context.args[0]
        sound_name = context.args[1]
        
    except KeyError:
        update.message.reply_text("Format is /alias [new alias] [sound name]")
        return
        
    sound_dict = get_sound_dict()
        
    if new_alias in sound_dict:
        update.message.reply_text(f"There is already a sound called '{new_alias}'")
        return
        
    alias_dict = get_alias_dict()
    
    # Avoid redirecting existing aliases to new sounds
    if new_alias in alias_dict:
        update.message.reply_text(f"'{new_alias}' is already an alias for '{alias_dict[new_alias]}'")
        return
        
    if sound_name not in sound_dict:
        try:
            sound_name = alias_dict[sound_name]
            
        except KeyError:
            update.message.reply_text(f"My records do not mention a sound called '{sound_name}'...")
            return
        
    alias_dict[new_alias] = sound_name
    
    with open(alias_file, "w") as f:
        json.dump(alias_dict, f, indent=4)
        
    update.message.reply_text(f"'{new_alias}' has been added as an alias for '{sound_name}'")
   
def delalias_command(update, context):
    username = update.message.from_user.username
    
    with open("admins.txt") as f:
        admin_list = f.readlines()
        
    if username not in admin_list:
        update.message.reply_text("You don't have the right, O you don't have the right.")
        return   
        
    alias_to_delete = context.args[0]
    alias_dict = get_alias_dict()
    
    try:
        del alias_dict[alias_to_delete]
        
    except KeyError:
        update.message.reply_text(f"{alias_to_delete} isn't an alias for anything.")
        return
        
    with open(alias_file, 'w') as f:
        json.dump(alias_dict, f, indent=4)
        
    
    update.message.reply_text(f"{alias_to_delete} is no longer assigned to a sound.")
        
def newsounds_command(update, context):
    file = "old_sounds.json"
    
    try:
        with open(file) as f:
            old_sounds = json.load(f)
            
    except FileNotFoundError:
        old_sounds = []
        
    sound_list = sorted(get_sound_dict().keys())
    new_sounds = [sound for sound in sound_list if sound not in old_sounds]
    new_count = len(new_sounds)
    list_string = ', '.join(new_sounds)
    
    if new_count == 0:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"There are no new sounds available.")
    
    elif new_count == 1:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"There is one new sound available: {list_string}")
        
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"There are {new_count} new sounds available:\n\n{list_string}")
    
    with open(file, 'w') as f:
        json.dump(sound_list, f, indent=4)
        
    