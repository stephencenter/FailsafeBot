from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import toml

CONFIG_PATH = "Data/settings.toml"

@dataclass
class ConfigMain:
    botname: str = "Failsafe"  #  Name of the bot, if replytoname is True then the bot will respond to this string
    runtelegram: bool = True  # Whether to run the telegram bot or skip it
    rundiscord: bool = True  # Whether to run the discord bot or skip it
    maxdice: int = 100  # Maximum number of dice in one command for dice roller (bigger numbers might make messages too large for telegram)
    maxfaces: int = 10000  # Maximum number of faces for the dice for dice roller
    replytoname: bool = True  # Whether the bot should respond when their name is said
    replytomonkey: bool = False  # Whether the bot should play a monkey sound when the word monkey is said (Discworld adventure game reference)
    randreplychance: float = 0.05  # The chance for the bot to randomly reply to any message in a chat they're in (0 = no chance 1 = every message)
    vcautodc: bool = True  # Whether the bot will automatically disconnect if they're the only ones in a voice call
    ytdldownload: bool = False  # Whether the vcstream command will download the video before playing it
    requireadmin: bool = True  # Whether certain commands require admin rights to perform
    usememory: bool = True  # Whether the bot will use the memory system for AI chatting
    memorysize: int = 24  # Maximum number of messages to record in memory for AI chatting (higher is probably more expensive)
    recordall: bool = False  # Whether the bot wil record ALL messages sent in chat to memory, or just messages directed towards it
    gptmodel: str = "gpt-4o-mini"  # What GPT model to use for AI chatting
    gpttemp: float = 1.0  # Temperature for GPT chat completions (0 to 2, values outside this will break)
    gptmaxtokens: int = 1024  # Value to be passed for parameter max_completion_tokens for gpt chat completion
    maxmessagelength: int = 1024  # Maximum amount of characters to allow in a CommandResponse object's bot_message property
    usewhitelist: bool = False  # Whether a chat needs to be on the whitelist for commands to function
    minmarkov: int = 2  # Minimum number of tokens for the markov chain command /wisdom (higher takes longer exponentially)
    maxmarkov: int = 255  # Maximum number of tokens for the markov chain command /wisdom
    usemegabytes: bool = True  # Whether the /system command should use megabytes (will use gigabytes if false)
    cmdautoyes: bool = False  # Whether the /terminal command should automatically say 'y' to y/n questions (prevents hanging)
    minsimilarity: float = 0.75  # The minimum similarity threshold when searching for sound names (1.0 = exact matches only)
    saysoftcap: int = 224  # The "soft cap" for elevenlabs text-to-speech input length (soft cap only breaks on punctuation)
    sayhardcap: int = 256  # The "hard cap" for elevenlabs text-to-speech input length (hard cap breaks no matter what)
    sayvoiceid: str = "XB0fDUnXU5powFXDhCwa"  # The voice to use for elevenlabs (defaults to Charlotte)
    saymodelid: str = "eleven_multilingual_v2"  # The base model to use for elevenlabs


@dataclass
class Config:
    main: ConfigMain = field(default_factory=ConfigMain)

    def __post_init__(self):
        try:
            with Path(CONFIG_PATH).open(encoding='utf-8') as f:
                loaded = toml.load(f)

        except FileNotFoundError:
            return

        for key in loaded:
            for subkey in loaded[key]:
                if key not in self.__dict__:
                    # Remove settings that don't exist anymore
                    continue
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

def save_config(config: Config) -> None:
    with Path(CONFIG_PATH).open(mode='w', encoding='utf-8') as f:
        toml.dump(asdict(config), f)

def parse_value_input(value: str) -> int | float | bool | str:
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
