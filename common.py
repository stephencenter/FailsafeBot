import json
import random
from collections.abc import Awaitable, Callable, Generator, Iterable
from dataclasses import asdict, dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any

import discord
import toml
from discord.errors import HTTPException
from discord.ext.commands import Bot as DiscordBot
from discord.ext.commands import Context as DiscordContext
from loguru import logger
from telegram import Update as TelegramUpdate
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import Application as TelegramBot
from telegram.ext import CallbackContext as TelegramContext

# PROJECT VARIABLES
APPLICATION_NAME = "FailsafeBot"
VERSION_NUMBER = "v1.1.7"

# DIRECTORIES
DATA_FOLDER_PATH = Path('Data')
TEMP_FOLDER_PATH = DATA_FOLDER_PATH / '.temp'
SOUNDS_FOLDER_PATH = DATA_FOLDER_PATH / 'Sounds'
LOGGING_FOLDER_PATH = DATA_FOLDER_PATH / 'logging'

# CORE FILES
TELEGRAM_TOKEN_PATH = DATA_FOLDER_PATH / "telegram_token.txt"
DISCORD_TOKEN_PATH = DATA_FOLDER_PATH / "discord_token.txt"
ADMINS_PATH = DATA_FOLDER_PATH / "admins.txt"
TELEGRAM_WHITELIST_PATH = DATA_FOLDER_PATH / "tg_whitelist.txt"
CONFIG_PATH = DATA_FOLDER_PATH / "settings.toml"
LOGGING_FILE_PATH = LOGGING_FOLDER_PATH / "log.txt"
USERNAME_MAP_PATH = DATA_FOLDER_PATH / "username_map.json"
TRACK_USERID_PATH = DATA_FOLDER_PATH / "track_userid.json"

# CHATTING FILES
OPENAI_KEY_PATH = DATA_FOLDER_PATH / "openai_key.txt"
ELEVENLABS_KEY_PATH = DATA_FOLDER_PATH / "eleven_key.txt"
PREPEND_PATH = DATA_FOLDER_PATH / "prepend_message.txt"
GPT_PROMPT_PATH = DATA_FOLDER_PATH / "gpt_prompt.txt"
MARKOV_PATH = DATA_FOLDER_PATH / "markov_chain.json"
MEMORY_PATH = DATA_FOLDER_PATH / "openai_memory.json"
RESPONSES_PATH = DATA_FOLDER_PATH / "response_list.txt"

# SOUNDS FILES
ALIAS_PATH = DATA_FOLDER_PATH / "sound_aliases.json"
PLAYCOUNTS_PATH = DATA_FOLDER_PATH / "playcounts.json"

# TRIVIA FILES
TRIVIA_POINTS_PATH = DATA_FOLDER_PATH / "trivia_points.json"
TRIVIA_CURRENT_PATH = DATA_FOLDER_PATH / "current_trivia.json"
TRIVIA_MEMORY_PATH = DATA_FOLDER_PATH / "trivia_memory.txt"
TRIVIA_URL = "https://opentdb.com/api.php?amount="

# D10000 FILES
D10000_LIST_PATH = DATA_FOLDER_PATH / "d10000_list.txt"
ACTIVE_EFFECTS_PATH = DATA_FOLDER_PATH / "active_effects.json"

# CONSTANTS
BZZZT_MESSAGE_TEXT = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"


# ==========================
# EXCEPTION TYPES
# ==========================
# region
class InvalidBotTypeError(TypeError):
    # This exception type should be raised if a function expects a TelegramBot or DiscordBot but gets something else instead
    def __init__(self, message: str | None = None):
        self.message = f"{APPLICATION_NAME} currently supports only Telegram and Discord bots"
        if message is not None:
            self.message = message
        super().__init__(self.message)
# endregion


# ==========================
# SETTINGS MANAGEMENT
# ==========================
# region
@dataclass
class ConfigMain:
    """Config dataclass for core application functionality."""

    botname: str = "Failsafe"  # Name of the bot, if replytoname is True then the bot will respond to this string
    runtelegram: bool = True  # Whether to run the telegram bot or skip it
    rundiscord: bool = True  # Whether to run the discord bot or skip it
    requireadmin: bool = True  # Whether certain commands require admin rights to perform
    maxmessagelength: int = 1024  # Maximum amount of characters to allow in a CommandResponse object's bot_message property
    usewhitelist: bool = False  # Whether a Telegram chat needs to be on the whitelist for commands to function


@dataclass
class ConfigChat:
    """Config dataclass for chatting functionality (text, voice, and general memory)."""

    replytoname: bool = True  # Whether the bot should respond when their name is said
    replytomonkey: bool = False  # Whether the bot should play a monkey sound when the word monkey is said (Discworld adventure game reference)
    randreplychance: float = 0.05  # The chance for the bot to randomly reply to any message in a chat they're in (0 = no chance 1 = every message)
    gptmodel: str = "gpt-4o-mini"  # What GPT model to use for AI chatting
    gpttemp: float = 1.0  # Temperature for GPT chat completions (0 to 2, values outside this will break)
    gptmaxtokens: int = 512  # Value to be passed for parameter max_completion_tokens for gpt chat completion
    usememory: bool = True  # Whether the bot will use the memory system for AI chatting
    memorysize: int = 24  # Maximum number of messages to record in memory for AI chatting (higher is probably more expensive)
    recordall: bool = False  # Whether the bot wil record ALL messages sent in chat to memory, or just messages directed towards it
    minmarkov: int = 2  # Minimum number of tokens for the markov chain command /wisdom (higher takes longer exponentially)
    maxmarkov: int = 256  # Maximum number of tokens for the markov chain command /wisdomly)
    saysoftcap: int = 224  # The "soft cap" for elevenlabs text-to-speech input length (soft cap only breaks on punctuation)
    sayhardcap: int = 256  # The "hard cap" for elevenlabs text-to-speech input length (hard cap breaks no matter what)
    sayvoiceid: str = "XB0fDUnXU5powFXDhCwa"  # The voice to use for elevenlabs (defaults to Charlotte)
    saymodelid: str = "eleven_multilingual_v2"  # The base model to use for elevenlabs
    vcautodc: bool = True  # Whether the bot will automatically disconnect if they're the only ones in a voice call


@dataclass
class ConfigMisc:
    """Config dataclass for command functionality that isn't covered by other dataclasses."""

    usemegabytes: bool = True  # Whether the /system command should use megabytes (will use gigabytes if false)
    minsimilarity: float = 0.75  # The minimum similarity threshold when searching for sound names (1.0 = exact matches on
    maxstreamtime: int = 30  # How much of a video the /stream command will download (does not apply to /vcstream)
    maxdice: int = 100  # Maximum number of dice in one command for dice roller (bigger numbers might make messages too large for telegram)
    maxfaces: int = 10000  # Maximum number of faces for the dice for dice roller
    cmdautoyes: bool = False  # Whether the /terminal command should automatically say 'y' to y/n questions (prevents hanging)


@dataclass
class Config:
    main: ConfigMain = field(default_factory=ConfigMain)
    chat: ConfigChat = field(default_factory=ConfigChat)
    misc: ConfigMisc = field(default_factory=ConfigMisc)

    def __post_init__(self):
        try:
            with CONFIG_PATH.open(encoding='utf-8') as f:
                loaded = toml.load(f)

        except (FileNotFoundError, toml.TomlDecodeError):
            return

        for key in self.__dict__:
            for subkey in self.__dict__[key].__dict__:
                if key in loaded and subkey in loaded[key]:
                    # Try to find subkey in the 'correct' location
                    self.__dict__[key].__dict__[subkey] = loaded[key][subkey]
                else:
                    # Try to find subkey in 'incorrect' locations, in case the dataclasses had their settings moved around
                    for other_key in loaded:
                        if other_key != key and subkey in loaded[other_key]:
                            self.__dict__[key].__dict__[subkey] = loaded[other_key][subkey]
                            break

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
    with CONFIG_PATH.open(mode='w', encoding='utf-8') as f:
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


def verify_settings() -> Generator[str]:
    seen = {}
    config = Config()

    for outer_key, subdict in config.__dict__.items():
        for subkey in subdict.__dict__:
            if subkey in seen:
                yield f"Config setting {subkey} is a duplicate between '{seen[subkey]}' and '{outer_key}'"
            else:
                seen[subkey] = outer_key
# endregion


# ==========================
# COMMANDS & RESPONSES
# ==========================
# region
class CommandResponse:
    def __init__(self, user_message: str, bot_message: str, *, record_to_memory: bool = True, send_to_chat: bool = True):
        self.user_message: str = user_message
        self.bot_message: str = bot_message
        self.record_to_memory: bool = record_to_memory  # Whether user_message and bot_message should be recorded to memory
        self.send_to_chat: bool = send_to_chat  # Whether bot_message should be sent to chat


class FileResponse(CommandResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str | Path, *, record_to_memory: bool = True, temp: bool = False,
                 send_to_chat: bool = False):
        super().__init__(user_message, bot_message, record_to_memory=record_to_memory, send_to_chat=send_to_chat)
        self.file_path: str | Path = file_path  # The path of the file to send
        self.temp: bool = temp  # Whether the file should be deleted after being sent


class SoundResponse(FileResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str | Path, *, record_to_memory: bool = True, temp: bool = False,
                 send_to_chat: bool = False):
        super().__init__(user_message, bot_message, file_path, record_to_memory=record_to_memory, temp=temp, send_to_chat=send_to_chat)


class NoPermissionsResponse(CommandResponse):
    def __init__(self):
        chosen_response = random.choice([
            "You don't have the right, O you don't have the right.",
            "You think I'd let just anyone do this?",
        ])
        super().__init__("Can I do that sensitive thing that requires admin rights?", chosen_response, record_to_memory=True, send_to_chat=True)


class NoResponse(CommandResponse):
    def __init__(self):
        super().__init__('', '', record_to_memory=False, send_to_chat=False)


class UserCommand:
    def __init__(self, target_bot: TelegramBot | DiscordBot, context: TelegramContext | DiscordContext, update: TelegramUpdate | None = None):
        if isinstance(target_bot, TelegramBot) and update is None:
            error_msg = "Update cannot be None when sending message to telegram bot"
            raise ValueError(error_msg)

        if isinstance(target_bot, TelegramBot) != isinstance(context, TelegramContext):
            error_msg = "Context type and bot type must match"
            raise TypeError(error_msg)

        if isinstance(target_bot, DiscordBot) != isinstance(context, DiscordContext):
            error_msg = "Context type and bot type must match"
            raise TypeError(error_msg)

        if not isinstance(target_bot, TelegramBot) and not isinstance(target_bot, DiscordBot):
            raise InvalidBotTypeError

        self.target_bot = target_bot
        self.context = context
        self.update = update
        self.response: CommandResponse | None = None

        self.track_user_id()

    def track_user_id(self) -> None:
        id_dict = try_read_json(TRACK_USERID_PATH, {})
        username = self.get_user_name().lower()
        user_id = self.get_user_id()

        if username in id_dict:
            if isinstance(self.target_bot, TelegramBot):
                id_dict[username]["telegram"] = user_id

            if isinstance(self.target_bot, DiscordBot):
                id_dict[username]["discord"] = user_id

        else:
            if isinstance(self.target_bot, TelegramBot):
                id_dict[username] = {"telegram": user_id}
            if isinstance(self.target_bot, DiscordBot):
                id_dict[username] = {"discord": user_id}

        write_json_to_file(TRACK_USERID_PATH, id_dict)

    def get_user_name(self, *, map_name: bool = False) -> str:
        # Returns the username of the user that sent the command or message
        if isinstance(self.update, TelegramUpdate):
            username = self.update.message.from_user.username

        elif isinstance(self.context, DiscordContext):
            username = self.context.author.name

        else:
            raise InvalidBotTypeError

        if username is None:
            return ''

        if map_name:
            return self.map_username(username)

        return username

    def get_user_id(self) -> str:
        # Returns the user ID of the user that sent the command or message
        if isinstance(self.update, TelegramUpdate):
            user_id = str(self.update.message.from_user.id)

        elif isinstance(self.context, DiscordContext):
            user_id = str(self.context.author.id)

        else:
            raise InvalidBotTypeError

        return user_id

    def get_id_by_username(self, username: str) -> str | None:
        # Attempt to retrieve the ID belonging to the provided username
        # This ID is platform-specific (Discord, Telegram) and can only be retrieved if the user has interacted with this bot before
        id_dict = try_read_json(TRACK_USERID_PATH, {})

        if username not in id_dict:
            return None

        if isinstance(self.target_bot, TelegramBot) and "telegram" in id_dict[username]:
            return id_dict[username]["telegram"]

        if isinstance(self.target_bot, DiscordBot) and "discord" in id_dict[username]:
            return id_dict[username]["discord"]

        return None

    def is_private(self) -> bool:
        # Returns whether the command was called in a private chat or a group chat
        if isinstance(self.update, TelegramUpdate):
            return self.update.message.chat.type == "private"

        if isinstance(self.context, DiscordContext):
            return self.context.guild is None

        raise InvalidBotTypeError

    def get_args_list(self) -> list[str]:
        # Returns the list of arguments provided with the command
        # Ex. /test a b c -> ['a', 'b', 'c']
        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            return self.context.args

        if isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            return self.context.message.content.split()[1:]

        raise InvalidBotTypeError

    def get_first_arg(self, *, lowercase: bool = False) -> str | None:
        # Returns the first element from the argument list, all lowercase if lowercase=True
        # Ex. /test a b c -> 'a'
        args_list = []

        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            args_list = self.context.args

        elif isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            args_list = self.context.message.content.split()[1:]

        else:
            raise InvalidBotTypeError

        try:
            if lowercase:
                return args_list[0].lower()
            return args_list[0]

        except IndexError:
            return None

    def get_user_message(self) -> str:
        # Returns the message that this user sent with this UserCommand
        # Ex. /test a b c -> 'a b c'
        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            return ' '.join(self.context.args)

        if isinstance(self.update, TelegramUpdate) and self.update.message.text is not None:
            return self.update.message.text

        if isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            return ' '.join(self.context.message.content.split()[1:])

        raise InvalidBotTypeError

    def get_user_prompt(self) -> str | None:
        # This is used for prompting the GPT chat completion model
        sender = self.get_user_name(map_name=True)

        if self.response is not None:
            user_message = self.response.user_message
        else:
            user_message = self.get_user_message()

        if not user_message:
            return None

        return f'{sender}: {user_message}'

    def is_admin(self) -> bool:
        # Returns whether the message sender is on the bot's admin list
        user_id = self.get_user_id()
        admin_list = try_read_lines_list(ADMINS_PATH, [])

        return user_id in admin_list

    def get_chat_id(self) -> str | None:
        if isinstance(self.update, TelegramUpdate) and self.update.message is not None:
            return str(self.update.message.chat.id)

        if isinstance(self.context, DiscordContext):
            if self.context.guild is not None:
                return str(self.context.guild.id)

            return str(self.context.channel.id)

        return None

    def is_whitelisted(self) -> bool:
        # Returns whether the chat is on the bot's whitelist (telegram only)
        if not Config().main.usewhitelist:
            return True

        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None:
                return False

            chat_id = str(self.update.message.chat.id)
            whitelist = try_read_lines_list(TELEGRAM_WHITELIST_PATH, [])

            return chat_id in whitelist

        return True

    async def send_text_response(self, response: str | None) -> None:
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_message(chat_id=self.update.effective_chat.id, text=response)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(response)

        else:
            raise InvalidBotTypeError

    async def send_file_response(self, response: FileResponse, text: str | None) -> None:
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_document(chat_id=self.update.effective_chat.id, document=response.file_path, caption=text)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise InvalidBotTypeError

        # Delete the file that was sent if it was a temporary file
        if response.temp:
            Path(response.file_path).unlink()

    async def send_sound_response(self, response: SoundResponse, text: str | None) -> None:
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_voice(chat_id=self.update.effective_chat.id, voice=response.file_path, caption=text)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise InvalidBotTypeError

        # Delete the file that was sent if it was a temporary file
        if response.temp:
            Path(response.file_path).unlink()

    def is_telegram(self) -> bool:
        # Returns whether this UserCommand object was sent to a Telegram bot or not
        return isinstance(self.target_bot, TelegramBot)

    def is_discord(self) -> bool:
        # Returns whether this UserCommand object was sent to a Discord bot or not
        return isinstance(self.target_bot, DiscordBot)

    def get_user_voice_channel(self) -> discord.VoiceChannel | None:
        # Returns the voice channel that the user who sent this UserCommand is currently in
        if not isinstance(self.context, DiscordContext):
            return None

        author = self.context.author
        if not isinstance(author, discord.Member):
            return None

        if not isinstance(author.voice, discord.VoiceState):
            return None

        if not isinstance(author.voice.channel, discord.VoiceChannel):
            return None

        return author.voice.channel

    def get_bot_voice_client(self) -> discord.VoiceClient | None:
        # Returns the voice channel that the bot this UserCommand was sent to is currently in
        if not isinstance(self.context, DiscordContext):
            return None

        if not isinstance(self.context.voice_client, discord.VoiceClient):
            return None

        return self.context.voice_client

    def map_username(self, username: str) -> str:
        username_map = try_read_json(USERNAME_MAP_PATH, {})

        try:
            corrected_name = username_map[username.lower()]
        except KeyError:
            return username

        return corrected_name


def requireadmin(function: Callable[[UserCommand], Awaitable[CommandResponse]]) -> Callable:
    # Put this decorator on a function using @requireadmin to prevent its use without admin rights
    @wraps(function)
    async def admin_wrapper(user_command: UserCommand) -> CommandResponse:
        if Config().main.requireadmin and not user_command.is_admin():
            return NoPermissionsResponse()

        return await function(user_command)

    admin_wrapper.requireadmin = True  # type: ignore | Used to flag whether a function requries admin rights or not
    return admin_wrapper


async def send_response(command_function: Callable[[UserCommand], Awaitable[CommandResponse]], user_command: UserCommand) -> None:
    config = Config()
    user_command.response = await command_function(user_command)

    if user_command.response is None:
        error_message = "Command did not return a CommandResponse object"
        raise TypeError(error_message)

    if user_command.response.send_to_chat and user_command.response.bot_message:
        text_response = user_command.response.bot_message

        if len(text_response) > config.main.maxmessagelength:
            text_response = text_response[:config.main.maxmessagelength]
            logger.info(f"Cut off bot response at {config.main.maxmessagelength} characters")

    else:
        text_response = None

    try:
        # Respond with a sound effect
        if isinstance(user_command.response, SoundResponse):
            await user_command.send_sound_response(user_command.response, text_response)

        # Respond with a file
        elif isinstance(user_command.response, FileResponse):
            await user_command.send_file_response(user_command.response, text_response)

        # Respond with text
        elif text_response:
            await user_command.send_text_response(text_response)

    except (BadRequest, TimedOut, NetworkError, HTTPException) as e:
        await user_command.send_text_response(BZZZT_MESSAGE_TEXT)

        # Re-raise BadRequests, as these indicate a bug with the script that will need to be fixed
        if e is BadRequest:
            raise

    # Add the command and its response to memory if necessary
    if user_command.response.record_to_memory:
        user_prompt = user_command.get_user_prompt()
        append_to_gpt_memory(user_prompt=user_prompt, bot_prompt=user_command.response.bot_message)


def command_wrapper(bot: TelegramBot | DiscordBot, command: Callable[[UserCommand], Awaitable[CommandResponse]]) -> Callable:
    if isinstance(bot, TelegramBot):
        async def telegram_wrapper(update: TelegramUpdate, context: TelegramContext) -> None:
            if update.message is None:
                return

            user_command = UserCommand(bot, context, update=update)
            if not user_command.is_whitelisted():
                # Telegram doesn't allow you to make "private" bots, meaning anyone can add your bot to their chat
                # and use up your CPU time. This check prevents the bot from responding to commands unless it comes
                # from a whitelisted chat
                logger.warning(f"whitelist rejected {update.message.chat.id}")
                return

            await send_response(command, user_command)

        return telegram_wrapper

    if isinstance(bot, DiscordBot):
        async def discord_wrapper(context: DiscordContext) -> None:
            user_command = UserCommand(bot, context)
            await send_response(command, user_command)

        return discord_wrapper

    raise InvalidBotTypeError
# endregion


# region
def append_to_gpt_memory(*, user_prompt: str | None = None, bot_prompt: str | None = None) -> None:
    config = Config()

    if not config.chat.usememory:
        return

    memory = get_gpt_memory()

    if user_prompt is not None:
        memory.append({"role": "user", "content": user_prompt})

    if bot_prompt is not None:
        memory.append({"role": "assistant", "content": bot_prompt})

    # The AI's memory has a size limit to keep API usage low, and to keep it from veering off track too much
    if (size := len(memory)) > config.chat.memorysize:
        memory = memory[size - config.chat.memorysize:]

    # Write the AI's memory to a file so it can be retrieved later
    write_json_to_file(MEMORY_PATH, memory)


def get_gpt_memory() -> list[dict]:
    # Load the AI's memory (if it exists)
    config = Config()

    if config.chat.usememory:
        return try_read_json(MEMORY_PATH, [])

    return []


def try_read_json[T](path: str | Path, default: T) -> T:
    # Attempt to load a json object from the provided path and return it
    # If this fails, return the provided default object instead
    try:
        with Path(path).open(encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default

    if data:
        return data
    return default


def try_read_lines_list[T](path: str | Path, default: T) -> list | T:
    # Attempt to load the text data from the provided path, treating each line as a separate element in a list, and return it
    # If this fails, return the provided default object instead
    try:
        with Path(path).open(encoding='utf-8') as f:
            lines = [x.strip() for x in f]
    except OSError:
        return default

    if lines:
        return lines
    return default


def try_read_lines_str[T](path: str | Path, default: T) -> str | T:
    # Attempt to load the text data from the provided path, treating the entire text file as a single string, and return it
    # If this fails, return the provided default object instead
    try:
        with Path(path).open(encoding='utf-8') as f:
            string_lines = ''.join(f.readlines())
    except OSError:
        return default

    if string_lines:
        return string_lines
    return default


def try_read_single_line[T](path: str | Path, default: T) -> str | T:
    # Attempt to read only the first line of text data from the provided path and return it
    # If this fails, return the provided default object instead
    try:
        with Path(path).open(encoding='utf-8') as f:
            line = f.readline().strip()
    except OSError:
        return default

    if line:
        return line
    return default


def write_json_to_file(path: str | Path, data: Iterable) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def write_lines_to_file(path: str | Path, lines: list) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', encoding='utf-8') as f:
        f.writelines(f"{x}\n" for x in lines)


def write_text_to_file(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', encoding='utf-8') as f:
        f.write(text)
# endregion
