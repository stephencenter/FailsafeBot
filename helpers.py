import json
import typing

APPLICATION_NAME = 'FailsafeBot'
VERSION_NUMBER = 'v1.1.0'
LOGGING_FILE_PATH = "Data/logging/log.txt"
RESPONSES_PATH = "Data/response_list.txt"

T = typing.TypeVar('T')

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
