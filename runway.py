import logging
import sys
from collections.abc import Generator
from pathlib import Path

from loguru import logger

import common

# Directories to check for and create if they don't exist
directories = {
    common.DATA_FOLDER_PATH,
    common.TEMP_FOLDER_PATH,
    common.SOUNDS_FOLDER_PATH,
    common.LOGGING_FOLDER_PATH,
}

# Text files (.txt, .json, etc) to check for and create if they don't exist
text_files = {
    common.TELEGRAM_TOKEN_PATH,
    common.DISCORD_TOKEN_PATH,
    common.ADMINS_PATH,
    common.TELEGRAM_WHITELIST_PATH,
    common.CONFIG_PATH,
    common.OPENAI_KEY_PATH,
    common.ELEVENLABS_KEY_PATH,
    common.USERNAME_MAP_PATH,
    common.ALIAS_PATH,
    common.PLAYCOUNTS_PATH,
    common.GPT_PROMPT_PATH,
    common.MARKOV_PATH,
    common.MEMORY_PATH,
    common.PREPEND_PATH,
    common.RESPONSES_PATH,
    common.LOGGING_FILE_PATH,
    common.TRIVIA_POINTS_PATH,
    common.TRIVIA_MEMORY_PATH,
    common.D10000_LIST_PATH,
    common.ACTIVE_EFFECTS_PATH,
    common.TRIVIA_CURRENT_PATH,
    common.TRACK_USERID_PATH,
}

# Paths that we will not create, this is exclusions for the globals checking from common.py
do_not_create = set()


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Convert LogRecord to Loguru format
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.bind(request_id="app").opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def init_logging() -> None:
    # Clear default logger
    logger.remove()

    # Add console output
    info_format = "{message} <level>[{level}]</level> <green>{time:YYYY-MM-DD HH:mm:ss}</green> <cyan>{name}:{function}:{line}</cyan>"
    logger.add(sys.stderr, level="INFO", backtrace=False, diagnose=False, format=info_format)

    # Add file output with error logging
    logger.add(common.LOGGING_FILE_PATH, level="WARNING", backtrace=False, diagnose=False)

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    # Override logging levels for individual modules
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)

    # Hook unhandled exceptions
    def log_exceptions(exc_type, exc_value, exc_traceback) -> None:  # noqa: ANN001
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).error("Unhandled exception")

    sys.excepthook = log_exceptions


def check_for_missing_paths() -> Generator[str]:
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
    for temp in common.TEMP_FOLDER_PATH.iterdir():
        temp.unlink()
        deleted_temp = True

    if deleted_temp:
        yield f"Cleared temp directory '{common.TEMP_FOLDER_PATH}'"
