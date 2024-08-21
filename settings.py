import random
from dataclasses import dataclass, field, asdict
from typing import Any
import toml
import helpers

CONFIG_PATH = "Data/settings.toml"

@dataclass
class ConfigMain:
    botname: str = "Failsafe"  # Name of the bot, if replytoname is True then the bot will respond to this string
    maxdice: int = 100  # Maximum number of dice in one command for dice roller
    maxfaces: int = 10000  # Maximum number of faces for the dice for dice roller
    memorysize: int = 10  # Maximum number of messages to record in memory for AI chatting
    replytoname: bool = True  # Whether the bot should respond when their name is said
    replytomonkey: bool = False  # Whether the bot should play a monkey sound when the word monkey is said (Discworld adventure game reference)
    vcautodc: bool = True  # Whether the bot will automatically disconnect if they're the only ones in a voice call
    ytdldownload: bool = False  # Whether the vcstream command will download the video before playing it

@dataclass
class Config:
    main: ConfigMain = field(default_factory=ConfigMain)

    def find_setting(self, search_string: str) -> tuple[str | None, str | None, Any]:
        # Provide a search string (either the setting name or [group name].[setting name]) and
        # this method will return the group name, setting name, and current value if it exists
        group_name = None
        setting_name = None
        value = None

        split_string = search_string.split('.')
        if len(split_string) == 2:
            if hasattr(self, split_string[0]):
                group = getattr(self, split_string[0])
                if hasattr(group, split_string[1]):
                    group_name = split_string[0]
                    setting_name = split_string[1]
                    value = getattr(group, setting_name)

        elif len(split_string) == 1:
            for group_key in self.__dict__:
                group = getattr(self, group_key)
                if hasattr(group, search_string):
                    group_name = group_key
                    setting_name = search_string
                    value = getattr(group, setting_name)

        return group_name, setting_name, value

    def apply_settings(self, dictionary):
        for key in dictionary:
            for subkey in dictionary[key]:
                self.__dict__[key].__dict__[subkey] = dictionary[key][subkey]

def get_config() -> Config:
    config = Config()

    try:
        with open(CONFIG_PATH, mode='r', encoding='utf-8') as f:
            loaded = toml.load(f)

    except FileNotFoundError:
        return config

    config.apply_settings(loaded)

    return config

def save_config(config: Config):
    with open(CONFIG_PATH, mode='w', encoding='utf-8') as f:
        toml.dump(asdict(config), f)

async def getconfig_command(context, update=None) -> helpers.CommandResponse:
    user_message = "Can you tell me the value of that setting?"
    if not await helpers.is_admin(context, update):
        return helpers.CommandResponse(user_message, random.choice(helpers.TXT_NO_PERMISSIONS))

    args_list = await helpers.get_args_list(context, update)

    try:
        search_string = args_list[0]
    except IndexError:
        return helpers.CommandResponse(user_message, "You need to provide a setting name to check.")

    config = get_config()
    group_name, setting_name, value = config.find_setting(search_string)

    user_message = f"Can you tell me the value of the setting {search_string}?"
    if value is None:
        return helpers.CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    return helpers.CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' is currently set to '{value}'.")

async def setconfig_command(context, update=None) -> helpers.CommandResponse:
    user_message = "Can you change the value of that setting?"
    if not await helpers.is_admin(context, update):
        return helpers.CommandResponse(user_message, random.choice(helpers.TXT_NO_PERMISSIONS))

    args_list = await helpers.get_args_list(context, update)

    try:
        search_string = args_list[0]
        new_value = ' '.join(args_list[1:])
    except IndexError:
        return helpers.CommandResponse(user_message, "Format is /setconfig [setting] [new value]")

    config = get_config()
    group_name, setting_name, _ = config.find_setting(search_string)

    user_message = f"Can you change the value of the setting {search_string}?"
    if group_name is None or setting_name is None:
        return helpers.CommandResponse(user_message, f"Couldn't find a setting called '{search_string}'.")

    new_value = parse_value_input(new_value)

    setattr(getattr(config, group_name), setting_name, new_value)
    save_config(config)

    return helpers.CommandResponse(user_message, f"Setting '{group_name}.{setting_name}' has been set to '{new_value}'.")

def parse_value_input(value: str):
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        pass

    return value

async def configlist_command(context, update=None) -> helpers.CommandResponse:
    config = get_config()

    setting_list = []
    for group in config.__dict__:
        for setting in getattr(config, group).__dict__:
            setting_list.append(f"{group}.{setting}")

    setting_list = '\n-- '.join(setting_list)
    return helpers.CommandResponse('', f"Here is a list of all available settings: \n-- {setting_list}")
