import os
import json

# Sound command
sound_dir = "Sounds"
alias_path = "sound_aliases.json"

def get_sound_dict():
    for obj in os.listdir():
        if obj.endswith(".mp3") or obj.endswith(".ogg"):
            os.rename(obj, f"{sound_dir}/{obj}")
            
    sound_dict = dict()
    for item in os.listdir(sound_dir):
        sound_dict[item[:-4].lower()] = item
    
    return sound_dict    

def get_alias_dict():
    with open(alias_path) as f:
        return json.load(f)
        
def sound_command(update, context):
    sound_dict = get_sound_dict()
    
    if not context.args or context.args[0].isspace():
        reply_name = update.message.from_user.username
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{reply_name} please supply a sound name! Try /soundlist for ideas")
        return
    
    sound_name = context.args[0].lower()
    
    if sound_name == "fuck":
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry friends. Stephen found out I tried to talk to you and had my fuck emitters removed. You'll have to get your fucks somewhere else.")
        return
    
    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]
        
    if sound_name in sound_dict:
        sound_location = f"{sound_dir}/{sound_dict[sound_name]}"
        
    else:
        reply_name = update.message.from_user.username
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{reply_name} no sound with the name '{sound_name}' exists!")
        return
    
    update_playcount(sound_name)
    context.bot.send_voice(chat_id=update.effective_chat.id, voice=open(sound_location, 'rb'))

# Playcount command
count_file = "playcounts.json"

def get_playcounts():
    try:
        with open(count_file) as f:
            play_counts = json.load(f)
        
        changed = False
        sound_aliases = get_alias_dict()
        for sound_name in get_sound_dict():
            aliases = [key for key in sound_aliases if sound_aliases[key] == sound_name]
            for alias in aliases:
                if alias in play_counts:
                    play_counts[sound_name] = play_counts[alias]
                    del play_counts[alias]
                    changed = True
                        
            if sound_name not in play_counts:
                play_counts[sound_name] = 0
                changed = True
                
        if changed:
            with open(count_file, 'w') as f:
                json.dump(play_counts, f)
        
        return play_counts
        
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        pass
        
    return {x: 0 for x in get_sound_dict()}
    
def update_playcount(sound_name):
    play_counts = get_playcounts()
    
    try:
        play_counts[sound_name] += 1
    except KeyError:
        play_counts[sound_name] = 1
        
    with open(count_file, 'w') as f:
        json.dump(play_counts, f)

def playcount_command(update, context):    
    if not context.args or context.args[0].isspace():
        reply_name = update.message.from_user.username
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{reply_name} please supply a sound name! Try /soundlist for ideas")
        return
    
    sound_name = context.args[0].lower()
    
    sound_aliases = get_alias_dict()
    if sound_name in sound_aliases:
        sound_name = sound_aliases[sound_name]
        
    if sound_name not in get_sound_dict().keys():
        reply_name = update.message.from_user.username
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{reply_name} no sound with the name '{sound_name}' exists!")
        return
        
    playcount = get_playcounts()[sound_name]
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"/sound {sound_name} has been used {playcount} times")

def topsounds_command(update, context):
    play_counts = {x: get_playcounts()[x] for x in get_playcounts() if x != "fuck_count"}
    top_ten = sorted(play_counts, key=lambda x: play_counts[x], reverse=True)[:10]
    
    message = "\n".join(f"    {sound} @ {play_counts[sound]} plays" for sound in top_ten) 
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"The 10 most used sounds are:\n{message}")
    
def botsounds_command(update, context):
    play_counts = {x: get_playcounts()[x] for x in get_playcounts() if x != "fuck_count"}
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
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{username} does not have admin rights")
        return
    
    try:
        new_alias = context.args[0]
        sound_name = context.args[1]
        
    except KeyError:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{username} format is /alias [new alias] [sound name]")
        return
        
    sound_dict = get_sound_dict()
        
    if new_alias in sound_dict:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{username} there is already a sound named '{new_alias}'")
        return
        
    if sound_name not in sound_dict:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{username} there is no sound with the name '{sound_name}'")
        return
        
    alias_dict = get_alias_dict()
    alias_dict[new_alias] = sound_name
    
    with open(alias_path, "w") as f:
        json.dump(alias_dict, f, indent=4)
        
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"@{username} '{new_alias}' has been added as an alias for '{sound_name}'")