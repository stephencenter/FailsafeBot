from collections.abc import Generator
from pathlib import Path

import common

directories = {
    common.DATA_FOLDER_PATH,
    common.TEMP_FOLDER_PATH,
    common.SOUNDS_FOLDER_PATH,
    common.LOGGING_FOLDER_PATH,
}

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
}


def create_project_structure() -> Generator[str]:
    for obj in common.__dict__.values():
        if isinstance(obj, Path) and obj not in directories | text_files:
            yield f"Path '{obj}' is expected but was not checked for"

    for folder in directories:
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            yield f"Created required directory {folder}"

    for file in text_files:
        if not file.exists():
            file.touch(exist_ok=True)
            yield f"Created required file {file}"

    deleted_temp = False
    for temp in common.TEMP_FOLDER_PATH.iterdir():
        temp.unlink()
        deleted_temp = True

    if deleted_temp:
        yield f"Cleared temp directory '{common.TEMP_FOLDER_PATH}'"
