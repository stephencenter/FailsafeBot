from dataclasses import dataclass, field, asdict
from typing import Any
import toml

CONFIG_PATH = "Data/settings.toml"

@dataclass
class ConfigMain:
    botname: str = "Failsafe"  #  Name of the bot, if replytoname is True then the bot will respond to this string
    runtelegram: bool = True  # Whether to run the telegram bot or skip it
    rundiscord: bool = True  # Whether to run the discord bot or skip it
    uselogging: bool = True  # Whether to utilize the logging module or not
    maxdice: int = 100  # Maximum number of dice in one command for dice roller (bigger numbers might make messages too large for telegram)
    maxfaces: int = 10000  # Maximum number of faces for the dice for dice roller
    replytoname: bool = True  # Whether the bot should respond when their name is said
    replytomonkey: bool = False  # Whether the bot should play a monkey sound when the word monkey is said (Discworld adventure game reference)
    vcautodc: bool = True  # Whether the bot will automatically disconnect if they're the only ones in a voice call
    ytdldownload: bool = False  # Whether the vcstream command will download the video before playing it
    requireadmin: bool = True  # Whether certain commands require admin rights to perform. Note that some commands like /terminal are extremely dangerous in untrustworthy hands
    usememory: bool = True  # Whether the bot will use the memory system for AI chatting
    memorysize: int = 24  # Maximum number of messages to record in memory for AI chatting (higher is probably more expensive)
    gptmodel: str = "gpt-4o-mini"  # What GPT model to use for AI chatting
    usewhitelist: bool = False  # Whether a chat needs to be on the whitelist for commands to function
    minmarkov: int = 2  # Minimum number of tokens for the markov chain command /wisdom (higher takes longer exponentially)
    maxmarkov: int = 255  # Maximum number of tokens for the markov chain command /wisdom
    usemegabytes: bool = True  # Whether the /system command should use megabytes (will use gigabytes if false)
    cmdautoyes: bool = False  # Whether the /terminal command should automatically say 'y' to y/n questions (prevents hanging)

@dataclass
class Config:
    main: ConfigMain = field(default_factory=ConfigMain)

    def __post_init__(self):
        try:
            with open(CONFIG_PATH, mode='r', encoding='utf-8') as f:
                loaded = toml.load(f)

        except FileNotFoundError:
            return

        for key in loaded:
            for subkey in loaded[key]:
                self.__dict__[key].__dict__[subkey] = loaded[key][subkey]

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
