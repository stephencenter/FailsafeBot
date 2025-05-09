"""Module for simulating UserCommands and testing its methods."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from loguru import logger
from telegram import Update as TelegramUpdateType
from telegram.ext import Application as TelegramBotType
from telegram.ext import CallbackContext as TelegramContextType

from common import UserCommand


# ==========================
# TELEGRAM CLASSES
# ==========================
# region
class FakeTelegramApplication:
    def __init(self) -> None:
        pass

    @property
    def __class__(self) -> type:  # type: ignore
        return TelegramBotType


class FakeTelegramUser:
    def __init__(self, username: str, id: str) -> None:  # noqa: A002
        self.username = username
        self.id = id


class FakeTelegramUpdate:
    def __init__(self, message: FakeTelegramMessage | None) -> None:
        self.message = message

    @property
    def __class__(self) -> type:  # type: ignore
        return TelegramUpdateType


class FakeTelegramMessage:
    def __init__(self, text: str | None, caption: str | None, chat: FakeTelegramChat, from_user: FakeTelegramUser) -> None:
        self.text = text
        self.caption = caption
        self.chat = chat
        self.from_user = from_user


class FakeTelegramContext:
    @property
    def __class__(self) -> type:  # type: ignore
        return TelegramContextType


class FakeTelegramChat:
    def __init__(self, id: str, type: str) -> None:  # noqa: A002
        self.id = id
        self.type = type


# ==========================
# DISCORD CLASSES
# ==========================
# region
"""
class FakeDiscordUser:
    def __init__(self, id, name) -> None:
        self.id = id
        self.name = name


class FakeDiscordAttachment:
    def __init__(self, url, filename) -> None:
        self.url = url
        self.filename = filename


class FakeDiscordMessage:
    def __init__(self, content, author, attachments=None) -> None:
        self.content = content
        self.author = author
        self.attachments = attachments or []


class FakeDiscordContext:
    def __init__(self, message) -> None:
        self.message = message


class FakeDiscordBot:
    pass
"""


def telegram_create_usercommand(test_input: TestInput) -> tuple[UserCommand, UserCommand]:
    bot = FakeTelegramApplication()
    context = FakeTelegramContext()
    chat = FakeTelegramChat(test_input.chat_id, test_input.chat_type_str)
    user = FakeTelegramUser(test_input.user_name, test_input.user_id)
    message_a = FakeTelegramMessage(test_input.text_input, None, chat, user)
    message_b = FakeTelegramMessage(None, test_input.text_input, chat, user)
    update_a = FakeTelegramUpdate(message_a)
    update_b = FakeTelegramUpdate(message_b)

    return UserCommand(bot, context, update_a), UserCommand(bot, context, update_b)  # type: ignore


@dataclass
class TestInput:
    text_input: str
    user_name: str
    user_id: str
    chat_id: str
    chat_type_str: str
    args_list: list[str]
    first_arg: str | None
    user_msg: str
    chat_type_bool: bool


async def test_args_list(user_command: UserCommand, item: TestInput) -> bool:
    return user_command.get_args_list() == item.args_list


async def test_first_arg(user_command: UserCommand, item: TestInput) -> bool:
    return user_command.get_first_arg() == item.first_arg


async def test_user_message(user_command: UserCommand, item: TestInput) -> bool:
    return user_command.get_user_message() == item.user_msg


async def test_user_name(user_command: UserCommand, item: TestInput) -> bool:
    return await user_command.get_user_name() == item.user_name


async def test_user_id(user_command: UserCommand, item: TestInput) -> bool:
    return user_command.get_user_id() == item.user_id


async def test_chat_id(user_command: UserCommand, item: TestInput) -> bool:
    return user_command.get_chat_id() == item.chat_id


async def test_chat_type(user_command: UserCommand, item: TestInput) -> bool:
    return user_command.is_private() == item.chat_type_bool


async def perform_tests() -> None:
    input_list: list[TestInput] = [
        TestInput("test 123 abc 456", "test_user", "11234", "321", "private",
            ["test", "123", "abc", "456"], "test", "test 123 abc 456", chat_type_bool=True,
        ),
        TestInput("/test test 123 abc 456", "test_user", "11234", "321", "public",
            ["test", "123", "abc", "456"], "test", "test 123 abc 456", chat_type_bool=False,
        ),
        TestInput("/test", "test_user", "11234", "321", "private",
            [], None, "", chat_type_bool=True,
        ),
        TestInput("/", "test_user", "11234", "321", "public",
            [], None, "", chat_type_bool=False,
        ),
        TestInput("", "test_user", "11234", "321", "private",
            [], None, "", chat_type_bool=True,
        ),
    ]

    for index, item in enumerate(input_list):
        for command in zip(telegram_create_usercommand(item), ["a", "b"], strict=True):
            for test in [test_args_list, test_first_arg, test_user_message, test_user_name, test_user_id, test_chat_id, test_chat_type]:
                result = await test(command[0], item)
                if result:
                    logger.info(f"Item {index}{command[1]} passed {test.__name__}()")
                else:
                    logger.error(f"Item {index}{command[1]} failed {test.__name__}()")


if __name__ == "__main__":
    asyncio.run(perform_tests())
