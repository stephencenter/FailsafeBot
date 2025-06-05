"""Runway for starting the script.

This module defines functions for building the project structure,
as well as checking for common data problems.

The functions in this module are called from the `main` module upon script
startup.
"""

import logging
import sys
import types
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import aiohttp
from discord.errors import ConnectionClosed
from loguru import logger
from telegram.error import Conflict as TelegramConflict
from telegram.error import NetworkError

import common

# Directories to check for and create if they don't exist
directories = {
    common.PATH_DATA_FOLDER,
    common.PATH_TEMP_FOLDER,
    common.PATH_SOUNDS_FOLDER,
    common.PATH_LOGGING_FOLDER,
    common.PATH_MARKOV_INPUT,
}

# Text files (.txt, .json, etc) to check for and create if they don't exist
text_files = {
    common.PATH_TELEGRAM_TOKEN,
    common.PATH_DISCORD_TOKEN,
    common.PATH_ADMIN_LIST,
    common.PATH_WHITELIST,
    common.PATH_CONFIG_FILE,
    common.PATH_OPENAI_KEY,
    common.PATH_ELEVENLABS_KEY,
    common.PATH_USERNAME_MAP,
    common.PATH_SOUND_ALIASES,
    common.PATH_PLAYCOUNTS,
    common.PATH_GPT_PROMPT,
    common.PATH_MARKOV_CHAIN,
    common.PATH_MEMORY_LIST,
    common.PATH_GPT_PREPEND,
    common.PATH_RESPONSE_LIST,
    common.PATH_LOGGING_FILE,
    common.PATH_TRIVIA_SCORES,
    common.PATH_D10000_LIST,
    common.PATH_ACTIVE_EFFECTS,
    common.PATH_CURRENT_TRIVIA,
    common.PATH_TRACK_USERID,
}

# Paths that we will not create, this is exclusions for the globals checking from common.py
do_not_create: set[Path] = set()


class InterceptHandler(logging.Handler):
    """Class that intercepts errors from libraries that use logging, and redirects to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.exc_info is not None:
            exc_type = record.exc_info[0]
            if exc_type is TelegramConflict:
                error_msg = "Multiple instances of Telegram bot are running! Bot will not work until this is resolved"
                logger.critical(error_msg)
                return

            if exc_type is NetworkError:
                error_msg = f"Temporarily lost connection to telegram servers ({exc_type.__name__})"
                logger.warning(error_msg)
                return

            if exc_type in {ConnectionClosed, aiohttp.ClientConnectorError, aiohttp.ClientConnectorDNSError}:
                error_msg = f"Temporarily lost connection to discord servers ({exc_type.__name__})"
                logger.warning(error_msg)
                return

        # Convert LogRecord to Loguru format
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.bind(request_id="app").opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def init_logging() -> None:
    # Clear default logger
    logger.remove()

    # Define format for logging
    msg_format = "{message}"
    level_format = "<level>[{level}]</level>"
    time_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green>"
    func_format = "<cyan>{name}:{function}:{line}</cyan>"

    logger_format = f"{msg_format} {level_format} {time_format} {func_format}"

    # Add console output
    logger.add(sys.stderr, level="DEBUG", backtrace=False, diagnose=False, format=logger_format, enqueue=True)

    # Add file output with error logging
    logger.add(common.PATH_LOGGING_FILE, level="WARNING", backtrace=False, diagnose=False, format=logger_format,
               enqueue=True)

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    # Override logging levels for individual modules
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)

    # Hook unhandled exceptions
    def log_exceptions(exc_type: type, exc_value: BaseException, exc_traceback: types.TracebackType | None) -> None:
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).error("Unhandled exception")

    sys.excepthook = log_exceptions


def check_for_untracked_paths() -> Generator[str]:
    for obj in common.__dict__.values():
        if isinstance(obj, Path) and obj not in directories | text_files | do_not_create:
            yield f"Path '{obj}' is expected but was not checked for"


def create_project_structure() -> Generator[str]:
    for folder in directories:
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            yield f"Created required directory {folder}"

    for file in text_files:
        if not file.exists():
            file.touch(exist_ok=True)
            yield f"Created required file {file}"


def clear_temp_folder() -> Generator[str]:
    deleted_temp = False
    for temp in common.PATH_TEMP_FOLDER.iterdir():
        temp.unlink()
        deleted_temp = True

    if deleted_temp:
        yield f"Cleared temp directory '{common.PATH_TEMP_FOLDER}'"


async def check_superadmins() -> AsyncGenerator[str]:
    admin_dict = await common.try_read_json(common.PATH_ADMIN_LIST, {})
    config = await common.Config.load()

    platform_list = [("telegram", config.main.autosupertelegram), ("discord", config.main.autosuperdiscord)]
    for p_str, autoassign in platform_list:
        if not autoassign:
            continue

        if not (p_str in admin_dict and "superadmin" in admin_dict[p_str] and admin_dict[p_str]["superadmin"]):
            yield f"{p_str.title()} has no superadmins, first interaction will get role"
