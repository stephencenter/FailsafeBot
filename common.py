import os
import random
import json
from typing import Callable, TypeVar
import discord
from discord.ext.commands import Bot as DiscordBot
from discord.ext.commands import Context as DiscordContext
from discord.errors import HTTPException
from telegram.ext import Application as TelegramBot
from telegram.ext import CallbackContext as TelegramContext
from telegram import Update as TelegramUpdate
from telegram.error import BadRequest, TimedOut, NetworkError
from loguru import logger
import settings
import chat
import common

APPLICATION_NAME = 'FailsafeBot'
VERSION_NUMBER = 'v1.1.0'

LOGGING_FILE_PATH = "Data/logging/log.txt"
RESPONSES_PATH = "Data/response_list.txt"
USERNAME_MAP_PATH = "Data/username_map.json"
TELEGRAM_WHITELIST_PATH = "Data/tg_whitelist.txt"
ADMINS_PATH = "Data/admins.txt"

T = TypeVar('T')

class CommandResponse:
    def __init__(self, user_message: str, bot_message: str, record_to_memory: bool = True, send_to_chat: bool = True):
        self.user_message: str = user_message
        self.bot_message: str = bot_message
        self.record_to_memory: bool = record_to_memory  # Whether user_message and bot_message should be recorded to memory
        self.send_to_chat: bool = send_to_chat  # Whether bot_message should be sent to chat

class FileResponse(CommandResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True, temp: bool = False, send_to_chat: bool = True):
        super().__init__(user_message, bot_message, record_to_memory=record_to_memory, send_to_chat=send_to_chat)
        self.file_path: str = file_path  # The path of the file to send
        self.temp: bool = temp  # Whether the file should be deleted after being sent

class SoundResponse(FileResponse):
    def __init__(self, user_message: str, bot_message: str, file_path: str, record_to_memory: bool = True):
        super().__init__(user_message, bot_message, file_path, record_to_memory, temp=False, send_to_chat=False)

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

class ChatCommand:
    def __init__(self, target_bot, context, update = None):
        if isinstance(target_bot, TelegramBot) and update is None:
            raise ValueError("Update cannot be None when sending message to telegram bot")

        if isinstance(target_bot, TelegramBot) != isinstance(context, TelegramContext):
            raise ValueError("Context type and bot type must match")

        if isinstance(target_bot, DiscordBot) != isinstance(context, DiscordContext):
            raise ValueError("Context type and bot type must match")

        if not isinstance(target_bot, TelegramBot) and not isinstance(target_bot, DiscordBot):
            raise NotImplementedError("Currently only supporting Telegram and Discord bots")

        self.target_bot = target_bot
        self.context = context
        self.update = update

    def get_author(self, map_name=False) -> str:
        # Returns the username of the user that sent the command or message
        if isinstance(self.update, TelegramUpdate):
            author_name = self.update.message.from_user.username

        elif isinstance(self.context, DiscordContext):
            author_name = self.context.author.name

        else:
            raise NotImplementedError()

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
            raise NotImplementedError()

        return user_id

    def is_private(self) -> bool:
        # Returns whether the command was called in a private chat or a group chat
        if isinstance(self.update, TelegramUpdate):
            return self.update.message.chat.type == "private"

        elif isinstance(self.context, DiscordContext):
            return self.context.guild is None

        raise NotImplementedError()

    def get_args_list(self) -> list[str]:
        # Returns the list of arguments provided with the command
        # e.g. /test a b c -> ['a', 'b', 'c']
        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            return self.context.args

        elif isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            return self.context.message.content.split()[1:]

        raise NotImplementedError()

    def get_user_message(self) -> str:
        # Returns the arguments provided with the command as a string
        # e.g. /test a b c -> 'a b c'
        if isinstance(self.context, TelegramContext) and self.context.args is not None:
            return ' '.join(self.context.args)

        elif isinstance(self.update, TelegramUpdate) and self.update.message.text is not None:
            return self.update.message.text

        elif isinstance(self.context, DiscordContext) and len(self.context.message.content) > 0:
            return ' '.join(self.context.message.content.split()[1:])

        raise NotImplementedError()

    def is_admin(self) -> bool:
        # Returns whether the message sender is on the bot's admin list
        if not settings.Config().main.requireadmin:
            return True

        user_id = self.get_author_id()
        admin_list = common.try_read_lines(ADMINS_PATH, [])

        return user_id in admin_list

    def is_whitelisted(self) -> bool:
        # Returns whether the chat is on the bot's whitelist (telegram only)
        if not settings.Config().main.usewhitelist:
            return True

        if isinstance(self.update, TelegramUpdate):
            chat_id = str(self.update.message.chat.id)
            whitelist = common.try_read_lines(TELEGRAM_WHITELIST_PATH, [])

            return chat_id in whitelist

        return True

    async def send_text_response(self, response: str | None):
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_message(chat_id=self.update.effective_chat.id, text=response)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(response)

        else:
            raise NotImplementedError()

    async def send_file_response(self, response: FileResponse, text: str | None):
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_document(chat_id=self.update.effective_chat.id, document=response.file_path, caption=text)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise NotImplementedError()

        # Delete the file that was sent if it was a temporary file
        if response.temp:
            os.remove(response.file_path)

    async def send_sound_response(self, response: SoundResponse, text: str | None):
        if isinstance(self.update, TelegramUpdate):
            await self.context.bot.send_voice(chat_id=self.update.effective_chat.id, voice=response.file_path, caption=text)

        elif isinstance(self.context, DiscordContext):
            await self.context.send(content=text, file=discord.File(response.file_path))

        else:
            raise NotImplementedError()

    def map_username(self, username: str) -> str:
        username_map = common.try_read_json(USERNAME_MAP_PATH, dict())

        try:
            corrected_name = username_map[username.lower()]
        except KeyError:
            return username

        return corrected_name

async def send_response(command: Callable, chat_command: ChatCommand) -> None:
    config = settings.Config()
    command_response: CommandResponse = await command(chat_command)

    if command_response.send_to_chat and command_response.bot_message:
        text_response = command_response.bot_message

        if len(text_response) > config.main.maxmessagelength:
            text_response = text_response[:config.main.maxmessagelength]
            logger.info(f"Cut off bot response at {config.main.maxmessagelength} characters")

    else:
        text_response = None

    try:
        # Respond with a sound effect
        if isinstance(command_response, SoundResponse):
            await chat_command.send_sound_response(command_response, text_response)

        # Respond with a file
        elif isinstance(command_response, FileResponse):
            await chat_command.send_file_response(command_response, text_response)

        # Respond with text
        elif text_response:
            await chat_command.send_text_response(text_response)

    except (BadRequest, TimedOut, NetworkError, HTTPException) as e:
        logger.error(e)
        error_response = "*BZZZT* my telecommunication circuits *BZZZT* appear to be *BZZZT* malfunctioning *BZZZT*"
        await chat_command.send_text_response(error_response)

    # Add the command and its response to memory if necessary
    if command_response.record_to_memory:
        user_prompt = chat.generate_user_prompt(command_response.user_message, chat_command)
        chat.append_to_memory(user_prompt=user_prompt, bot_prompt=command_response.bot_message)

def command_wrapper(bot: TelegramBot | DiscordBot, command: Callable) -> Callable:
    if isinstance(bot, TelegramBot):
        async def wrapper_function(update, context): # type: ignore
            chat_command = ChatCommand(bot, context, update=update)

            if not chat_command.is_whitelisted():
                # Telegram doesn't allow you to make "private" bots, meaning anyone can add your bot to their chat
                # and use up your CPU time. This check prevents the bot from responding to commands unless it comes
                # from a whitelisted chat
                logger.warning(f"whitelist rejected {update.message.chat.id}")
                return

            await send_response(command, chat_command)

    elif isinstance(bot, DiscordBot):
        async def wrapper_function(context):
            chat_command = ChatCommand(bot, context)
            await send_response(command, chat_command)

    return wrapper_function

def try_read_json(path: str, default: T) -> T:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default

def try_read_lines(path: str, default) -> list:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return [x.strip() for x in f.readlines()]
    except OSError:
        return default

def write_json_to_file(path: str, data) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def write_lines_to_file(path: str, lines) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(f"{x}\n" for x in lines)
