from dataclasses import dataclass, field, asdict
from typing import Any
import toml

CONFIG_PATH = "Data/settings.toml"

@dataclass
class ConfigMain:
    botname: str = "Failsafe"  #  Name of the bot, if replytoname is True then the bot will respond to this string
    maxdice: int = 100  # Maximum number of dice in one command for dice roller
    maxfaces: int = 10000  # Maximum number of faces for the dice for dice roller
    replytoname: bool = True  # Whether the bot should respond when their name is said
    replytomonkey: bool = False  # Whether the bot should play a monkey sound when the word monkey is said (Discworld adventure game reference)
    vcautodc: bool = True  # Whether the bot will automatically disconnect if they're the only ones in a voice call
    ytdldownload: bool = False  # Whether the vcstream command will download the video before playing it
    requireadmin: bool = True  # Whether certain commands require admin rights to perform
    usememory: bool = True  # Whether the bot will use the memory system for AI chatting
    memorysize: int = 10  # Maximum number of messages to record in memory for AI chatting
    gptmodel: str = "gpt-4o-mini"  # What GPT model to use for AI chatting

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

    def apply_settings(self, dictionary: dict):
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
