import json
import random
import typing
from collections.abc import Iterable
from pathlib import Path

import discord
from discord.ext.commands import Bot as DiscordBot
from discord.ext.commands import Context as DiscordContext
from telegram import Update as TelegramUpdate
from telegram.ext import Application as TelegramBot
from telegram.ext import CallbackContext as TelegramContext

import settings

APPLICATION_NAME = 'FailsafeBot'
VERSION_NUMBER = 'v1.1.1'

ELEVENLABS_KEY_PATH = "Data/eleven_key.txt"
LOGGING_FILE_PATH = "Data/logging/log.txt"
RESPONSES_PATH = "Data/response_list.txt"
USERNAME_MAP_PATH = "Data/username_map.json"
TELEGRAM_WHITELIST_PATH = "Data/tg_whitelist.txt"
TEMP_FOLDER_PATH = ".temp"
ADMINS_PATH = "Data/admins.txt"

T = typing.TypeVar('T')

class CommandResponse:
    def __init__(self, user_message: str, bot_message: str, *, record_to_memory: bool = True, send_to_chat: bool = True):
        self.user_message: str = user_message
        self.bot_message: str = bot_message
        self.record_to_memory: bool = record_to_memory  # Whether user_message and bot_message should be recorded to memory
        self.send_to_chat: bool = send_to_chat  # Whether bot_message should be sent to chat

class FileResponse(CommandResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str | Path, *, record_to_memory: bool = True, temp: bool = False):
        super().__init__(user_message, bot_message, record_to_memory=record_to_memory, send_to_chat=False)
        self.file_path: str | Path = file_path  # The path of the file to send
        self.temp: bool = temp  # Whether the file should be deleted after being sent

class SoundResponse(FileResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str | Path, *, record_to_memory: bool = True, temp: bool = False):
        super().__init__(user_message, bot_message, file_path, record_to_memory=record_to_memory, temp=temp)

class NoPermissionsResponse(CommandResponse):
    def __init__(self, user_message: str):
        chosen_response = random.choice([
            "You don't have the right, O you don't have the right.",
            "You think I'd let just anyone do this?"
        ])
        super().__init__(user_message, chosen_response, record_to_memory=True, send_to_chat=True)

class NoResponse(CommandResponse):
    def __init__(self):
        super().__init__('', '', record_to_memory=False, send_to_chat=False)

class UserCommand:
    def __init__(self, target_bot: TelegramBot | DiscordBot, context: TelegramContext | DiscordContext, update: TelegramUpdate | None = None):
        if isinstance(target_bot, TelegramBot) and update is None:
            raise ValueError("Update cannot be None when sending message to telegram bot")

        if isinstance(target_bot, TelegramBot) != isinstance(context, TelegramContext):
            raise TypeError("Context type and bot type must match")

        if isinstance(target_bot, DiscordBot) != isinstance(context, DiscordContext):
            raise TypeError("Context type and bot type must match")

        if not isinstance(target_bot, TelegramBot) and not isinstance(target_bot, DiscordBot):
            raise NotImplementedError("Currently only supporting Telegram and Discord bots")

        self.target_bot = target_bot
        self.context = context
        self.update = update
        self.response: CommandResponse | None = None

    def get_author(self, *, map_name: bool = False) -> str:
        # Returns the username of the user that sent the command or message
        if isinstance(self.update, TelegramUpdate):
            author_name = self.update.message.from_user.username

        elif isinstance(self.context, DiscordContext):
            author_name = self.context.author.name

        else:
            raise NotImplementedError

        if author_name is None:
            return ''

        if map_name:
            return self.map_username(author_name)

        return author_name

    def get_author_id(self) -> str:
        # Returns the user ID of the user that sent the command or message
        if isinstance(self.update, TelegramUpdate):
            user_id = str(self.update.message.from_user.id)

        elif isinstance(self.context, DiscordContext):
            user_id = str(self.context.author.id)

        else:
            raise NotImplementedError

        return user_id

    def is_private(self) -> bool:
        # Returns whether the command was called in a private chat or a group chat
        if isinstance(self.update, TelegramUpdate):
            return self.update.message.chat.type == "private"

        if isinstance(self.context, DiscordContext):
            return self.context.guild is None

        raise NotImplementedError

    def get_args_list(self) -> list[str]:
        # Returns the list of arguments provided with the command
        # e.g. /test a b c -> ['a', 'b', 'c']
        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            return self.context.args

        if isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            return self.context.message.content.split()[1:]

        raise NotImplementedError

    def get_first_arg(self, *, lowercase: bool = False) -> str | None:
        args_list = []

        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            args_list = self.context.args

        elif isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            args_list = self.context.message.content.split()[1:]

        else:
            raise NotImplementedError

        try:
            if lowercase:
                return args_list[0].lower()
            return args_list[0]

        except IndexError:
            return None

    def get_user_message(self) -> str:
        if self.response is not None:
            return self.response.user_message

        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            return ' '.join(self.context.args)

        if isinstance(self.update, TelegramUpdate) and self.update.message.text is not None:
            return self.update.message.text

        if isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            return ' '.join(self.context.message.content.split()[1:])

        raise NotImplementedError

    def get_user_prompt(self) -> str:
        sender = self.get_author(map_name=True)
        user_prompt = f'{sender}: {self.get_user_message()}'

        return user_prompt

    def is_admin(self) -> bool:
        # Returns whether the message sender is on the bot's admin list
        if not settings.Config().main.requireadmin:
            return True

        user_id = self.get_author_id()
        admin_list = try_read_lines(ADMINS_PATH, [])

        return user_id in admin_list

    def is_whitelisted(self) -> bool:
        # Returns whether the chat is on the bot's whitelist (telegram only)
        if not settings.Config().main.usewhitelist:
            return True

        if isinstance(self.update, TelegramUpdate):
            if self.update.message is None:
                return False

            chat_id = str(self.update.message.chat.id)
            whitelist = try_read_lines(TELEGRAM_WHITELIST_PATH, [])

            return chat_id in whitelist

        return True

    async def send_text_response(self, response: str | None) -> None:
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_message(chat_id=self.update.effective_chat.id, text=response)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(response)

        else:
            raise NotImplementedError

    async def send_file_response(self, response: FileResponse, text: str | None) -> None:
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_document(chat_id=self.update.effective_chat.id, document=response.file_path, caption=text)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise NotImplementedError

        # Delete the file that was sent if it was a temporary file
        if response.temp:
            Path(response.file_path).unlink()

    async def send_sound_response(self, response: SoundResponse, text: str | None) -> None:
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_voice(chat_id=self.update.effective_chat.id, voice=response.file_path, caption=text)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise NotImplementedError

        # Delete the file that was sent if it was a temporary file
        if response.temp:
            Path(response.file_path).unlink()

    def is_telegram(self) -> bool:
        return isinstance(self.target_bot, TelegramBot)

    def is_discord(self) -> bool:
        return isinstance(self.target_bot, DiscordBot)

    def get_user_voice_channel(self) -> discord.VoiceChannel | None:
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

def try_read_json(path: str | Path, default: T) -> T:
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default

def try_read_lines(path: str | Path, default: T) -> list | T:
    try:
        with open(path, encoding='utf-8') as f:
            return [x.strip() for x in f]
    except OSError:
        return default

def try_read_single_line(path: str | Path, default: T) -> str | T:
    try:
        with open(path, encoding='utf-8') as f:
            return f.readline().strip()
    except OSError:
        return default

def write_json_to_file(path: str | Path, data: Iterable) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def write_lines_to_file(path: str | Path, lines: list) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(f"{x}\n" for x in lines)
