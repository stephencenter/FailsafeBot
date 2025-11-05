"""Common utilities.

This module contains a large number of constants, classes, and functions used throughout
the rest of this script. This includes important file paths, configuration, and file IO functions.
"""

from __future__ import annotations  # Python 3.14 feature for deferred annotations

import collections
import contextlib
import html
import json
import string
import tomllib
from collections.abc import AsyncGenerator, AsyncIterator, Iterable
from pathlib import Path
from typing import Any, Never

import aiofiles
import aiofiles.os
import tomli_w
import unidecode
from loguru import logger

# Do not import any internal modules, this will cause circular imports

# ==========================
# CONSTANTS
# ==========================
# region
# PROJECT CONSTANTS
COMMAND_PREFIX = '/'  # May be configurable in the future

# DIRECTORIES
PATH_DATA_FOLDER = Path("Data")
PATH_TEMP_FOLDER = PATH_DATA_FOLDER / ".temp"
PATH_SOUNDS_FOLDER = PATH_DATA_FOLDER / "Sounds"
PATH_LOGGING_FOLDER = PATH_DATA_FOLDER / "logging"
PATH_MARKOV_INPUT = PATH_DATA_FOLDER / "chat_data"  # Folder containing telegram chat logs (.json format) for markov

# CORE FILES
PATH_PYPROJECT_TOML = Path("pyproject.toml")
PATH_TELEGRAM_TOKEN = PATH_DATA_FOLDER / "telegram_token.txt"
PATH_DISCORD_TOKEN = PATH_DATA_FOLDER / "discord_token.txt"
PATH_ADMIN_LIST = PATH_DATA_FOLDER / "admins.json"
PATH_WHITELIST = PATH_DATA_FOLDER / "whitelist.json"
PATH_CONFIG_FILE = PATH_DATA_FOLDER / "settings.toml"
PATH_LOGGING_FILE = PATH_LOGGING_FOLDER / "log.txt"
PATH_USERNAME_MAP = PATH_DATA_FOLDER / "username_map.json"
PATH_TRACK_USERID = PATH_DATA_FOLDER / "track_userid.json"

# CHATTING FILES
PATH_OPENAI_KEY = PATH_DATA_FOLDER / "openai_key.txt"
PATH_ELEVENLABS_KEY = PATH_DATA_FOLDER / "eleven_key.txt"
PATH_GPT_PREPEND = PATH_DATA_FOLDER / "prepend_message.txt"
PATH_GPT_PROMPT = PATH_DATA_FOLDER / "gpt_prompt.txt"
PATH_MEMORY_LIST = PATH_DATA_FOLDER / "openai_memory.json"
PATH_RESPONSE_LIST = PATH_DATA_FOLDER / "response_list.txt"
PATH_MARKOV_CHAIN = PATH_DATA_FOLDER / "markov_chain.json"

# SOUNDS FILES
PATH_SOUND_ALIASES = PATH_DATA_FOLDER / "sound_aliases.json"
PATH_PLAYCOUNTS = PATH_DATA_FOLDER / "playcounts.json"

# TRIVIA FILES
PATH_TRIVIA_SCORES = PATH_DATA_FOLDER / "trivia_points.json"
PATH_CURRENT_TRIVIA = PATH_DATA_FOLDER / "current_trivia.json"
URL_TRIVIA = "https://opentdb.com/api.php?amount="

# D10000 FILES
PATH_D10000_LIST = PATH_DATA_FOLDER / "d10000_list.txt"
PATH_ACTIVE_EFFECTS = PATH_DATA_FOLDER / "active_effects.json"

# This message is sent if the bot is unable to create a response for whatever reason (API errors, etc)
TXT_BZZZT_ERROR = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"

# This message is sent if the user doesn't provide a sound name for /sound
TXT_SOUND_NOT_PROVIDED = (
    "I'm afraid my mindreader unit has been malfunctioning lately, what sound did you want?",
    "Use your words please.",
    "I unfortunately do not have any sounds without a name.",
)

# This message is sent if the user requests a sound that doesn't exist with /sound
TXT_SOUND_NOT_FOUND = (
    "Are you insane, do you have any idea how dangerous a sound with that name would be?",
    "I wouldn't be caught dead with a sound like that on my list.",
    "No dice. Someone probably forgot to upload it, what a fool.",
)

TXT_NO_PERMISSIONS = (
    "You don't have the right, O you don't have the right.",
    "You think I'd let just anyone do this?",
)
# endregion


# ==========================
# SETTINGS MANAGEMENT
# ==========================
# region
class ConfigError(Exception):
    """Error to be raised if loading a setting fails due to invalid values (e.g. expected float, got string)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Config:
    """Class that stores user config data for this application.

    Do not instantiate this class directly, call `await Config.load()` to create a config object.
    """

    # We have to declare these here, so that our type checker knows these attributes exist
    main: ConfigMain
    chat: ConfigChat
    misc: ConfigMisc

    def __init__(self, _: Never) -> None:
        error_msg = "Use `await Config.load()` instead of creating Config directly."
        raise RuntimeError(error_msg)

    @classmethod
    async def load(cls) -> Config:
        """Create Config object and load its contents from a file."""
        self = object.__new__(cls)
        self.main = ConfigMain()
        self.chat = ConfigChat()
        self.misc = ConfigMisc()

        # We have an await here, so we can't do this in __init__
        loaded = await try_read_toml(PATH_CONFIG_FILE, {})

        if not loaded:
            logger.warning(f"Failed to load {PATH_CONFIG_FILE}, falling back to default settings")
            return self

        # Use loaded toml file to update fields
        for key in self.__dict__:
            for subkey in self.__dict__[key].__dict__:
                if key in loaded and subkey in loaded[key]:
                    # Try to find subkey in the 'correct' location
                    target_setting: ConfigItem[Any] = self.__dict__[key].__dict__[subkey]
                    new_value = loaded[key][subkey]

                    try:
                        target_setting.validate_new_value(new_value)
                        target_setting.value = new_value
                    except ConfigError as e:
                        logger.error(e)

                else:
                    # Try to find subkey in 'incorrect' locations, in case classes had their settings moved around
                    for other_key in loaded:
                        if other_key != key and subkey in loaded[other_key]:
                            target_setting: ConfigItem[Any] = self.__dict__[key].__dict__[subkey]
                            new_value = loaded[other_key][subkey]

                            try:
                                target_setting.validate_new_value(new_value)
                                target_setting.value = new_value
                            except ConfigError as e:
                                logger.error(e)

                            break

        return self

    def find_setting(self, search_string: str) -> tuple[str | None, str | None, ConfigItem[Any] | None]:
        """Take a search string and return the matching group name, setting name, and current value if it exists.

        Accepts either the setting name or [group name].[setting name], will return the first match found
        """
        group_name: str | None = None
        setting_name: str | None = None
        cfg_item: ConfigItem[Any] | None = None

        split_string = search_string.split('.')
        if len(split_string) == 2:
            if hasattr(self, split_string[0]):
                group = getattr(self, split_string[0])
                if hasattr(group, split_string[1]):
                    group_name = split_string[0]
                    setting_name = split_string[1]
                    cfg_item = getattr(group, setting_name)

        elif len(split_string) == 1:
            for group_key in self.__dict__:
                group = getattr(self, group_key)
                if hasattr(group, search_string):
                    group_name = group_key
                    setting_name = search_string
                    cfg_item = getattr(group, setting_name)
                    break

        return group_name, setting_name, cfg_item

    async def save_config(self) -> None:
        """Write the current state of the Config object to a file."""
        settings_dict: dict[str, dict[str, Any]] = {}
        for key in self.__dict__:
            settings_dict[key] = {}

            for subkey, config_item in self.__dict__[key].__dict__.items():
                settings_dict[key][subkey] = config_item.value

        await write_toml_to_file(PATH_CONFIG_FILE, settings_dict)

    def update_setting(self, group_name: str, setting_name: str, value: str) -> None:
        target_setting: ConfigItem[Any] = getattr(getattr(self, group_name), setting_name)

        if target_setting.item_type is bool:
            if value.lower() == "true":
                new_value = True
            elif value.lower() == "false":
                new_value = False
            else:
                error_msg = f"New value '{value}' is incompatible with setting '{target_setting.name}' (true/false)"
                raise ConfigError(error_msg)

        elif target_setting.item_type is float:
            try:
                new_value = float(value)
            except ValueError as e:
                error_msg = f"New value '{value}' is incompatible with setting '{target_setting.name}' (number)"
                raise ConfigError(error_msg) from e

        elif target_setting.item_type is int:
            try:
                new_value = int(value)
            except ValueError as e:
                error_msg = f"New value '{value}' is incompatible with setting '{target_setting.name}' (integer)"
                raise ConfigError(error_msg) from e

        else:
            new_value = str(value)

        # Can raise ConfigError, must be caught by whatever calls this method
        target_setting.validate_new_value(new_value)

        # Set value, will not reach this point if above validation fails
        target_setting.value = new_value

    async def verify_settings(self) -> AsyncGenerator[str]:
        seen = {}
        for outer_key, subdict in self.__dict__.items():
            for subkey, value in subdict.__dict__.items():
                if subkey in seen:
                    yield f"Config setting {subkey} is a duplicate between '{seen[subkey]}' and '{outer_key}'"

                else:
                    seen[subkey] = outer_key

                if subkey != value.name:
                    yield f"Config setting '{subkey}' has its name incorrectly assigned as '{value.name}'"


class ConfigItem[T]:
    """Defines an individual configuration item, including default value, current value, and valid range."""

    def __init__(self, name: str,
                 *, default_value: T, description: str, valid_range: tuple[float, float] | None = None) -> None:
        self.name = name
        self.value = default_value
        self.description = description
        self.item_type = type(default_value)
        self.default_value = default_value
        self.valid_range = valid_range

        if self.item_type not in {float, int, str, bool}:
            error_msg = f"Only float, int, str, bool are accepted setting types (got {self.item_type.__name__})"
            raise ConfigError(error_msg)

        if self.valid_range is not None:
            if self.item_type not in {float, int}:
                error_msg = "valid_range != None is only valid for floats and ints."
                raise ConfigError(error_msg)

            if (num_items := len(self.valid_range)) != 2:
                error_msg = f"valid_range must have two elements: min and max (got {num_items} elements)"

            if self.valid_range[0] > self.valid_range[1]:
                error_msg = "Second item of valid_range has to be equal or larger than the first"
                raise ConfigError(error_msg)

        elif self.valid_range is None and self.item_type in {float, int}:
            error_msg = "valid_range cannot be None if item is float or int"
            raise ConfigError(error_msg)

    def __bool__(self) -> bool:
        if self.item_type is bool:
            return bool(self.value)

        error_msg = f"Use ConfigItem.value to access {self.name}'s value"
        raise RuntimeError(error_msg)

    def __repr__(self) -> str:
        return str(self.value)

    def validate_new_value(self, new_value: T) -> None:
        if not isinstance(new_value, self.item_type):
            error_msg = f"New value for setting '{self.name}' has to be of type {self.item_type.__name__}"
            raise ConfigError(error_msg)

        if self.valid_range is not None and isinstance(new_value, (float, int)):
            v_min, v_max = self.valid_range

            if not (v_min <= new_value <= v_max):
                error_msg = f"New value for setting '{self.name}' is outside valid range of {v_min} to {v_max}"
                raise ConfigError(error_msg)

    def reset_to_default(self) -> None:
        self.value = self.default_value


class ConfigList:
    """ABC for ConfigMain, ConfigChat, etc."""


class ConfigMain(ConfigList):
    """Config class for core application functionality."""

    def __init__(self) -> None:
        self.botname = ConfigItem("botname", default_value="Failsafe",
            description="Name of the bot, if replytoname is True then the bot will respond to this string")

        self.runtelegram = ConfigItem("runtelegram", default_value=True,
            description="Whether to run the Telegram bot or not")

        self.rundiscord = ConfigItem("rundiscord", default_value=True,
            description="Whether to run the Discord bot or not")

        self.whitelisttelegram = ConfigItem("whitelisttelegram", default_value=False,
            description="Whether a Telegram chat ID needs to be on the whitelist for commands to function")

        self.whitelistdiscord = ConfigItem("whitelistdiscord", default_value=False,
            description="Whether a Discord chat ID needs to be on the whitelist for commands to function")

        self.autosupertelegram = ConfigItem("autosupertelegram", default_value=True,
            description="Whether Telegram superadmin will be auto-assigned if none exist (disabled after first use)")

        self.autosuperdiscord = ConfigItem("autosuperdiscord", default_value=True,
            description="Whether Discord superadmin will be auto-assigned if none exist (disabled after first use)")

        self.requireadmin = ConfigItem("requireadmin", default_value=True,
            description="Whether certain commands require admin rights to perform")

        self.startupchecks = ConfigItem("startupchecks", default_value=True,
            description="Whether tests should be performed upon startup to detect common issues")

        self.maxmessagelength = ConfigItem("maxmessagelength", default_value=1024, valid_range=(32, 4096),
            description="Maximum amount of characters to allow in a CommandResponse object's bot_message property")


class ConfigChat(ConfigList):
    """Config class for chatting functionality (text, voice, and general memory)."""

    def __init__(self) -> None:
        self.replytoname = ConfigItem("replytoname", default_value=True,
            description="Whether the bot should respond when their name is said")

        self.replytomonkey = ConfigItem("replytomonkey", default_value=False,
            description="Whether the bot should play a sound when the word monkey is said (Discworld reference)")

        self.randreplychance = ConfigItem("randreplychance", default_value=0.05, valid_range=(0, 1),
            description="Chance for the bot to randomly reply to any message in the chat (0 -> 0%, 1.0 -> 100%)")

        self.gptmodel = ConfigItem("gptmodel", default_value="gpt-4o-mini",
            description="The GPT model to use for AI chatting")

        self.gpttemp = ConfigItem("gpttemp", default_value=1.0, valid_range=(0, 2),
            description="Temperature for GPT chat completions (0 to 2, values outside this will break)")

        self.gptmaxtokens = ConfigItem("gptmaxtokens", default_value=256, valid_range=(1, 4096),
            description="Value for parameter max_completion_tokens for GPT chat completion (1 token = ~4 chars)")

        self.usememory = ConfigItem("usememory", default_value=True,
            description="Whether the bot will use the memory system for AI chatting")

        self.memorysize = ConfigItem("memorysize", default_value=64, valid_range=(1, 4096),
            description="Maximum number of messages to record in memory")

        self.recallsize = ConfigItem("recallsize", default_value=16, valid_range=(1, 4096),
            description="Amount of messages to pull from memory for AI chatting/recall")

        self.recordall = ConfigItem("recordall", default_value=False,
            description="Whether the bot will record ALL text messages sent in chat to memory, or just directed ones")

        self.minmarkov = ConfigItem("minmarkov", default_value=2, valid_range=(1, 4096),
            description="Minimum number of tokens for the markov chain command /wisdom (higher takes longer)")

        self.maxmarkov = ConfigItem("maxmarkov", default_value=256, valid_range=(32, 4096),
            description="Maximum number of tokens for the markov chain command /wisdom")

        self.saysoftcap = ConfigItem("saysoftcap", default_value=256, valid_range=(32, 4096),
            description="The 'soft cap' for elevenlabs text-to-speech input length")

        self.sayvoiceid = ConfigItem("sayvoiceid", default_value="XB0fDUnXU5powFXDhCwa",
            description="The voice to use for elevenlabs (defaults to Charlotte)")

        self.saymodelid = ConfigItem("saymodelid", default_value="eleven_multilingual_v2",
            description="The base model to use for elevenlabs")

        self.vcautodc = ConfigItem("vcautodc", default_value=True,
            description="Whether the bot will automatically disconnect if they're the only ones in a voice call")


class ConfigMisc(ConfigList):
    """Config class for command functionality that isn't covered by other dataclasses."""

    def __init__(self) -> None:
        self.usemegabytes = ConfigItem("usemegabytes", default_value=False,
            description="Whether the /system command should use megabytes (will use gigabytes if false)")

        self.minsimilarity = ConfigItem("minsimilarity", default_value=0.75, valid_range=(0.25, 1),
            description="The minimum similarity threshold when searching for sound names (1.0 = exact matches only)")

        self.maxstreamtime = ConfigItem("maxstreamtime", default_value=30, valid_range=(5, 3600),
            description="How much of a video the /stream command will download (does not apply to /vcstream)")

        self.maxdice = ConfigItem("maxdice", default_value=100, valid_range=(1, 1000),
            description="Max number of dice at once for /roll (bigger numbers might reach message length cap)")

        self.maxfaces = ConfigItem("maxfaces", default_value=10000, valid_range=(100, 100000),
            description="Maximum number of faces for the dice for dice roller")
# endregion


# region
async def append_to_gpt_memory(*, user_prompt: str | None = None, bot_response: str | None = None) -> None:
    config = await Config.load()

    if not config.chat.usememory.value:
        return

    memory = await get_full_chat_memory()

    if user_prompt is not None:
        memory.append({"role": "user", "content": user_prompt})

    if bot_response is not None:
        memory.append({"role": "assistant", "content": bot_response})

    # We cap the amount of memory stored (configurable) for storage space purposes
    memory_point = max(0, len(memory) - config.chat.memorysize.value)
    memory = memory[memory_point:]

    # Write the AI's memory to a file so it can be retrieved later
    await write_json_to_file(PATH_MEMORY_LIST, memory)


async def get_full_chat_memory() -> list[dict[str, str]]:
    """Load and return the AI's full memory."""
    return await try_read_json(PATH_MEMORY_LIST, [])


async def get_recall_chat_memory() -> list[dict[str, str]]:
    """Load and return the most recent messages from the AI's memory.

    The number of messages retrieved is configurable -- this allows for the AI to only have access
    to a portion of the full stored memory, which is useful for limiting API input token count
    """
    config = await Config.load()
    memory_list = await try_read_json(PATH_MEMORY_LIST, [])

    recall_point = max(0, len(memory_list) - config.chat.recallsize.value)
    return memory_list[recall_point:]


def convert_to_ascii(text: str) -> str:
    """Attempt to replace all non-ascii characters in string with ascii equivalents (e.g. 'é' -> 'e').

    Removes all characters that have no good equivalents.
    """
    text = html.unescape(text)
    return unidecode.unidecode(text, errors="replace", replace_str='')


def make_valid_filename(input_str: str, *, strict: bool) -> str:
    """Return input_str with characters unsuitable for filenames replaced or removed.

    strict=False will remove all characters that are not alphanumeric, except specific special characters like '_'
    strict=True will remove all characters that are not alphanumeric with no exceptions
    """
    input_str = convert_to_ascii(input_str)

    if strict:
        return ''.join(char for char in input_str if char.isalnum())

    valid_chars = [*string.ascii_uppercase, *string.ascii_lowercase, *string.digits, *"-_()'"]
    return ''.join(char for char in input_str if char in valid_chars)


async def get_project_info() -> dict[str, str]:
    project_info: dict[str, str] = collections.defaultdict(lambda: 'Error')
    loaded_data = (await try_read_toml(PATH_PYPROJECT_TOML, {'project': {'name': 'FailsafeBot'}}))

    project_info.update(loaded_data['project'])

    return project_info


# region
async def try_read_lines_list[T](path: str | Path, default: T) -> list[str] | T:
    """Attempt to load the text data from the provided path as a list of strings, and return it.

    If this fails, return the provided default object instead.
    """
    try:
        async with aiofiles.open(path, encoding='utf-8') as f:
            lines = [x.strip() for x in await f.readlines()]
            return lines or default
    except FileNotFoundError:
        logger.error(f"Tried to open file at {path}, but file did not exist")
    except OSError:
        logger.error(f"Tried to open file at {path}, but encountered an error")

    return default


async def try_read_lines_str[T](path: str | Path, default: T) -> str | T:
    """Attempt to load the text data from the provided path as a single string, and return it.

    If this fails, return the provided default object instead.
    """
    try:
        async with aiofiles.open(path, encoding='utf-8') as f:
            string_lines = ''.join(await f.readlines())
            return string_lines or default
    except FileNotFoundError:
        logger.error(f"Tried to open file at {path}, but file did not exist")
    except OSError:
        logger.error(f"Tried to open file at {path}, but encountered an error")

    return default


async def try_read_single_line[T](path: str | Path, default: T) -> str | T:
    """Attempt to read only the first line of text data from the provided path and return it.

    If this fails, return the provided default object instead.
    """
    try:
        async with aiofiles.open(path, encoding='utf-8') as f:
            line = (await f.readline()).strip()
            return line or default
    except FileNotFoundError:
        logger.error(f"Tried to open file at {path}, but file did not exist")
    except OSError:
        logger.error(f"Tried to open file at {path}, but encountered an error")

    return default


async def try_read_bytes(path: str | Path, default: bytes) -> bytes:
    """Attempt to load bytes from the provided path and return it.

    If this fails, return the provided default bytes object instead.
    """
    try:
        async with aiofiles.open(path, mode='rb') as f:
            data = await f.read()
            return data or default
    except FileNotFoundError:
        logger.error(f"Tried to open file at {path}, but file did not exist")
    except OSError:
        logger.error(f"Tried to open file at {path}, but encountered an error")

    return default


async def try_read_json[T](path: str | Path, default: T) -> T:
    """Attempt to load a json object from the provided path and return it.

    If this fails, return the provided default object instead.
    """
    try:
        async with aiofiles.open(path, encoding='utf-8') as f:
            data = json.loads(await f.read())
            return data or default
    except FileNotFoundError:
        logger.error(f"Tried to open file at {path}, but file did not exist")
    except json.JSONDecodeError:
        logger.error(f"Tried to open file at {path}, but failed to decode json")
    except OSError:
        logger.error(f"Tried to open file at {path}, but encountered an error")

    return default


async def try_read_toml(path: str | Path, default: dict[str, Any]) -> dict[str, Any]:
    """Attempt to load a toml object from the provided path and return it as a dictionary.

    If this fails, return the provided default object instead.
    """
    try:
        async with aiofiles.open(path, encoding='utf-8') as f:
            data = tomllib.loads(await f.read())
            return data or default
    except FileNotFoundError:
        logger.error(f"Tried to open file at {path}, but file did not exist")
    except tomllib.TOMLDecodeError:
        logger.error(f"Tried to open file at {path}, but failed to decode toml")
    except OSError:
        logger.error(f"Tried to open file at {path}, but encountered an error")

    return default


async def write_lines_to_file(path: str | Path, lines: list[str]) -> None:
    with contextlib.suppress(FileExistsError):
        await aiofiles.os.mkdir(Path(path).parent)

    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        await f.writelines(f"{x}\n" for x in lines)


async def write_text_to_file(path: str | Path, text: str) -> None:
    with contextlib.suppress(FileExistsError):
        await aiofiles.os.mkdir(Path(path).parent)

    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        await f.write(text)


async def append_lines_to_file(path: str | Path, lines: list[str]) -> None:
    with contextlib.suppress(FileExistsError):
        await aiofiles.os.mkdir(Path(path).parent)

    async with aiofiles.open(path, mode='a', encoding='utf-8') as f:
        await f.writelines(f"{x}\n" for x in lines)


async def write_bytes_to_file(path: str | Path, byte_obj: AsyncIterator[bytes] | bytes | bytearray) -> None:
    with contextlib.suppress(FileExistsError):
        await aiofiles.os.mkdir(Path(path).parent)

    async with aiofiles.open(path, "wb") as f:
        if isinstance(byte_obj, AsyncIterator):
            async for chunk in byte_obj:
                await f.write(chunk)
        else:
            await f.write(byte_obj)


async def write_json_to_file(path: str | Path, data: Iterable[Any]) -> None:
    with contextlib.suppress(FileExistsError):
        await aiofiles.os.mkdir(Path(path).parent)

    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        content = json.dumps(data, indent=4)
        await f.write(content)


async def write_toml_to_file(path: str | Path, data: dict[str, Any]) -> None:
    """Write provided dictionary to TOML file.

    Does not preserve style or comments.
    """
    with contextlib.suppress(FileExistsError):
        await aiofiles.os.mkdir(Path(path).parent)

    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        content = tomli_w.dumps(data)
        await f.write(content)
# endregion
