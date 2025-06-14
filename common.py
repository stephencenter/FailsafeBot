"""Common utilities.

This module contains a large number of constants, classes, and functions used throughout
the rest of this script. This includes important file paths, UserCommand/CommandResponse classes,
and file IO functions.
"""

from __future__ import annotations  # Python 3.14 feature for deferred annotations

import contextlib
import dataclasses
import functools
import html
import json
import random
import string
import types
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
import discord
import toml
import unidecode
from discord.errors import HTTPException
from discord.ext.commands import Bot as DiscordBot
from discord.ext.commands import Context as DiscordContext
from loguru import logger
from telegram import Update as TelegramUpdate
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import Application as TelegramBot
from telegram.ext import CallbackContext as TelegramContext

# Do not import any internal modules, this will cause circular imports

# ==========================
# CONSTANTS
# ==========================
# region
# PROJECT VARIABLES
APPLICATION_NAME = "FailsafeBot"
VERSION_NUMBER = "v1.1.17"
COMMAND_PREFIX = '/'  # May be configurable in the future

# DIRECTORIES
PATH_DATA_FOLDER = Path("Data")
PATH_TEMP_FOLDER = PATH_DATA_FOLDER / ".temp"
PATH_SOUNDS_FOLDER = PATH_DATA_FOLDER / "Sounds"
PATH_LOGGING_FOLDER = PATH_DATA_FOLDER / "logging"
PATH_MARKOV_INPUT = PATH_DATA_FOLDER / "chat_data"  # Folder containing telegram chat logs (.json format) for markov

# CORE FILES
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
@dataclass
class ConfigMain:
    """Config dataclass for core application functionality."""

    # Name of the bot, if replytoname is True then the bot will respond to this string
    botname: str = "Failsafe"
    # botname : str = (def_type=str, def_val="Failsafe", cur_val="Failsafe", valid_range=None)

    # Whether to run the Telegram/Discord bot or skip it
    runtelegram: bool = True
    rundiscord: bool = True

    # Whether certain commands require admin rights to perform
    requireadmin: bool = True

    # Maximum amount of characters to allow in a CommandResponse object's bot_message proper
    maxmessagelength: int = 1024

    # Whether a Telegram/Discord chat ID needs to be on the whitelist for commands to function
    whitelisttelegram: bool = False
    whitelistdiscord: bool = False

    # Whether Telegram/Discord superadmin rights will be auto-assigned if none exist (disabled after first use)
    autosupertelegram: bool = True
    autosuperdiscord: bool = True


@dataclass
class ConfigChat:
    """Config dataclass for chatting functionality (text, voice, and general memory)."""

    # Whether the bot should respond when their name is said
    replytoname: bool = True

    # Whether the bot should play a sound when the word monkey is said (Discworld adventure game reference)
    replytomonkey: bool = False

    # Chance for the bot to randomly reply to any message in a chat they're in (0 -> 0%, 1.0 -> 100%)
    randreplychance: float = 0.05

    # What GPT model to use for AI chatting
    gptmodel: str = "gpt-4o-mini"

    # Temperature for GPT chat completions (0 to 2, values outside this will break)
    gpttemp: float = 1.0

    # Value to be passed for parameter max_completion_tokens for gpt chat completion (1 token = ~4 chars)
    gptmaxtokens: int = 256

    # Whether the bot will use the memory system for AI chatting
    usememory: bool = True

    # Maximum number of messages to record in memory
    memorysize: int = 64

    # Amount of messages to pull from memory for AI chatting/recall (higher uses more input tokens/money)
    recallsize: int = 16

    # Whether the bot wil record ALL text messages sent in chat to memory, or just messages directed towards it
    recordall: bool = False

    # Minimum number of tokens for the markov chain command /wisdom (higher takes longer exponentially)
    minmarkov: int = 2

    # Maximum number of tokens for the markov chain command /wisdom)
    maxmarkov: int = 256

    # The "soft cap" for elevenlabs text-to-speech input length (higher = higher cost/credit usage)
    saysoftcap: int = 256

    # The voice to use for elevenlabs (defaults to Charlotte)
    sayvoiceid: str = "XB0fDUnXU5powFXDhCwa"

    # The base model to use for elevenlabs
    saymodelid: str = "eleven_multilingual_v2"

    # Whether the bot will automatically disconnect if they're the only ones in a voice call
    vcautodc: bool = True


@dataclass
class ConfigMisc:
    """Config dataclass for command functionality that isn't covered by other dataclasses."""

    # Whether the /system command should use megabytes (will use gigabytes if false)
    usemegabytes: bool = False

    # The minimum similarity threshold when searching for sound names (1.0 = exact matches only)
    minsimilarity: float = 0.75

    # How much of a video the /stream command will download (does not apply to /vcstream)
    maxstreamtime: int = 30

    # Maximum number of dice in one command for dice roller (bigger numbers might reach message length cap)
    maxdice: int = 100

    # Maximum number of faces for the dice for dice roller
    maxfaces: int = 10000


@dataclass
class Config:
    """Dataclass that stores user config data for this application.

    Do not instantiate this class directly, call `await Config.load()` to create a config object.
    """

    main: ConfigMain = dataclasses.field(default_factory=ConfigMain)
    chat: ConfigChat = dataclasses.field(default_factory=ConfigChat)
    misc: ConfigMisc = dataclasses.field(default_factory=ConfigMisc)

    def __init__(self) -> None:
        error_msg = "Use `await Config.load()` instead of creating Config directly."
        raise RuntimeError(error_msg)

    @classmethod
    async def load(cls) -> Config:
        self = object.__new__(cls)
        self.main = ConfigMain()
        self.chat = ConfigChat()
        self.misc = ConfigMisc()

        loaded = await try_read_toml(PATH_CONFIG_FILE, {})

        if not loaded:
            logger.warning(f"Failed to load {PATH_CONFIG_FILE}, falling back to default settings")
            return self

        # Use loaded toml file to update fields
        for key in self.__dict__:
            for subkey in self.__dict__[key].__dict__:
                if key in loaded and subkey in loaded[key]:
                    # Try to find subkey in the 'correct' location
                    self.__dict__[key].__dict__[subkey] = loaded[key][subkey]
                else:
                    # Try to find subkey in 'incorrect' locations, in case dataclasses had their settings moved around
                    for other_key in loaded:
                        if other_key != key and subkey in loaded[other_key]:
                            self.__dict__[key].__dict__[subkey] = loaded[other_key][subkey]
                            break

        return self

    def find_setting(self, search_string: str) -> tuple[str | None, str | None, Any]:
        # Accepts a search string (either the setting name or [group name].[setting name]) and
        # parses/returns the group name, setting name, and current value if it exists
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

    async def save_config(self) -> None:
        await write_toml_to_file(PATH_CONFIG_FILE, dataclasses.asdict(self))

    def update_setting(self, group_name: str, setting_name: str, value: str) -> None:
        lowercase = value.lower()
        if lowercase == "true":
            new_value = True
        elif lowercase == "false":
            new_value = False

        else:
            try:
                new_value = int(value)
            except ValueError:
                try:
                    new_value = float(value)
                except ValueError:
                    new_value = value

        setattr(getattr(self, group_name), setting_name, new_value)


async def verify_settings() -> AsyncGenerator[str]:
    seen = {}
    config = await Config.load()

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
class UserCommand:
    """Class that stores information regarding messages or commands sent to the bot.

    This class acts as a wrapper for both PTB's CallbackContext and Update, and Discord.py's Context. This allows
    commands to easily be written that support both platforms.
    """

    def __init__(self, target_bot: AnyBotAnn, context: AnyContextAnn, update: TelegramUpdate | None) -> None:
        self.target_bot = target_bot
        self.context = context
        self.update = update
        self.response: CommandResponse | None = None

        if isinstance(target_bot, TelegramBot) and update is None:
            error_msg = "Update cannot be None when sending message to telegram bot"
            raise ValueError(error_msg)

        if isinstance(target_bot, TelegramBot) != isinstance(context, TelegramContext):
            error_msg = f"Bot type (telegram bot) and context type ({type(context).__name__}) must match"
            raise TypeError(error_msg)

        if isinstance(target_bot, DiscordBot) != isinstance(context, DiscordContext):
            error_msg = f"Bot type (discord bot) and context type ({type(context).__name__}) must match"
            raise TypeError(error_msg)

    def get_command_name(self) -> str | None:
        """Return name of the command that was called, or None if no command was called."""
        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None:
                raise MissingUpdateInfoError(self)

            if (text := self.update.message.text) is not None and text.startswith('/'):
                return text.split()[0][1:]

            if (caption := self.update.message.caption) is not None and caption.startswith('/'):
                return caption.split()[0][1:]

        elif isinstance(self.context, DiscordContext):
            if self.context.command is not None:
                return self.context.command.name

        return None

    async def track_user_id(self) -> None:
        """Write the calling user's name and ID to a json file for later retrieval."""
        id_dict: dict[str, dict[str, str]] = await try_read_json(PATH_TRACK_USERID, {})
        username = (await self.get_user_name()).lower()
        user_id = self.get_user_id()
        platform_str = self.get_platform_string()

        if platform_str in id_dict:
            id_dict[platform_str][username] = user_id

        else:
            id_dict[platform_str] = {username: user_id}

        await write_json_to_file(PATH_TRACK_USERID, id_dict)

    async def get_user_name(self, *, map_name: bool = False) -> str:
        """Return the username of the user that sent the command or message."""
        username = None
        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None or self.update.message.from_user is None:
                raise MissingUpdateInfoError(self)

            username = self.update.message.from_user.username

        elif isinstance(self.context, DiscordContext):
            username = self.context.author.name

        if username is None:
            raise InvalidBotTypeError(self)

        if map_name:
            return await self.map_username(username)

        return username

    def get_user_id(self) -> str:
        """Return the user ID of the user that sent the command or message."""
        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None or self.update.message.from_user is None:
                raise MissingUpdateInfoError(self)

            return str(self.update.message.from_user.id)

        if isinstance(self.context, DiscordContext):
            return str(self.context.author.id)

        raise InvalidBotTypeError(self)

    async def get_id_by_username(self, username: str) -> str | None:
        """Attempt to retrieve the user ID belonging to the provided username.

        This ID is platform-specific (Discord, Telegram) and can only be retrieved if the
        user has interacted with this bot before and was tracked by UserCommand.track_user_id()
        """
        id_dict = await try_read_json(PATH_TRACK_USERID, {})
        platform_str = self.get_platform_string()

        if platform_str in id_dict and username in id_dict[platform_str]:
            return id_dict[platform_str][username]

        return None

    def is_private(self) -> bool:
        """Return whether the command was called in a private chat or a group chat."""
        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None:
                raise MissingUpdateInfoError(self)

            return self.update.message.chat.type == "private"

        if isinstance(self.context, DiscordContext):
            return self.context.guild is None

        raise InvalidBotTypeError(self)

    def get_args_list(self) -> list[str]:
        """Return the list of arguments provided with the command.

        Example: /test a b c -> ['a', 'b', 'c']
        """
        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None:
                raise MissingUpdateInfoError(self)

            if (text := self.update.message.text) is not None:
                if text.startswith('/'):
                    return text.split()[1:]
                return text.split()

            if (caption := self.update.message.caption) is not None:
                if caption.startswith('/'):
                    return caption.split()[1:]
                return caption.split()

            raise MissingUpdateInfoError(self)

        if isinstance(self.context, DiscordContext):
            if (caption := self.context.message.content).startswith('/'):
                return caption.split()[1:]
            return caption.split()

        raise InvalidBotTypeError(self)

    def get_first_arg(self, *, lowercase: bool = False) -> str | None:
        """Return the first element from the argument list, all lowercase if lowercase=True.

        Example: /test a b c -> 'a'
        """
        args_list = self.get_args_list()

        if args_list:
            if lowercase:
                return args_list[0].lower()
            return args_list[0]

        return None

    def get_user_message(self) -> str:
        """Return the message that this user sent with this UserCommand.

        Examples:
            Hello world! -> 'Hello world!'
            /test a b c -> 'a b c'
        """
        return ' '.join(self.get_args_list())

    async def get_user_attachments(self) -> list[bytearray] | BadRequest | None:
        if isinstance(self.update, TelegramUpdate):
            # NOTE: If this function is returning None for a TelegramBot when you're expecting files,
            # make sure that you have your command registered in FILE_COMMAND_LIST and not COMMAND_LIST!
            if self.update.message is None:
                raise MissingUpdateInfoError(self)

            attachments: list[bytearray] = []
            for file in [self.update.message.document, self.update.message.audio, self.update.message.voice]:
                if file is not None:
                    try:
                        telegram_file = await file.get_file()
                    except BadRequest as e:
                        return e

                    byte_data = await telegram_file.download_as_bytearray()
                    attachments.append(byte_data)

            return attachments or None

        if isinstance(self.context, DiscordContext):
            attachments = [bytearray(await att.read()) for att in self.context.message.attachments]
            return attachments or None

        raise InvalidBotTypeError(self)

    async def get_user_prompt(self) -> str | None:
        # This is used for prompting the GPT chat completion model
        sender = await self.get_user_name(map_name=True)

        if self.response is not None:
            user_message = self.response.user_message
        else:
            user_message = self.get_user_message()

        if not user_message:
            return None

        return f'{sender}: {user_message}'

    async def is_admin(self) -> bool:
        """Return whether the message sender is on the bot's admin list or superadmin list."""
        user_id = self.get_user_id()
        admin_dict: dict[str, dict[str, list[str]]] = await try_read_json(PATH_ADMIN_LIST, {})
        platform_str = self.get_platform_string()

        if platform_str not in admin_dict:
            return False

        if "admin" in admin_dict[platform_str] and user_id in admin_dict[platform_str]["admin"]:
            return True

        # Superadmin rights also give you normal admin rights
        return "superadmin" in admin_dict[platform_str] and user_id in admin_dict[platform_str]["superadmin"]

    async def is_superadmin(self) -> bool:
        """Return whether the message sender is on the bot's superadmin list.

        Normal admin rights are NOT sufficient for this to return True.
        """
        user_id = self.get_user_id()
        admin_dict: dict[str, dict[str, list[str]]] = await try_read_json(PATH_ADMIN_LIST, {})
        platform_str = self.get_platform_string()

        if platform_str not in admin_dict:
            return False

        return "superadmin" in admin_dict[platform_str] and user_id in admin_dict[platform_str]["superadmin"]

    async def assign_super_if_none(self) -> None:
        # Gives the user the superadmin role if no superadmins are assigned
        user_id = self.get_user_id()
        user_name = await self.get_user_name()
        admin_dict: dict[str, dict[str, list[str]]] = await try_read_json(PATH_ADMIN_LIST, {})
        platform_str = self.get_platform_string()

        message_str = f"Assigned vacant superadmin role for {platform_str} to {user_id} ({user_name})"
        if platform_str not in admin_dict:
            admin_dict[platform_str] = {"superadmin": [user_id]}
            logger.warning(message_str)
            await write_json_to_file(PATH_ADMIN_LIST, admin_dict)
            return

        if "superadmin" not in admin_dict[platform_str] or not admin_dict[platform_str]["superadmin"]:
            admin_dict[platform_str]["superadmin"] = [user_id]
            logger.warning(message_str)
            await write_json_to_file(PATH_ADMIN_LIST, admin_dict)
            return

    def get_chat_id(self) -> str:
        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None:
                raise MissingUpdateInfoError(self)

            return str(self.update.message.chat.id)

        if isinstance(self.context, DiscordContext):
            if self.context.guild is not None:
                return str(self.context.guild.id)

            return str(self.context.channel.id)

        raise InvalidBotTypeError(self)

    async def is_whitelisted(self) -> bool:
        """Return whether the chat is on the bot's whitelist."""
        chat_id = self.get_chat_id()
        platform_str = self.get_platform_string()
        whitelist: dict[str, list[str]] = await try_read_json(PATH_WHITELIST, {})

        if platform_str not in whitelist:
            return False

        return chat_id in whitelist[platform_str]

    async def get_and_send_response(self, command_function: CommandAnn) -> None:
        config = await Config.load()

        # Send the command to the bot and await its response
        self.response = await command_function(self)

        text_response = None
        if self.response.send_chat and self.response.bot_message:
            text_response = self.response.bot_message

        if text_response is not None and len(text_response) > config.main.maxmessagelength:
            text_response = text_response[:config.main.maxmessagelength]
            logger.info(f"Cut off bot response at {config.main.maxmessagelength} characters")

        try:
            # Respond with a sound effect
            if isinstance(self.response, SoundResponse):
                await self.send_sound_response(self.response, text_response)

            # Respond with a file
            elif isinstance(self.response, FileResponse):
                await self.send_file_response(self.response, text_response)

            # Respond with text
            elif text_response:
                await self.send_text_response(text_response)

        except (BadRequest, TimedOut, NetworkError, HTTPException) as e:
            await self.send_text_response(TXT_BZZZT_ERROR)

            command_name = self.get_command_name()
            user_message = self.get_user_message()
            error_string = f"{type(e).__name__}: {e}"

            if command_name is not None:
                command_string = f"{command_name} {user_message}".strip()
                logger.error(f"Command '/{command_string}' encountered an exception ({error_string})")
            else:
                logger.error(f"User message '{user_message}' encountered an exception ({error_string})")

            # Re-raise BadRequests, as these indicate a bug with the script that will need to be fixed
            if isinstance(e, BadRequest):
                raise

        # Add the command and its response to memory if necessary
        if self.response.record_memory:
            user_prompt = await self.get_user_prompt()
            await append_to_gpt_memory(user_prompt=user_prompt, bot_response=self.response.bot_message)

    async def send_text_response(self, response: str | None) -> None:
        if isinstance(self.context, TelegramContext) and isinstance(self.update, TelegramUpdate):
            if self.update.effective_chat is None:
                raise MissingUpdateInfoError(self)

            await self.context.bot.send_message(chat_id=self.update.effective_chat.id, text=response)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(response)

        else:
            raise InvalidBotTypeError(self)

    async def send_file_response(self, response: FileResponse, text: str | None) -> None:
        if isinstance(self.context, TelegramContext) and isinstance(self.update, TelegramUpdate):
            if self.update.effective_chat is None:
                raise MissingUpdateInfoError(self)

            await self.context.bot.send_document(
                chat_id=self.update.effective_chat.id,
                document=response.file_path,
                caption=text,
            )

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise InvalidBotTypeError(self)

        # Delete the file that was sent if it was a temporary file
        if response.temp:
            Path(response.file_path).unlink()

    async def send_sound_response(self, response: SoundResponse, text: str | None) -> None:
        if isinstance(self.context, TelegramContext) and isinstance(self.update, TelegramUpdate):
            if self.update.effective_chat is None:
                raise MissingUpdateInfoError(self)

            await self.context.bot.send_voice(
                chat_id=self.update.effective_chat.id,
                voice=response.file_path,
                caption=text,
            )

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise InvalidBotTypeError(self)

        # Delete the file that was sent if it was a temporary file
        if response.temp:
            Path(response.file_path).unlink()

    def is_telegram(self) -> bool:
        """Return whether this UserCommand object was sent to a Telegram bot or not."""
        return isinstance(self.target_bot, TelegramBot)

    def is_discord(self) -> bool:
        """Return whether this UserCommand object was sent to a Discord bot or not."""
        return isinstance(self.target_bot, DiscordBot)

    def get_platform_string(self) -> str:
        """Return the string for the user/bot's current platform.

        Platform string is used to store/retrieve platform-dependent data like user IDs and chat IDs.
        Current platform strings are "telegram" and "discord".
        """
        if self.is_telegram():
            return "telegram"
        if self.is_discord():
            return "discord"
        raise InvalidBotTypeError(self)

    def get_user_voice_channel(self) -> discord.VoiceChannel | None:
        """Return the voice channel that the user who sent this UserCommand is currently in."""
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
        """Return the voice channel that the bot this UserCommand was sent to is currently in."""
        if not isinstance(self.context, DiscordContext):
            return None

        if not isinstance(self.context.voice_client, discord.VoiceClient):
            logger.debug(f"Voice client: {self.context.voice_client}")
            return None

        return self.context.voice_client

    async def map_username(self, username: str) -> str:
        username_map = await try_read_json(PATH_USERNAME_MAP, {})

        try:
            corrected_name = username_map[username.lower()]
        except KeyError:
            return username

        return corrected_name


@dataclass(kw_only=True)
class CommandResponse:
    """Class representing the bot's response to a UserCommand."""

    user_message: str
    bot_message: str
    record_memory: bool = field(default=True)  # Whether user_message and bot_message should be recorded to memory
    send_chat: bool = field(default=True)  # Whether bot_message should be sent to chat


@dataclass(kw_only=True)
class FileResponse(CommandResponse):
    """Subclass of CommandResponse for when the response has a file attached."""

    file_path: str | Path  # Path of file relative to script
    temp: bool = field(default=False)  # Whether the file should be deleted after its sent
    record_memory: bool = field(default=True)
    send_chat: bool = field(default=False)


@dataclass(kw_only=True)
class SoundResponse(FileResponse):
    """Subclass of FileResponse for when the response is to be sent as a voice message.

    Note that the Discord API does not currently (2025-05-22) support bots sending voice messages,
    so the distinction is only important for Telegram.
    """


@dataclass(kw_only=True)
class NoResponse(CommandResponse):
    """Subclass of CommandResponse for when there is no response, and thus no message is to be sent by the bot."""

    def __init__(self) -> None:
        super().__init__(user_message='', bot_message='', record_memory=False, send_chat=False)
# endregion


# ==========================
# EXCEPTION TYPES
# ==========================
# region
class InvalidBotTypeError(TypeError):
    """Exception type to be raised if a function expects a TelegramBot or DiscordBot but receives something else."""

    def __init__(self, user_command: UserCommand, message: str | None = None) -> None:
        self.message = message
        if message is None:
            bot_type = type(user_command.target_bot).__name__
            context_type = type(user_command.context).__name__
            update_type = type(user_command.update).__name__
            type_string = f"Bot: {bot_type}, Context: {context_type}, Update: {update_type}?"
            self.message = f"Function failed for provided types ({type_string})"

        super().__init__(self.message)


class MissingUpdateInfoError(ValueError):
    """Exception type to be raised if a function is passed a Telegram Update but it is missing information."""

    def __init__(self, user_command: UserCommand, message: str | None = None) -> None:
        update = user_command.update
        if message is not None:
            self.message = message

        elif update is None:
            self.message = "Update cannot be None"

        elif update.message is None:
            self.message = "Update.message cannot be None"

        elif (update.message.text is None and update.message.caption is None):
            self.message = "Update.message.text and Update.message.caption cannot both be None"

        elif update.message.from_user is None:
            self.message = "Update.message.from_user cannot be None"

        elif update.effective_chat is None:
            self.message = "Update.effective_chat cannot be None"

        if update is not None:
            logger.error(f"UPDATE DICT: {update.to_dict()}")

        super().__init__(self.message)
# endregion


# ==========================
# TYPE ANNOTATIONS
# ==========================
# region
CommandAnn = Callable[[UserCommand], types.CoroutineType[Any, Any, CommandResponse]]
TelegramBotAnn = TelegramBot[Any, Any, Any, Any, Any, Any]
DiscordBotAnn = DiscordBot
AnyBotAnn = TelegramBotAnn | DiscordBotAnn
TelegramContextAnn = TelegramContext[Any, Any, Any, Any]
DiscordContextAnn = DiscordContext[Any]
AnyContextAnn = TelegramContextAnn | DiscordContextAnn
TelegramFuncAnn = Callable[[TelegramUpdate, TelegramContextAnn], types.CoroutineType[Any, Any, None]]
DiscordFuncAnn = Callable[[DiscordContextAnn], types.CoroutineType[Any, Any, None]]
# endregion

# ==========================
# WRAPPERS
# ==========================
# region
def requireadmin(function: CommandAnn) -> CommandAnn:
    # Put this decorator on a function using @requireadmin to prevent its use without admin rights
    @functools.wraps(function)
    async def admin_wrapper(user_command: UserCommand) -> CommandResponse:
        config = await Config.load()
        if config.main.requireadmin and not await user_command.is_admin():
            user_message = "Can I do that sensitive thing that requires superadmin rights?"
            return CommandResponse(user_message=user_message, bot_message=random.choice(TXT_NO_PERMISSIONS))

        return await function(user_command)

    admin_wrapper.requireadmin = True  # type: ignore | Used to flag whether a function requries admin rights or not
    return admin_wrapper


def requiresuper(function: CommandAnn) -> CommandAnn:
    # Put this decorator on a functio using @requiresuper to prevent its use without superadmin rights
    # This is strictly stronger than admin rights, normal admin rights are insufficent
    @functools.wraps(function)
    async def superadmin_wrapper(user_command: UserCommand) -> CommandResponse:
        config = await Config.load()
        if config.main.requireadmin and not await user_command.is_superadmin():
            user_message = "Can I do that sensitive thing that requires superadmin rights?"
            return CommandResponse(user_message=user_message, bot_message=random.choice(TXT_NO_PERMISSIONS))

        return await function(user_command)

    superadmin_wrapper.requiresuper = True  # type: ignore | Used to flag whether a function requries superadmin rights or not
    return superadmin_wrapper


def wrap_telegram_command(bot: TelegramBotAnn, command_function: CommandAnn) -> TelegramFuncAnn:
    @functools.wraps(command_function)
    async def telegram_wrapper(update: TelegramUpdate, context: TelegramContextAnn) -> None:
        if update.message is None:
            return

        config = await Config.load()
        user_command = UserCommand(bot, context, update)

        # Track this user's platform, name, and user ID. This powers the /getuserid command
        await user_command.track_user_id()

        # If the whitelist is enforced, don't allow interacting with this bot unless on the list
        if config.main.whitelisttelegram and not await user_command.is_whitelisted():
            logger.warning(f"Whitelist rejected chat ID {user_command.get_chat_id()} for Telegram Bot")
            return

        # If there are no superadmins assigned to this bot, assign this user as the superadmin
        if config.main.autosupertelegram:
            await user_command.assign_super_if_none()

            # Automatically disable this setting after checking for superadmins to prevent accidents
            config.main.autosupertelegram = False
            await config.save_config()

        await user_command.get_and_send_response(command_function)

    return telegram_wrapper


def wrap_discord_command(bot: DiscordBotAnn, command_function: CommandAnn) -> DiscordFuncAnn:
    @functools.wraps(command_function)
    async def discord_wrapper(context: DiscordContextAnn) -> None:
        config = await Config.load()
        user_command = UserCommand(bot, context, None)

        # Track this user's platform, name, and user ID. This powers the /getuserid command
        await user_command.track_user_id()

        # If the whitelist is enforced, don't allow interacting with this bot unless on the list
        if config.main.whitelistdiscord and not await user_command.is_whitelisted():
            logger.warning(f"Whitelist rejected chat ID {user_command.get_chat_id()} for Discord Bot")
            return

        # If there are no superadmins assigned to this bot, assign this user as the superadmin
        if config.main.autosuperdiscord:
            await user_command.assign_super_if_none()

            # Automatically disable this setting after checking for superadmins to prevent accidents
            config.main.autosuperdiscord = False
            await config.save_config()

        await user_command.get_and_send_response(command_function)

    return discord_wrapper
# endregion


# region
async def append_to_gpt_memory(*, user_prompt: str | None = None, bot_response: str | None = None) -> None:
    config = await Config.load()

    if not config.chat.usememory:
        return

    memory = await get_full_chat_memory()

    if user_prompt is not None:
        memory.append({"role": "user", "content": user_prompt})

    if bot_response is not None:
        memory.append({"role": "assistant", "content": bot_response})

    # We cap the amount of memory stored (configurable) for storage space purposes
    memory_point = max(0, len(memory) - config.chat.memorysize)
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

    recall_point = max(0, len(memory_list) - config.chat.recallsize)
    return memory_list[recall_point:]


def convert_to_ascii(text: str) -> str:
    """Attempt to replace all non-ascii characters in string with ascii equivalents (e.g. 'é' -> 'e')

    Removes all characters that have no good equivalents.
    """
    text = html.unescape(text)
    return unidecode.unidecode(text, errors="replace", replace_str='')


def make_valid_filename(input_str: str, *, strict: bool) -> str:
    """Return input_str with characters unsuitable for filenames replaced or removed."""
    input_str = convert_to_ascii(input_str)

    if strict:
        return ''.join(char for char in input_str if char.isalnum())

    valid_chars = [*string.ascii_uppercase, *string.ascii_lowercase, *string.digits, *"-_()'"]
    return ''.join(char for char in input_str if char in valid_chars)


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
            data = toml.loads(await f.read())
            return data or default
    except FileNotFoundError:
        logger.error(f"Tried to open file at {path}, but file did not exist")
    except toml.TomlDecodeError:
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
    with contextlib.suppress(FileExistsError):
        await aiofiles.os.mkdir(Path(path).parent)

    async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
        content = toml.dumps(data)
        await f.write(content)
# endregion
